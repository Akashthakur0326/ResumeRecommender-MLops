import sys
import json
from pathlib import Path
from typing import Dict, List, Tuple

# 1. Path Setup
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from src.vector_db.client import PostgresClient
from src.vector_db.encoder import SemanticEncoder
from utils.logger import setup_logger
from utils.paths import BASE_DIR

# --- GLOBAL CONFIGURATION (The Tweakable Knobs) ---
TOP_K_CATEGORIES = 3

# Weights must sum to approx 1.0 (recommended)
W_SEMANTIC = 0.60   # High weight on meaning (Vector)
W_KEYWORDS = 0.25   # Medium weight on broad vocabulary (Array)
W_MUST_HAVE = 0.15  # Low weight on specific constraints (JSONB) - acts as a tiebreaker

logger = setup_logger(BASE_DIR / "logs" / "scoring.log", "hybrid_scorer")

class HybridScorer:
    def __init__(self):
        self.db = PostgresClient()
        self.encoder = SemanticEncoder()
        
    def _calculate_overlap_score(self, resume_text: str, target_terms: List[str]) -> float:
        """
        Helper: Calculates normalized intersection (Matches / Total Terms).
        Returns 0.0 to 1.0
        """
        if not target_terms:
            return 0.0
            
        resume_lower = resume_text.lower()
        # Simple substring match (can be upgraded to Regex/Spacy later)
        matches = [term for term in target_terms if term.strip().lower() in resume_lower]
        
        return len(matches) / len(target_terms)

    def get_top_recommendations(self, resume_text: str) -> Dict[str, float]:
        """
        Main Pipeline:
        1. Embed Resume.
        2. Fetch Top 20 Candidates via Vector Search (Fast Filter).
        3. Re-Rank using Weighted Formula (Detailed Scoring).
        4. Return Top K.
        """
        # 1. Generate Query Vector
        resume_vector = self.encoder.encode_batch([resume_text])[0]
        if hasattr(resume_vector, 'tolist'):
            resume_vector_list = resume_vector.tolist()
        else:
            resume_vector_list = resume_vector
            
        conn = self.db.connect()
        candidates = []

        try:
            with conn.cursor() as cur:
                # 2. SQL Retrieval: Get the "Vibe Match" candidates first
                # We fetch more than TOP_K (e.g., 20) to allow re-ranking logic to work
                query = """
                    SELECT 
                        job_title, 
                        internal_category,
                        full_definition, 
                        resume_keywords,
                        1 - (anchor_embedding <=> %s::vector) as semantic_score
                    FROM role_definitions
                    ORDER BY anchor_embedding <=> %s::vector
                    LIMIT 20;
                """
                cur.execute(query, (resume_vector_list, resume_vector_list))
                rows = cur.fetchall()

                # 3. Python Re-Ranking Loop
                for row in rows:
                    title, category, full_def, keywords_array, sem_score = row
                    
                    # A. Keyword Score (Broad Array)
                    kw_score = self._calculate_overlap_score(resume_text, keywords_array or [])
                    
                    # B. Must-Have Score (Strict JSONB)
                    must_haves = full_def.get('skill_taxonomy', {}).get('must_have', [])
                    must_score = self._calculate_overlap_score(resume_text, must_haves)

                    # C. Final Weighted Formula
                    final_score = (
                        (sem_score * W_SEMANTIC) + 
                        (kw_score * W_KEYWORDS) + 
                        (must_score * W_MUST_HAVE)
                    )

                    candidates.append({
                        "category": category,
                        "job_title": title,
                        "score": round(final_score, 4),
                        "breakdown": {
                            "semantic": round(sem_score, 2),
                            "keywords": round(kw_score, 2),
                            "must_haves": round(must_score, 2)
                        }
                    })

        except Exception as e:
            logger.error(f"Scoring Failed: {str(e)}")
            return {}
        finally:
            conn.close()

        # 4. Sort and Slice
        candidates.sort(key=lambda x: x['score'], reverse=True)
        top_picks = candidates[:TOP_K_CATEGORIES]

        # Log the winner for debugging
        if top_picks:
            logger.info(f"🏆 Top Match: {top_picks[0]['job_title']} (Score: {top_picks[0]['score']})")

        # Format output as requested (Dict with top categories)
        result = {
            "rankings": top_picks,
            "meta": {
                "weights_used": {"semantic": W_SEMANTIC, "keywords": W_KEYWORDS, "must_have": W_MUST_HAVE}
            }
        }
        return result

# --- Quick Test Block ---
if __name__ == "__main__":
    scorer = HybridScorer()
    
    # Fake Resume Text for Testing
    fake_resume = """
    I am a python developer with experience in building REST APIs using Flask and Django.
    I know SQL and have worked with Docker containers. I love backend engineering.
    """
    
    output = scorer.get_top_recommendations(fake_resume)
    print(json.dumps(output, indent=2))
import sys
import logging
from pathlib import Path
from typing import Dict, List, Any
import numpy as np

# --- CI/CD Path Safety ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.vector_db.client import PostgresClient
from src.vector_db.encoder import SemanticEncoder
from src.parser.engine import ResumeParserEngine
from utils.logger import setup_logger
from utils.paths import BASE_DIR

# --- CONFIGURATION ---
TOP_K_CATEGORIES = 3
JOBS_PER_CATEGORY = 5 

# Hybrid Weights
W_SEMANTIC = 0.60
W_KEYWORDS = 0.25
W_MUST_HAVE = 0.15

logger = setup_logger(BASE_DIR / "logs" / "scoring.log", "resume_scorer")

class ResumeScorerService:
    def __init__(self):
        try:
            self.db = PostgresClient()
            self.encoder = SemanticEncoder()
            # Note: AI Engine is NOT initialized here anymore
            
            self.parser_helper = ResumeParserEngine()
            
            logger.info("✅ ResumeScorerService initialized (Fast Mode).")
        except Exception as e:
            logger.critical(f"❌ Service Initialization Failed: {e}")
            raise RuntimeError("Could not start Resume Scorer Service") from e

    def close(self):
        if hasattr(self, 'db') and self.db:
            self.db.close()

    def _calculate_overlap(self, resume_text: str, target_terms: List[str]) -> float:
        if not target_terms: return 0.0
        resume_lower = resume_text.lower()
        matches = [t for t in target_terms if t.strip().lower() in resume_lower]
        return len(matches) / len(target_terms)

    def _extract_user_skills(self, resume_text: str) -> List[str]:
        try:
            data = self.parser_helper.parse(resume_text)
            return data.get("skills", [])
        except Exception as e:
            logger.warning(f"Skill extraction failed: {e}")
            return []

    def _get_category_matches(self, resume_text: str, resume_vector: List[float]) -> List[Dict]:
        """Stage 1: Identify best fitting Role Archetypes."""
        conn = self.db.connect()
        candidates = []
        try:
            with conn.cursor() as cur:
                query = """
                    SELECT job_title, full_definition, 
                           1 - (anchor_embedding <=> %s::vector) as semantic_score
                    FROM role_definitions
                    ORDER BY anchor_embedding <=> %s::vector
                    LIMIT 15;
                """
                cur.execute(query, (resume_vector, resume_vector))
                rows = cur.fetchall()

                for row in rows:
                    category_title, full_def, sem_score = row
                    keywords = full_def.get('resume_keywords', [])
                    must_haves = full_def.get('skill_taxonomy', {}).get('must_have', [])

                    kw_score = self._calculate_overlap(resume_text, keywords)
                    
                    if must_haves:
                        must_have_text = " ".join(must_haves)
                        must_have_vec = self.encoder.encode_batch([must_have_text])[0]
                        if hasattr(must_have_vec, 'tolist'):
                             must_have_vec = must_have_vec.tolist()
                        dot_product = np.dot(resume_vector, must_have_vec)
                        must_score = max(0.0, dot_product)
                    else:
                        must_score = 0.0
                    
                    final_score = (
                        (sem_score * W_SEMANTIC) + 
                        (kw_score * W_KEYWORDS) + 
                        (must_score * W_MUST_HAVE)
                    )

                    candidates.append({
                        "category": category_title,
                        "score": round(final_score, 4),
                        "meta": {
                            "semantic_match": round(sem_score, 2),
                            "keyword_match": round(kw_score, 2),
                            "must-have_match" : round(must_score, 2)
                        }
                    })

            candidates.sort(key=lambda x: x['score'], reverse=True)
            return candidates[:TOP_K_CATEGORIES]
        except Exception as e:
            logger.error(f"Stage 1 Failed: {e}")
            return []
        finally:
            conn.close()

    def _get_job_postings(self, category: str, resume_vector: List[float]) -> List[Dict]:
        """Stage 2: Fetch Top Matches (Successes)"""
        conn = self.db.connect()
        try:
            with conn.cursor() as cur:
                core_term = category.split()[0] 
                search_term = f"%{core_term}%"
                
                query_fuzzy = """
                    SELECT job_id, job_title, location, metadata, 
                        1 - (description_embedding <=> %s::vector) as match_confidence
                    FROM job_embeddings
                    WHERE category ILIKE %s OR job_title ILIKE %s
                    ORDER BY description_embedding <=> %s::vector ASC
                    LIMIT 20;
                """
                cur.execute(query_fuzzy, (resume_vector, search_term, search_term, resume_vector))
                rows = cur.fetchall()

                if not rows:
                    # Fallback logic omitted for brevity, keep your existing one
                    return []

                jobs = []
                seen_jobs = set()
                
                for row in rows:
                    jid, title, loc, meta, score = row 
                    match_percent = round(score * 100, 1)
                    if match_percent < 50.0: continue 

                    company = meta.get('company', 'Unknown')
                    job_signature = f"{title.lower()}|{company.lower()}"
                    if job_signature in seen_jobs: continue
                    seen_jobs.add(job_signature)

                    jobs.append({
                        "job_id": jid,
                        "title": title,
                        "location": loc,
                        "match_confidence": match_percent,
                        "posted_at": meta.get('posted_at', 'Recent'),
                        "company": company, 
                        "apply_link": meta.get('link', '#'),
                        "salary": meta.get('salary', 'Not Disclosed'),
                        "source": meta.get('source', 'External')
                    })
                    if len(jobs) >= JOBS_PER_CATEGORY: break
                return jobs
        except Exception as e:
            logger.error(f"Stage 2 Failed for {category}: {e}")
            return []
        finally:
            conn.close()

    def _get_category_misses(self, category: str, resume_vector: List[float]) -> List[str]:
        """Fetches the 'Bottom 3' jobs (Gaps)."""
        conn = self.db.connect()
        try:
            with conn.cursor() as cur:
                core_term = category.split()[0]
                search_term = f"%{core_term}%"
                
                query = """
                    SELECT job_title 
                    FROM job_embeddings
                    WHERE category ILIKE %s 
                    ORDER BY description_embedding <=> %s::vector DESC
                    LIMIT 3;
                """
                cur.execute(query, (search_term, resume_vector))
                rows = cur.fetchall()
                
                if not rows:
                    return ["Senior Role", "Principal Engineer", "Architect"]
                return [row[0] for row in rows]
        except Exception as e:
            logger.error(f"Failed to fetch misses: {e}")
            return []
        finally:
            conn.close()

    def get_recommendations(self, resume_text: str) -> Dict[str, Any]:
        """
        FAST MODE: Only does Vector Search & Postgres lookups.
        Returns 'context_for_ai' so the Frontend can call the AI later.
        """
        # 1. Embed
        try:
            resume_vector = self.encoder.encode_batch([resume_text])[0]
            if hasattr(resume_vector, 'tolist'):
                resume_vector = resume_vector.tolist()
        except Exception as e:
            return {"error": "Could not process text"}

        # 2. Extract Skills (Needed for AI later)
        user_skills = self._extract_user_skills(resume_text)

        # 3. Find Categories
        top_categories = self._get_category_matches(resume_text, resume_vector)
        final_results = []

        # 4. Find Jobs (NO AI CALL HERE)
        for cat_data in top_categories:
            category_name = cat_data['category']
            
            # A. Get Jobs
            real_jobs = self._get_job_postings(category_name, resume_vector)
            
            # B. Get Gaps (Still fast, just a DB lookup)
            missed_jobs = self._get_category_misses(category_name, resume_vector)
            
            # C. Prepare Context for Future AI Call
            matched_titles = [j['title'] for j in real_jobs[:3]]
            if not matched_titles: matched_titles = [category_name]

            final_results.append({
                "category": category_name,
                "category_match_score": cat_data['score'],
                "reasoning": cat_data['meta'],
                "recommended_jobs": real_jobs,
                # 📦 NEW: Packaged data for the frontend to use later
                "context_for_ai": {
                    "user_skills": user_skills,
                    "matched_jobs": matched_titles,
                    "gap_jobs": missed_jobs
                }
            })

        return {
            "status": "success",
            "results": final_results
        }
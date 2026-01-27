import sys
import json
import logging
from pathlib import Path
from typing import Dict, List, Any

# --- CI/CD Path Safety ---
# In Docker/CI, file paths can be tricky. We use robust resolution.
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.vector_db.client import PostgresClient
from src.vector_db.encoder import SemanticEncoder
from utils.logger import setup_logger
from utils.paths import BASE_DIR

# --- CONFIGURATION ---
TOP_K_CATEGORIES = 3
JOBS_PER_CATEGORY = 5  # Show top 5 jobs per identified category

# Hybrid Weights
W_SEMANTIC = 0.60
W_KEYWORDS = 0.25
W_MUST_HAVE = 0.15

logger = setup_logger(BASE_DIR / "logs" / "scoring.log", "resume_scorer")

class ResumeScorerService:
    """
    Service Layer: Handles the business logic of matching resumes to jobs.
    Designed to be injected into FastAPI routes.
    """
    def __init__(self):
        # We initialize connections once to save overhead
        try:
            self.db = PostgresClient()
            self.encoder = SemanticEncoder()
            logger.info("✅ ResumeScorerService initialized successfully.")
        except Exception as e:
            logger.critical(f"❌ Service Initialization Failed: {e}")
            raise RuntimeError("Could not start Resume Scorer Service") from e

    def _calculate_overlap(self, resume_text: str, target_terms: List[str]) -> float:
        """Helper: Calculates normalized intersection for keyword matching."""
        if not target_terms: return 0.0
        
        resume_lower = resume_text.lower()
        matches = [t for t in target_terms if t.strip().lower() in resume_lower]
        return len(matches) / len(target_terms)

    def _get_category_matches(self, resume_text: str, resume_vector: List[float]) -> List[Dict]:
        """
        Stage 1: Identify the best fitting 'Role Archetypes'.
        UPDATED: Uses 'job_title' to ensure unique, granular results.
        """
        conn = self.db.connect()
        candidates = []
        
        try:
            with conn.cursor() as cur:
                # ✅ CHANGED: Select 'job_title' instead of 'internal_category'
                query = """
                    SELECT 
                        job_title,  -- The Unique Key (e.g., 'NLP Engineer', 'LLM Engineer')
                        full_definition, 
                        1 - (anchor_embedding <=> %s::vector) as semantic_score
                    FROM role_definitions
                    ORDER BY anchor_embedding <=> %s::vector
                    LIMIT 15;
                """
                cur.execute(query, (resume_vector, resume_vector))
                rows = cur.fetchall()

                for row in rows:
                    # ✅ Unpack job_title as 'category'
                    category_title, full_def, sem_score = row
                    
                    keywords = full_def.get('keywords', [])
                    must_haves = full_def.get('skill_taxonomy', {}).get('must_have', [])

                    kw_score = self._calculate_overlap(resume_text, keywords)
                    must_score = self._calculate_overlap(resume_text, must_haves)

                    final_score = (
                        (sem_score * W_SEMANTIC) + 
                        (kw_score * W_KEYWORDS) + 
                        (must_score * W_MUST_HAVE)
                    )

                    candidates.append({
                        "category": category_title, # Now using the unique title
                        "score": round(final_score, 4),
                        "meta": {
                            "semantic_match": round(sem_score, 2),
                            "keyword_match": round(kw_score, 2)
                        }
                    })

            # Sort and return Top K
            candidates.sort(key=lambda x: x['score'], reverse=True)
            return candidates[:TOP_K_CATEGORIES]

        except Exception as e:
            logger.error(f"Stage 1 (Category Search) Failed: {e}")
            return []
        finally:
            conn.close()

    def _get_job_postings(self, category: str, resume_vector: List[float]) -> List[Dict]:
        """
        Stage 2: Find jobs. Applies Threshold (50%) and Deduplication.
        """
        conn = self.db.connect()
        try:
            with conn.cursor() as cur:
                # 1. Fetch more candidates than we need (e.g., 20) so we can filter duplicates
                query = """
                    SELECT 
                        job_id, job_title, location, metadata, created_at,
                        1 - (description_embedding <=> %s::vector) as match_confidence
                    FROM job_embeddings
                    WHERE category ILIKE %s OR category ILIKE %s
                    ORDER BY description_embedding <=> %s::vector ASC
                    LIMIT 20;
                """
                # Fuzzy search logic
                fuzzy_cat = category.replace("Engineering", "Engineer").replace("Science", "Scientist")
                search_term = f"%{fuzzy_cat[:5]}%"
                
                cur.execute(query, (resume_vector, category, search_term, resume_vector))
                rows = cur.fetchall()
                
                jobs = []
                seen_jobs = set() # To track duplicates (Title + Company)
                
                for row in rows:
                    jid, title, loc, meta, dt, score = row
                    
                    # ---------------------------------------------------------
                    # 1. THRESHOLD CHECK (The "50% Rule")
                    # ---------------------------------------------------------
                    match_percent = round(score * 100, 1)
                    if match_percent < 50.0:
                        continue # Skip this job, it's trash

                    # ---------------------------------------------------------
                    # 2. DEDUPLICATION (The "No Repeats" Rule)
                    # ---------------------------------------------------------
                    company = meta.get('company', 'Unknown')
                    # Create a unique signature for this job
                    job_signature = f"{title.lower()}|{company.lower()}"
                    
                    if job_signature in seen_jobs:
                        continue # Skip duplicate
                    seen_jobs.add(job_signature)

                    # ---------------------------------------------------------
                    # 3. APPEND VALID JOB
                    # ---------------------------------------------------------
                    jobs.append({
                        "job_id": jid,
                        "title": title,
                        "location": loc,
                        "match_confidence": match_percent,
                        "posted_at": dt.strftime("%Y-%m-%d") if dt else "Recent",
                        "company": company, 
                        "apply_link": meta.get('link', '#'),
                        "salary": meta.get('salary', 'Not Disclosed'),
                        "source": meta.get('source', 'External')
                    })
                    
                    # Stop if we hit the limit (e.g., 10 jobs)
                    if len(jobs) >= 10:
                        break
                
                return jobs
        except Exception as e:
            logger.error(f"Stage 2 Failed for {category}: {e}")
            return []
        finally:
            conn.close()
            
    def get_recommendations(self, resume_text: str) -> Dict[str, Any]:
        """
        Main Entry Point: Orchestrates the entire matching pipeline.
        """
        # 1. Embed once (Heavy Operation)
        try:
            resume_vector = self.encoder.encode_batch([resume_text])[0]
            if hasattr(resume_vector, 'tolist'):
                resume_vector = resume_vector.tolist()
        except Exception as e:
            logger.error(f"Embedding Generation Failed: {e}")
            return {"error": "Could not process text"}

        # 2. Find Top Categories (The "Vibe Check")
        top_categories = self._get_category_matches(resume_text, resume_vector)
        
        final_results = []

        # 3. For each category, find real jobs
        for cat_data in top_categories:
            category_name = cat_data['category']
            
            # Fetch jobs from the 'Speed Layer' DB
            real_jobs = self._get_job_postings(category_name, resume_vector)

            final_results.append({
                "category": category_name,
                "category_match_score": cat_data['score'],
                "reasoning": cat_data['meta'],
                "recommended_jobs": real_jobs
            })

        return {
            "status": "success",
            "results": final_results
        }
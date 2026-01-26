import sys
import json
import pandas as pd
from pathlib import Path
from psycopg2.extras import Json

# 1. Path Management: Ensure utils are accessible

project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from utils.paths import BASE_DIR, JOBS_CSV_PATH, KB_JSON_PATH

from src.vector_db.client import PostgresClient
from src.vector_db.encoder import SemanticEncoder
from utils.logger import setup_logger

# Initialize specialized logger for database operations
logger = setup_logger(BASE_DIR / "logs" / "vector_db_ingestion.log", "role_ingestor")

class RoleIngestor:
    def __init__(self):
        """Initializes the Encoder for vectors and the Postgres connection client."""
        self.encoder = SemanticEncoder()
        self.db = PostgresClient()

    def construct_embedding_text(self, role_data: dict) -> str:
        """
        Builds the 'Semantic Context' for the vector.
        Aggregates summary, responsibilities, and must-have skills into a single block.
        Truncates to 2000 chars to respect the transformer's token limits.
        """
        summary = role_data.get('role_summary', '')
        
        # Join list fields into strings for the vector encoder
        resp_list = role_data.get('primary_responsibilities', [])
        responsibilities = " ".join(resp_list) if isinstance(resp_list, list) else str(resp_list)
        
        exp_dict = role_data.get('experience_requirements', {})
        experience = " ".join(exp_dict.values()) if isinstance(exp_dict, dict) else str(exp_dict)
        
        skills = role_data.get('skill_taxonomy', {})
        must_haves = " ".join(skills.get('must_have', [])) if isinstance(skills, dict) else ""
        
        # The 'Anchor' text used to define the role's position in vector space
        text_blob = (
            f"Role: {role_data.get('job_title')} | "
            f"Summary: {summary} | "
            f"Responsibilities: {responsibilities} | "
            f"Requirements: {experience} | "
            f"Key Skills: {must_haves}"
        )
        
        return text_blob[:2000]

    def ingest_roles(self):
        """
        Execution Pipeline:
        1. Validates file presence.
        2. Ensures PGVector HNSW and GIN indexes exist.
        3. Generates embeddings for 34 anchor roles.
        4. Upserts data including Vector, JSONB, and Keyword Arrays.
        """
        logger.info("🚀 Starting Anchor Role Ingestion Pipeline...")

        if not JOBS_CSV_PATH.exists() or not KB_JSON_PATH.exists():
            logger.error("❌ Critical files missing: Verify jobs.csv and Knowledge Base JSON.")
            return

        # Load Master CSV and the detailed Knowledge Base
        jobs_df = pd.read_csv(JOBS_CSV_PATH)
        with open(KB_JSON_PATH, 'r', encoding='utf-8') as f:
            kb_raw = json.load(f)
            # Lookup dict for O(1) matching between CSV rows and JSON details
            kb_lookup = {item['job_title']: item for item in kb_raw}

        # Connection management (Assuming autocommit=True in your PostgresClient)
        conn = self.db.connect()
        success_count = 0

        try:
            with conn.cursor() as cur:
                # --- DB OPTIMIZATION & SCHEMA ENFORCEMENT ---
                
                # Ensure the table supports the new keywords array if not already done via psql
                logger.info("🛠️ Ensuring schema is up to date...")
                cur.execute("ALTER TABLE role_definitions ADD COLUMN IF NOT EXISTS resume_keywords TEXT[];")

                # HNSW Index for Vector Similarity (Semantic Search)
                logger.info("🛠️ Optimizing: Ensuring HNSW vector index exists...")
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_role_anchor_vec 
                    ON role_definitions USING hnsw (anchor_embedding vector_cosine_ops);
                """)

                # GIN Index for JSONB (Structured Constraint Filtering)
                logger.info("🛠️ Optimizing: Ensuring GIN index for JSONB exists...")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_role_full_def_gin ON role_definitions USING GIN (full_definition);")

                # --- INGESTION LOOP ---

                for _, row in jobs_df.iterrows():
                    title = row['job_title']
                    role_details = kb_lookup.get(title)
                    
                    if not role_details:
                        logger.warning(f"⚠️ Details for '{title}' not found in KB. Skipping.")
                        continue

                    # 1. Generate Semantic Anchor (Vector)
                    embedding_text = self.construct_embedding_text(role_details)
                    vector = self.encoder.encode_batch([embedding_text])[0]

                    # 2. Extract Keywords for the Array column (Match Term)
                    # This allows us to use the '&&' overlap operator in Postgres
                    keywords = role_details.get('resume_keywords', [])
                    keywords = [
                        k.strip().lower()
                        for k in role_details.get("resume_keywords", [])
                    ]

                    # 3. UPSERT Logic (Insert or Update if Title exists)
                    query = """
                        INSERT INTO role_definitions 
                        (job_title, internal_category, priority_tier, anchor_embedding, full_definition, resume_keywords)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (job_title) DO UPDATE 
                        SET anchor_embedding = EXCLUDED.anchor_embedding, 
                            full_definition = EXCLUDED.full_definition,
                            internal_category = EXCLUDED.internal_category,
                            priority_tier = EXCLUDED.priority_tier,
                            resume_keywords = EXCLUDED.resume_keywords;
                    """

                    cur.execute(query, (
                        title,
                        row['internal_category'],
                        row['priority_tier'],
                        vector,
                        Json(role_details),
                        keywords
                    ))
                    success_count += 1
                    logger.info(f"✅ Synced Role: {title}")

            logger.info(f"🏁 Success: {success_count} anchor roles fully indexed in Postgres.")

        except Exception as e:
            logger.error(f"🔥 Database Transaction Failed: {str(e)}")
        finally:
            conn.close()

if __name__ == "__main__":
    ingestor = RoleIngestor()
    ingestor.ingest_roles()
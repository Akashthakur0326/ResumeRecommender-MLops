import mlflow
import yaml
import pandas as pd
import time
from psycopg2.extras import execute_values, Json
from pathlib import Path
import sys
import os

# 1. PATH MANAGEMENT
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from src.vector_db.client import PostgresClient
from src.vector_db.encoder import SemanticEncoder
from utils.paths import get_final_data_path, PARAMS_PATH, BASE_DIR
from utils.logger import setup_logger

# 2. CONFIGURATION LOADING
with open(PARAMS_PATH) as f:
    params = yaml.safe_load(f)

CURR_MONTH = params['ingest']['current_month']
BATCH_SIZE = params['ml_models']['vector_encoding']['batch_size']

logger = setup_logger(BASE_DIR / "logs" / "vector_db" / f"{CURR_MONTH}.log")

def prepare_context_text(df: pd.DataFrame) -> list:
    """
    Combines fields to maximize semantic signal for the embedding model.
    """
    return (
        "Job Title: " + df['title'].astype(str) + 
        " | Description: " + df['description'].astype(str).str[:2000]
    ).tolist()

TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI")
if not TRACKING_URI:
    logger.warning("⚠️ MLFLOW_TRACKING_URI not set. Logs may be saved locally!")
else:
    mlflow.set_tracking_uri(TRACKING_URI)

def main():
    mlflow.set_experiment("Job_Vector_Ingestion")

    with mlflow.start_run(run_name=f"Ingest_{CURR_MONTH}"):
        start_time = time.time()
        
        # 4. EXTRACTION
        csv_path = get_final_data_path(CURR_MONTH)
        if not csv_path.exists():
            logger.error(f"❌ Final CSV for {CURR_MONTH} not found.")
            return
        
        df = pd.read_csv(csv_path)
        total_records = len(df)

        # 5. Pre-Encoding Filter
        # Since we just Truncated the DB, this will return 0 existing IDs, 
        # allowing a full re-ingestion.
        db = PostgresClient()
        with db.connect().cursor() as cur:
            cur.execute(
                "SELECT job_id FROM job_embeddings WHERE ingestion_month = %s",
                (CURR_MONTH,)
            )
            existing_ids = {str(row[0]) for row in cur.fetchall()}

        df_new = df[~df['job_id'].astype(str).isin(existing_ids)]
        new_records_count = len(df_new)

        # 6. AUDIT
        mlflow.log_param("ingestion_month", CURR_MONTH)
        mlflow.log_param("new_jobs_detected", new_records_count)

        if df_new.empty:
            logger.info(f"✅ month {CURR_MONTH} is already synchronized.")
            (csv_path.parent / f"{CURR_MONTH}.vector_done").touch()
            return

        # 7. TRANSFORM
        encoder = SemanticEncoder() 
        text_blobs = prepare_context_text(df_new)
        
        enc_start = time.time()
        embeddings = encoder.encode_batch(text_blobs, batch_size=BATCH_SIZE) 
        mlflow.log_metric("encoding_duration_sec", time.time() - enc_start)

        # 8. LOAD
        try:
            data_tuples = []
            for idx, (original_i, row) in enumerate(df_new.iterrows()):
                
                # --- ✅ FIX: CAPTURE ALL METADATA ---
                meta_payload = {
                    "company": row.get('company_name'),
                    "salary": row.get('salary'),
                    "link": row.get('apply_link') or row.get('job_link'),
                    "source": row.get('data_source'),
                    
                    # CAPTURED FROM CSV
                    "posted_at": row.get('posted_at'),         # e.g., "6 days ago"
                    "created_at": row.get('ingestion_timestamp'), # e.g., "2026-01-22..."
                    "schedule_type": row.get('schedule_type')  # e.g., "Full-time"
                }

                data_tuples.append((
                    str(row['job_id']),             # PK
                    row['title'],                   # Display
                    row['category'],                # Filter
                    row.get('location', 'N/A'),     # Filter
                    embeddings[idx],                # Vector
                    Json(meta_payload),             # JSONB Data
                    CURR_MONTH                      # Version
                ))
        
            insert_query = """
                INSERT INTO job_embeddings 
                (job_id, job_title, category, location, description_embedding, metadata, ingestion_month)
                VALUES %s
                ON CONFLICT (job_id) DO NOTHING;
            """
            
            with db.connect().cursor() as cur:
                execute_values(cur, insert_query, data_tuples)
            
            # 9. FINALIZATION
            logger.info(f"✅ Ingested {new_records_count} new records into Postgres.")
            (csv_path.parent / f"{CURR_MONTH}.vector_done").touch()

        except Exception as e:
            logger.error(f"❌ Ingestion failed: {e}")
            raise e
        finally:
            db.close()

if __name__ == "__main__":
    main()
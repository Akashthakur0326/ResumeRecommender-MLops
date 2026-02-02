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

CURR_MONTH = str(params['ingest']['current_month'])
BATCH_SIZE = params['ml_models']['vector_encoding']['batch_size']
INSERT_BATCH_SIZE = 100  # 🆕 Limit rows per insert query to prevent timeouts

logger = setup_logger(BASE_DIR / "logs" / "vector_db" / f"{CURR_MONTH}.log")

def prepare_context_text(df: pd.DataFrame) -> list:
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
            logger.error(f"❌ Final CSV for {CURR_MONTH} not found at {csv_path}")
            sys.exit(1)
        
        df = pd.read_csv(csv_path)
        
        # 5. Pre-Encoding Filter
        db = PostgresClient()
        
        try:
            with db.connect().cursor() as cur:
                cur.execute(
                    "SELECT job_id FROM job_embeddings WHERE ingestion_month = %s",
                    (CURR_MONTH,)
                )
                existing_ids = {str(row[0]) for row in cur.fetchall()}
        finally:
            # 🚨 FIX 1: CLOSE CONNECTION NOW. 
            # We are about to do heavy CPU work (Encoding) which takes minutes.
            # Keeping the DB connection open causes an "Idle Timeout".
            db.close()

        df_new = df[~df['job_id'].astype(str).isin(existing_ids)]
        new_records_count = len(df_new)

        mlflow.log_param("ingestion_month", CURR_MONTH)
        mlflow.log_param("new_jobs_detected", new_records_count)

        if df_new.empty:
            logger.info(f"✅ Batch {CURR_MONTH} is already synchronized.")
            (csv_path.parent / f"{CURR_MONTH}.vector_done").touch()
            return

        # 6. TRANSFORM (Heavy CPU Work - No DB Connection Active)
        logger.info(f"⏳ Encoding {new_records_count} records (this may take a while)...")
        encoder = SemanticEncoder() 
        text_blobs = prepare_context_text(df_new)
        
        enc_start = time.time()
        embeddings = encoder.encode_batch(text_blobs, batch_size=BATCH_SIZE) 
        mlflow.log_metric("encoding_duration_sec", time.time() - enc_start)

        # 7. LOAD (Re-connect Freshly)
        try:
            # 🚨 FIX 2: Re-instantiate client to force a fresh connection
            db = PostgresClient() 
            
            data_tuples = []
            for idx, (original_i, row) in enumerate(df_new.iterrows()):
                meta_payload = {
                    "company": row.get('company_name'),
                    "salary": row.get('salary'),
                    "link": row.get('apply_link') or row.get('job_link'),
                    "source": row.get('data_source'),
                    "posted_at": row.get('posted_at'),       
                    "created_at": row.get('ingestion_timestamp'), 
                    "schedule_type": row.get('schedule_type')  
                }

                data_tuples.append((
                    str(row['job_id']),             
                    row['title'],                   
                    row['category'],                
                    row.get('location', 'N/A'),     
                    embeddings[idx],                
                    Json(meta_payload),             
                    CURR_MONTH                      
                ))
        
            insert_query = """
                INSERT INTO job_embeddings 
                (job_id, job_title, category, location, description_embedding, metadata, ingestion_month)
                VALUES %s
                ON CONFLICT (job_id) DO NOTHING;
            """
            
            # 🚨 FIX 3: Batch Insertion to prevent Packet Size errors
            with db.connect().cursor() as cur:
                total_batches = (len(data_tuples) // INSERT_BATCH_SIZE) + 1
                for i in range(0, len(data_tuples), INSERT_BATCH_SIZE):
                    batch = data_tuples[i:i + INSERT_BATCH_SIZE]
                    execute_values(cur, insert_query, batch)
                    logger.info(f"   Saved batch {i//INSERT_BATCH_SIZE + 1}/{total_batches}")
            
            logger.info(f"✅ Ingested {new_records_count} new records into Postgres.")
            (csv_path.parent / f"{CURR_MONTH}.vector_done").touch()

        except Exception as e:
            logger.error(f"❌ Ingestion failed: {e}")
            raise e
        finally:
            db.close()

if __name__ == "__main__":
    main()
import mlflow
import yaml
import pandas as pd
import time
from psycopg2.extras import execute_values, Json
from pathlib import Path
import sys

# 1. PATH MANAGEMENT
# Resolve the project root so we can import internal modules from anywhere
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from src.vector_db.client import PostgresClient
from src.vector_db.encoder import SemanticEncoder
from utils.paths import get_final_data_path, PARAMS_PATH, BASE_DIR
from utils.logger import setup_logger

# 2. CONFIGURATION LOADING
# Fetch month and limits from central params.yaml
with open(PARAMS_PATH) as f:
    params = yaml.safe_load(f)

CURR_MONTH = params['ingest']['current_month']
logger = setup_logger(BASE_DIR / "logs" / "vector_db" / f"{CURR_MONTH}.log")

def prepare_context_text(df: pd.DataFrame) -> list:
    """
    Combines fields to maximize semantic signal for the embedding model.
    Truncates to 2000 chars to fit within transformer token limits.
    """
    return (
        "Job Title: " + df['title'].astype(str) + 
        " | Description: " + df['description'].astype(str).str[:2000]
    ).tolist()

def main():
    # 3. MLFLOW TRACKING SETUP
    # Group all ingestion runs under one experiment for performance monitoring
    mlflow.set_experiment("Job_Vector_Ingestion")

    with mlflow.start_run(run_name=f"Ingest_{CURR_MONTH}"):
        start_time = time.time()
        
        # 4. EXTRACTION: Load data from the DVC-labeled CSV
        csv_path = get_final_data_path(CURR_MONTH)
        if not csv_path.exists():
            logger.error(f"❌ Final CSV for {CURR_MONTH} not found. Check pipeline stages.")
            return
        
        df = pd.read_csv(csv_path)
        total_records = len(df)

        # 5. Pre-Encoding Filter
        # Query the DB to find IDs we already have to avoid the 'GPU Tax'
        db = PostgresClient()
        with db.connect().cursor() as cur:
            cur.execute(
                "SELECT job_id FROM job_embeddings WHERE ingestion_month = %s",
                (CURR_MONTH,)
            )
            # Store as set for O(1) lookup speed
            existing_ids = {str(row[0]) for row in cur.fetchall()}

        # Filter out jobs that are already vectorized
        df_new = df[~df['job_id'].astype(str).isin(existing_ids)]
        new_records_count = len(df_new)

        # 6. AUDIT: Log parameters to MLflow
        mlflow.log_param("ingestion_month", CURR_MONTH)
        mlflow.log_param("csv_total_rows", total_records)
        mlflow.log_param("new_jobs_detected", new_records_count)
        mlflow.log_param("model", "all-mpnet-base-v2")

        # Early exit if there is nothing new to process
        if df_new.empty:
            logger.info(f"✅ month {CURR_MONTH} is already fully synchronized. Skipping.")
            mlflow.log_metric("ingested_count", 0)
            (csv_path.parent / f"{CURR_MONTH}.vector_done").touch()
            return

        # 7. TRANSFORM: Semantic Vectorization
        # This is the most compute-heavy step
        encoder = SemanticEncoder() 
        text_blobs = prepare_context_text(df_new)
        
        enc_start = time.time()
        embeddings = encoder.encode_batch(text_blobs, batch_size=32)
        mlflow.log_metric("encoding_duration_sec", time.time() - enc_start)

        # 8. LOAD: Database Insertion
        try:
            data_tuples = []
            for i, row in df_new.iterrows():
                # Prepare metadata as a searchable JSONB blob
                meta_payload = {
                    "company": row.get('company_name'),
                    "salary": row.get('salary'),
                    "link": row.get('apply_link') or row.get('job_link'),
                    "source": row.get('data_source')
                }

                data_tuples.append((
                    str(row['job_id']),         # PK
                    row['title'],               # Display
                    row['category'],            # Filter
                    row.get('location', 'N/A'), # Filter
                    embeddings[i],              # 768-dim Vector
                    Json(meta_payload),         # JSONB Data
                    CURR_MONTH                  # Version
                ))

            # Strictly follow the 'No Re-embedding' rule with ON CONFLICT DO NOTHING
            insert_query = """
                INSERT INTO job_embeddings 
                (job_id, job_title, category, location, description_embedding, metadata, ingestion_month)
                VALUES %s
                ON CONFLICT (job_id) DO NOTHING;
            """
            
            with db.connect().cursor() as cur:
                execute_values(cur, insert_query, data_tuples)
            
            # 9. FINALIZATION: Log metrics and cleanup
            mlflow.log_metric("records_inserted", new_records_count)
            mlflow.log_metric("total_workflow_sec", time.time() - start_time)
            logger.info(f"✅ Ingested {new_records_count} new records into Postgres.")
            
            # Create the DVC sentinel file
            (csv_path.parent / f"{CURR_MONTH}.vector_done").touch()

        except Exception as e:
            mlflow.log_param("error_message", str(e))
            logger.error(f"❌ Ingestion failed during database write: {e}")
            raise e
        finally:
            db.close()

if __name__ == "__main__":
    main()
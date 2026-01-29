# this is a one time vector pipeline making test 
import yaml
from pathlib import Path
import sys
import time

# Add project root to path so imports work
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT_DIR))

from src.vector_db.ingest import main as run_ingestion
from src.vector_db.client import PostgresClient

def backfill():
    # 1. Setup Paths
    final_data_dir = ROOT_DIR / "data" / "final" / "serpapi"
    params_path = ROOT_DIR / "params.yaml"

    # 2. Initialize the DB Table (Since we just wiped it!)
    print("🛠️  Initializing Database Schema...")
    db = PostgresClient()
    # We create the table manually here to ensure the "Cold Start" doesn't fail
    with db.get_cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS job_embeddings (
                job_id TEXT PRIMARY KEY,
                job_title TEXT,
                category TEXT,
                location TEXT,
                description_embedding vector(768),
                metadata JSONB,
                ingestion_month TEXT
            );
        """)
    db.close()
    print("✅ Schema created.")

    # 3. Find all historical CSVs
    historical_files = list(final_data_dir.glob("*.csv"))
    if not historical_files:
        print("❌ No history found in data/final/serpapi/. Run 'dvc pull' first.")
        return

    print(f"🔄 Found {len(historical_files)} historical files to backfill.")

    # 4. Save original params to restore later
    with open(params_path, 'r') as f:
        original_params = yaml.safe_load(f)
    
    original_month = original_params['ingest']['current_month']

    try:
        # 5. The Loop
        for file_path in historical_files:
            target_month = file_path.stem # e.g., "2026-01-28"
            print(f"\n🚀 Backfilling for date: {target_month}")

            # Update params.yaml
            with open(params_path, 'r') as f:
                current_params = yaml.safe_load(f)
            
            current_params['ingest']['current_month'] = target_month
            
            with open(params_path, 'w') as f:
                yaml.safe_dump(current_params, f)

            # Run Ingestion
            run_ingestion()
            
    except Exception as e:
        print(f"❌ Critical Backfill Error: {e}")

    finally:
        # 6. RESTORE original params no matter what happens
        print(f"\n🧹 Restoring params.yaml to {original_month}...")
        with open(params_path, 'r') as f:
            final_params = yaml.safe_load(f)
        
        final_params['ingest']['current_month'] = original_month
        
        with open(params_path, 'w') as f:
            yaml.safe_dump(final_params, f)
        
        print("✨ Backfill Complete. System Restored.")

if __name__ == "__main__":
    backfill()
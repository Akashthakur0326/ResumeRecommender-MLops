import pandas as pd
import yaml
import sys
from pathlib import Path
from sqlalchemy import text
from datetime import datetime

# 1. Setup Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PROJECT_ROOT))

from utils.db import get_db_engine
from utils.paths import JOBS_CSV_PATH, LOCATIONS_YAML_PATH

def seed_database():
    engine = get_db_engine()
    
    print("🚀 Starting Database Seed...")
    
    # --- 1. Load Data from Files ---
    if not JOBS_CSV_PATH.exists():
        print(f"❌ Error: {JOBS_CSV_PATH} not found.")
        sys.exit(1)
        
    print(f"📖 Reading {JOBS_CSV_PATH}...")
    jobs_df = pd.read_csv(JOBS_CSV_PATH)

    if not LOCATIONS_YAML_PATH.exists():
        print(f"❌ Error: {LOCATIONS_YAML_PATH} not found.")
        sys.exit(1)

    print(f"📖 Reading {LOCATIONS_YAML_PATH}...")
    with open(LOCATIONS_YAML_PATH, "r", encoding="utf-8") as f:
        # Your YAML structure:
        # locations:
        #   - Bengaluru, India
        #   - ...
        data = yaml.safe_load(f)
        locations_list = data.get("locations", [])
        
    if not locations_list:
        print("⚠️ Warning: No locations found in YAML file.")

    # --- 2. Define Schema ---
    schema_sql = """
    -- Table 1: Static Job Taxonomy
    CREATE TABLE IF NOT EXISTS jobs_base (
        job_id SERIAL PRIMARY KEY,
        job_title VARCHAR(255) UNIQUE NOT NULL,
        internal_category VARCHAR(255) NOT NULL
    );

    -- Table 2: Dynamic Ingestion Policy (SCD Type 2)
    CREATE TABLE IF NOT EXISTS ingestion_policy (
        policy_id SERIAL PRIMARY KEY,
        internal_category VARCHAR(255) NOT NULL,
        priority VARCHAR(50) NOT NULL,
        effective_from TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        effective_to TIMESTAMP NULL,
        reason VARCHAR(255)
    );

    -- Table 3: Active Locations
    CREATE TABLE IF NOT EXISTS locations_base (
        loc_id SERIAL PRIMARY KEY,
        location_name VARCHAR(255) UNIQUE NOT NULL,
        is_active BOOLEAN DEFAULT TRUE
    );
    """
    
    with engine.connect() as conn:
        conn.execute(text(schema_sql))
        conn.commit()
        print("✅ Schema created (if not existed).")

        # --- 3. Populate Jobs (Taxonomy) ---
        jobs_clean = jobs_df[['job_title', 'internal_category']].drop_duplicates()
        job_count = 0
        for _, row in jobs_clean.iterrows():
            insert_job = text("""
                INSERT INTO jobs_base (job_title, internal_category)
                VALUES (:title, :cat)
                ON CONFLICT (job_title) DO NOTHING;
            """)
            conn.execute(insert_job, {"title": row['job_title'], "cat": row['internal_category']})
            job_count += 1
        
        print(f"✅ Populated jobs_base with {job_count} roles.")

        # --- 4. Populate Locations ---
        loc_count = 0
        for loc in locations_list:
            insert_loc = text("""
                INSERT INTO locations_base (location_name)
                VALUES (:loc)
                ON CONFLICT (location_name) DO NOTHING;
            """)
            conn.execute(insert_loc, {"loc": loc})
            loc_count += 1
        
        print(f"✅ Populated locations_base with {loc_count} cities.")

        # --- 5. Populate Initial Policy ---
        policy_data = jobs_df[['internal_category', 'priority_tier']].drop_duplicates('internal_category')
        policy_count = 0
        
        for _, row in policy_data.iterrows():
            # Check if active policy exists
            check_sql = text("""
                SELECT 1 FROM ingestion_policy 
                WHERE internal_category = :cat AND effective_to IS NULL
            """)
            result = conn.execute(check_sql, {"cat": row['internal_category']}).fetchone()
            
            if not result:
                insert_policy = text("""
                    INSERT INTO ingestion_policy (internal_category, priority, effective_from, reason)
                    VALUES (:cat, :prio, :now, 'Initial Seed from CSV')
                """)
                conn.execute(insert_policy, {
                    "cat": row['internal_category'], 
                    "prio": row['priority_tier'],
                    "now": datetime.now()
                })
                policy_count += 1
        
        conn.commit()
        print(f"✅ Seeded {policy_count} ingestion policies.")

if __name__ == "__main__":
    seed_database()
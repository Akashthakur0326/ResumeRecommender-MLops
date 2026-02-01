import sys
import pandas as pd
from pathlib import Path
from sqlalchemy import text
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PROJECT_ROOT))

from utils.db import get_db_engine

# --- THRESHOLDS ---
MIN_THRESHOLD_PCT = 2.0  
MAX_THRESHOLD_PCT = 15.0 

def manage_drift():
    engine = get_db_engine()
    print("🧠 Analyzing Data Drift...")

    # FIX: Explicitly commit/rollback using the connection directly
    with engine.connect() as conn:
        # 1. Get Current Distribution from Vector Store
        query_dist = text("""
            SELECT category, COUNT(*) as count
            FROM job_embeddings
            GROUP BY category
        """)
        df_dist = pd.read_sql(query_dist, conn)

        if df_dist.empty:
            print("⚠️ Database is empty. Keeping default policies.")
            return

        total_jobs = df_dist['count'].sum()
        print(f"📊 Total Jobs in DB: {total_jobs}")

        # 2. Calculate Percentages
        df_dist['percentage'] = (df_dist['count'] / total_jobs) * 100

        # 3. Fetch Current Active Policies
        query_policy = text("""
            SELECT internal_category, priority
            FROM ingestion_policy
            WHERE effective_to IS NULL
        """)
        current_policies = pd.read_sql(query_policy, conn)
        policy_map = dict(zip(current_policies['internal_category'], current_policies['priority']))

        updates_made = 0

        # 4. Evaluate Each Category
        for _, row in df_dist.iterrows():
            category = row['category']
            pct = row['percentage']
            
            # --- DECISION LOGIC ---
            if pct < MIN_THRESHOLD_PCT:
                new_priority = "High"
                reason = f"Starved: Only {pct:.2f}% (Threshold: {MIN_THRESHOLD_PCT}%)"
            elif pct > MAX_THRESHOLD_PCT:
                new_priority = "Low"
                reason = f"Saturated: {pct:.2f}% (Threshold: {MAX_THRESHOLD_PCT}%)"
            else:
                new_priority = "Medium"
                reason = f"Healthy: {pct:.2f}%"

            current_priority = policy_map.get(category, "None")
            
            if current_priority != new_priority:
                print(f"🔄 Updating {category}: {current_priority} -> {new_priority} ({reason})")
                
                try:
                    # A. Close old policy
                    close_sql = text("""
                        UPDATE ingestion_policy
                        SET effective_to = :now
                        WHERE internal_category = :cat AND effective_to IS NULL
                    """)
                    conn.execute(close_sql, {"now": datetime.now(), "cat": category})

                    # B. Insert new policy
                    insert_sql = text("""
                        INSERT INTO ingestion_policy 
                        (internal_category, priority, effective_from, reason)
                        VALUES (:cat, :prio, :now, :reason)
                    """)
                    conn.execute(insert_sql, {
                        "cat": category,
                        "prio": new_priority,
                        "now": datetime.now(),
                        "reason": reason
                    })
                    
                    # FIX: Simply commit the changes on the connection
                    conn.commit()
                    updates_made += 1
                except Exception as e:
                    # Rollback if anything goes wrong for this specific update
                    conn.rollback()
                    print(f"❌ Failed to update {category}: {e}")
            else:
                pass

    print(f" Drift Management Complete. Policies updated: {updates_made}")

if __name__ == "__main__":
    manage_drift()
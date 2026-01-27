import sys
from pathlib import Path

# Path Setup
ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))

from src.vector_db.client import PostgresClient

def check_alignment():
    db = PostgresClient()
    conn = db.connect()
    
    with conn.cursor() as cur:
        print("\n🔍 --- INTEGRITY CHECK ---")
        
        # 1. Get the new Candidate Keys (Job Titles from Definitions)
        cur.execute("SELECT job_title FROM role_definitions;")
        candidate_keys = set([r[0] for r in cur.fetchall()])
        print(f"📋 Candidate Keys (Stage 1 Output): {len(candidate_keys)} unique titles")
        
        # 2. Get the Target Buckets (Categories from Job Embeddings)
        cur.execute("SELECT DISTINCT category FROM job_embeddings;")
        target_buckets = set([r[0] for r in cur.fetchall()])
        print(f"📋 Target Buckets (Stage 2 Filters): {len(target_buckets)} unique categories")
        
        # 3. The Clash Test
        print("\n-------- MATCH REPORT --------")
        matches = candidate_keys.intersection(target_buckets)
        mismatches = candidate_keys - target_buckets
        
        print(f"✅ Safe Matches: {len(matches)}")
        print(f"❌ Broken Links: {len(mismatches)}")
        
        if mismatches:
            print("\n⚠️ The following Titles will return 0 jobs if used as filters:")
            print(list(mismatches)[:10])
            print("... (and others)")
            
            print("\n💡 DIAGNOSIS:")
            print("Using 'job_title' ensures uniqueness, BUT it breaks the lookup.")
            print("You should stick to 'internal_category' (which we fixed with SQL)")
            print("and rely on the DELETE command (Pruning) to solve the duplicates.")
            
    conn.close()

if __name__ == "__main__":
    check_alignment()
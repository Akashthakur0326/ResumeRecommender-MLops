import sys
import os
import json
import psycopg2
from pathlib import Path
from dotenv import load_dotenv

# 1. SETUP PATHS so Python finds your modules
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

# Import your Service (Ensure this path matches where you saved score_resume.py)
try:
    from app.services.score_resume import ResumeScorerService
except ImportError:
    # Fallback if you haven't moved the file yet, assumes it's in the same folder for testing
    print("⚠️ Could not import from app.services. Attempting local import...")
    try:
        from score_resume import ResumeScorerService
    except ImportError:
        print("❌ CRITICAL: Could not find 'ResumeScorerService'. Check your file structure.")
        sys.exit(1)

# Load AWS Credentials
load_dotenv()

def check_db_counts():
    """Step 1: Verify AWS RDS has data"""
    print("\n📊 --- STEP 1: CHECKING DATABASE COUNTS ---")
    try:
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST"),
            database=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            port=os.getenv("DB_PORT")
        )
        cur = conn.cursor()
        
        # Check Role Definitions (Anchors)
        cur.execute("SELECT count(*) FROM role_definitions;")
        role_count = cur.fetchone()[0]
        print(f"✅ Role Definitions (Anchors): {role_count}")

        # Check Job Embeddings (Scraped Data)
        cur.execute("SELECT count(*) FROM job_embeddings;")
        job_count = cur.fetchone()[0]
        print(f"✅ Job Embeddings (Scraped):   {job_count}")

        cur.close()
        conn.close()
        
        if job_count == 0:
            print("⚠️ WARNING: Job table is empty. 'get_recommendations' will return empty lists.")
            
    except Exception as e:
        print(f"❌ DB Connection Failed: {e}")
        sys.exit(1)

def test_scorer_service():
    """Step 2: Simulate a real API request"""
    print("\n🧠 --- STEP 2: TESTING RECOMMENDATION ENGINE ---")
    
    # A "Strong" Dummy Resume to ensure we hit the 50% match threshold
    dummy_resume = """
    I am a Senior Software Engineer with 5 years of experience in Python, AWS, and Machine Learning.
    I have built REST APIs using FastAPI and deployed them on Docker and Kubernetes.
    I am proficient in SQL, PostgreSQL, and CI/CD pipelines.
    Looking for backend development or MLOps roles.
    """
    
    print(f"📄 Input Resume Snippet: {dummy_resume.strip()[:100]}...")
    
    try:
        # Initialize the Service (This triggers DB connection & Encoder load)
        service = ResumeScorerService()
        
        # Run the Logic
        response = service.get_recommendations(dummy_resume)
        
        # Check specific parts of the response
        if response.get("status") == "success":
            results = response.get("results", [])
            print(f"✅ Success! Found {len(results)} Matching Categories.")
            
            for i, res in enumerate(results):
                cat = res['category']
                score = res['category_match_score']
                jobs = res['recommended_jobs']
                print(f"\n  🔹 Category {i+1}: {cat} (Score: {score})")
                print(f"     Found {len(jobs)} Job Recommendations:")
                
                for job in jobs:
                    print(f"       - [{job['match_confidence']}%] {job['title']} @ {job['company']}")
                    
        else:
            print("❌ Service returned failure status.")
            print(response)

    except Exception as e:
        print(f"❌ Service Logic Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_db_counts()
    test_scorer_service()
#checks if db is reachable before going for the cron job 

import sys
from pathlib import Path
from sqlalchemy import text

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PROJECT_ROOT))

from utils.db import get_db_engine

def check_connection():
    print("🔌 Testing RDS Connection...")
    try:
        engine = get_db_engine()
        with engine.connect() as conn:
            # Simple lightweight query
            conn.execute(text("SELECT 1"))
        print("✅ Connection Successful. RDS is ready.")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Connection Failed: {e}")
        # Exit with error code to stop GitHub Action
        sys.exit(1)

if __name__ == "__main__":
    check_connection()
import os
import psycopg2
import sys
from pathlib import Path
from dotenv import load_dotenv

# 1. Path Management
# __file__ is: .../ResumeRecommenderMLops/src/vector_db/client.py
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

# Now this import will work reliably
from utils.paths import BASE_DIR

# Load env vars using the resolved BASE_DIR
load_dotenv(BASE_DIR / ".env")

class PostgresClient:
    def __init__(self):
        self.host = os.getenv("DB_HOST", "localhost")
        self.db_name = os.getenv("DB_NAME", "postgres")
        self.user = os.getenv("DB_USER", "postgres")
        self.password = os.getenv("DB_PASSWORD", "postgres123")
        self.conn = None

    def connect(self):
        if self.conn is None or self.conn.closed:
            try:
                self.conn = psycopg2.connect(
                    host=self.host,
                    database=self.db_name,
                    user=self.user,
                    password=self.password
                )
                # 🔥 FIX: Source of truth for transaction management
                self.conn.autocommit = True 
            except Exception as e:
                raise ConnectionError(f"Failed to connect to DB: {e}")
        return self.conn
    
    def close(self):
        """Safely closes connection."""
        if self.conn and not self.conn.closed:
            self.conn.close()

    def get_cursor(self):
        """Returns a cursor from the active connection."""
        return self.connect().cursor()
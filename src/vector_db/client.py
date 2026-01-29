import os
import psycopg2
import sys
import time  
from pathlib import Path
from dotenv import load_dotenv

# 1. Path Management
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from utils.paths import BASE_DIR

load_dotenv(BASE_DIR / ".env")

class PostgresClient:
    def __init__(self):
        self.host = os.getenv("DB_HOST", "localhost")
        self.db_name = os.getenv("DB_NAME", "postgres")
        self.user = os.getenv("DB_USER", "postgres")
        self.password = os.getenv("DB_PASSWORD", "postgres123")
        self.conn = None

    def connect(self):
        """
        Connects to the database with a retry mechanism to handle 
        Docker startup delays (The 'Race Condition').
        """
        if self.conn is None or self.conn.closed:
            # We try 5 times, waiting 2 seconds between each try.
            # Total wait time = 10 seconds.
            max_retries = 5
            retry_delay = 2 
            
            for attempt in range(max_retries):
                try:
                    self.conn = psycopg2.connect(
                        host=self.host,
                        database=self.db_name,
                        user=self.user,
                        password=self.password,
                        sslmode=os.getenv("DB_SSL_MODE", "prefer")
                    )
                    self.conn.autocommit = True
                    # If we get here, connection was successful
                    return self.conn
                
                except psycopg2.OperationalError as e:
                    # OperationalError usually means "Can't connect to server"
                    if attempt < max_retries - 1:
                        print(f"⏳ Database not ready yet... retrying in {retry_delay}s ({attempt+1}/{max_retries})")
                        time.sleep(retry_delay)
                    else:
                        # If it's the last attempt, crash loudly
                        print("❌ Database connection failed after multiple retries.")
                        raise ConnectionError(f"Failed to connect to DB after {max_retries} attempts: {e}")
                        
        return self.conn
    
    def close(self):
        if self.conn and not self.conn.closed:
            self.conn.close()

    def get_cursor(self):
        return self.connect().cursor()
# utils/db.py
import os
import sys
from sqlalchemy import create_engine
from dotenv import load_dotenv
from pathlib import Path

# Load env from root
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

def get_db_engine():
    """
    Returns a SQLAlchemy engine for the RDS database.
    Ensures secure connection using env vars.
    """
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    host = os.getenv("DB_HOST")
    port = os.getenv("DB_PORT", "5432")
    dbname = os.getenv("DB_NAME")

    if not all([user, password, host, dbname]):
        raise EnvironmentError("❌ Missing DB credentials in .env file")

    # Construct connection string: postgresql://user:password@host:port/dbname
    db_url = f"postgresql://{user}:{password}@{host}:{port}/{dbname}"
    
    return create_engine(db_url)
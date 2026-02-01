# data_ingestion/jd_ingestion/serp_api/priority_scheduler.py
import pandas as pd
from typing import List, Dict
import sys
from pathlib import Path
from sqlalchemy import text

# ... (Path setup remains the same) ...
project_root = Path(__file__).resolve().parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from utils.db import get_db_engine

def load_jobs_with_priority() -> List[Dict]:
    """ Fetch active jobs and their current policy priority """
    engine = get_db_engine()
    query = """
    SELECT j.job_title, p.priority
    FROM jobs_base j
    JOIN ingestion_policy p ON j.internal_category = p.internal_category
    WHERE p.effective_to IS NULL;
    """
    try:
        with engine.connect() as conn:
            df = pd.read_sql(text(query), conn)
        return df.to_dict(orient="records") if not df.empty else []
    except Exception as e:
        print(f"❌ DB Error (Jobs): {e}")
        raise e

def load_active_locations() -> List[str]:
    """ Fetch all active locations from DB """
    engine = get_db_engine()
    query = "SELECT location_name FROM locations_base WHERE is_active = TRUE;"
    
    try:
        with engine.connect() as conn:
            result = conn.execute(text(query)).fetchall()
        # Result is list of tuples like [('New York',), ('London',)]
        return [row[0] for row in result]
    except Exception as e:
        print(f"❌ DB Error (Locations): {e}")
        raise e
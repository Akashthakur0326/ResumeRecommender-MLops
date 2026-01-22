import pandas as pd
from typing import List, Dict
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent.parent

# 2. Add the Project Root to Python's search path
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from utils.paths import JOBS_CSV_PATH


def load_jobs_with_priority() -> List[Dict]:
    """
    Returns:
    [
      {
        "job_title": "...",
        "priority": "High" | "Medium" | "Low"
      }
    ]
    """
    df = pd.read_csv(JOBS_CSV_PATH)

    required_cols = {"job_title", "priority_tier"}
    if not required_cols.issubset(df.columns):
        raise ValueError(f"jobs.csv must contain {required_cols}")

    jobs = []
    for _, row in df.iterrows():
        jobs.append({
            "job_title": row["job_title"],
            "priority": row["priority_tier"]
        })

    return jobs
    
from pathlib import Path

# __file__ is: .../ResumeRecommenderMLops/utils/paths.py
# .parent is: .../ResumeRecommenderMLops/utils/
# .parent.parent is: .../ResumeRecommenderMLops/ (The Root)
BASE_DIR = Path(__file__).resolve().parent.parent

#BASE_DIR = Path(r"C:\Users\Admin\Desktop\ResumeRecommenderMLops")

# Now these paths will correctly point to your root-level folders
RAW_SERPAPI_DIR = BASE_DIR / "data" / "raw" / "serpapi"
PROCESSED_SERPAPI_DIR = BASE_DIR / "data" / "processed" / "serpapi"
LOG_DIR = BASE_DIR / "logs" / "serpapi"
FINAL_DIR = BASE_DIR / "data" / "final"/ "serpapi"

JOBS_CSV_PATH = BASE_DIR / "data" / "constants" / "jobs.csv"
LOCATIONS_YAML_PATH = BASE_DIR / "data" / "constants" / "locations.yaml"

PARAMS_PATH = BASE_DIR / "params.yaml"

def get_raw_run_dir(run_month: str) -> Path:
    """
    this is a helper fn which helps when we run a cron job to make folders acc to date of the month that job had been run on 
    """
    return RAW_SERPAPI_DIR / run_month 

def get_processed_data_path(run_month: str) -> Path:
    
    return PROCESSED_SERPAPI_DIR / f"{run_month}.csv" 


def get_final_data_path(run_month: str) -> Path:
    
    return FINAL_DIR / f"{run_month}.csv" 

def get_log_path(run_month: str) -> Path:
    """
    Creates a per-run log file
    """
    path = LOG_DIR / f"{run_month}.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path
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

KB_JSON_PATH = BASE_DIR / "data" / "constants" / "KB" / "detailed_job_descriptions.json"


DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"
MODEL_DIR = BASE_DIR / "models"

# Data Paths
DATA_DIR = BASE_DIR / "data"
CONSTANTS_DIR = DATA_DIR / "constants"
SKILLS_CSV_PATH = CONSTANTS_DIR / "skills.csv"

# Artifacts (DVC Tracked)
ARTIFACTS_DIR = BASE_DIR / "artifacts"
NLTK_DATA_PATH = ARTIFACTS_DIR / "nltk_data"

#Helper to ensure a directory exists before returning it
def _ensure(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path

def get_raw_run_dir(run_month: str) -> Path:
    """
    this is a helper fn which helps when we run a cron job to make folders acc to date of the month that job had been run on 
    """
    return _ensure(DATA_DIR / "raw" / "serpapi" / run_month) 

def get_processed_data_path(run_month: str) -> Path:
    
    _ensure(DATA_DIR / "processed" / "serpapi")
    return DATA_DIR / "processed" / "serpapi" / f"{run_month}.csv" 


def get_final_data_path(run_month: str) -> Path:
    # Ensure the PARENT directory exists (data/final/serpapi)
    # Assuming FINAL_DIR points to data/final/serpapi
    _ensure(FINAL_DIR) 
    return FINAL_DIR / f"{run_month}.csv" 

def get_log_path(run_month: str) -> Path:
    """
    Creates a per-run log file
    """
    _ensure(LOG_DIR / "serpapi")
    return LOG_DIR / "serpapi" / f"{run_month}.log"

def get_model_path(model_name: str) -> Path:
    """
    Points to the DVC-tracked model folder
    """
    return MODEL_DIR / model_name
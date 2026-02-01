import json
import yaml
import os
import mlflow
import sys
from pathlib import Path
from dotenv import load_dotenv

# 1. Calculate the Project Root
project_root = Path(__file__).resolve().parent.parent.parent.parent

# 2. Add the Project Root to Python's search path
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

# Now import local modules
from utils.dates import current_run_date
from utils.paths import get_raw_run_dir, get_log_path, PARAMS_PATH
from utils.logger import setup_logger
from priority_scheduler import load_jobs_with_priority, load_active_locations
from serpapi_client import fetch_jobs

def load_params():
    """Safety check to ensure params exist"""
    if not PARAMS_PATH.exists():
        raise FileNotFoundError(f"params.yaml missing at {PARAMS_PATH}")
    with open(PARAMS_PATH, "r") as f:
        return yaml.safe_load(f)
    
def slice_locations(locations: list, priority: str) -> list:
    L = len(locations)
    if L == 0: return [] 
    
    if priority == "High":
        return locations
    elif priority == "Medium":
        return locations[: max(1, int(0.9 * L))] 
    elif priority == "Low":
        return locations[: max(1, int(0.75 * L))]
    else:
        return locations

def safe_filename(text: str) -> str:
    return (
        text.replace(" ", "_")
            .replace(",", "")
            .replace("/", "_")
            .replace("\\", "_")
    )

def main():
    load_dotenv() 

    params = load_params()
    MAX_API_CALLS = params["serpapi_ingestion"]["max_api_calls"]

    tracking_uri = os.getenv("MLFLOW_TRACKING_URI")
    if not tracking_uri:
        raise EnvironmentError("MLFLOW_TRACKING_URI not set")

    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment("serpapi_ingestion")

    run_month = current_run_date()
    raw_dir = get_raw_run_dir(run_month)
    raw_dir.mkdir(parents=True, exist_ok=True)

    logger = setup_logger(
        log_path=get_log_path(run_month),
        logger_name="serpapi_ingestion"
    )

    logger.info(f"Starting SerpAPI ingestion for {run_month}")

    # --- DB DATA FETCHING ---
    try:
        all_locations = load_active_locations()
        logger.info(f"Loaded {len(all_locations)} locations from RDS.")
        
        # FIX: Removed the redundant double-call to load_jobs_with_priority
        jobs = load_jobs_with_priority()
        if not jobs:
            logger.error("No active jobs found in DB. Check ingestion_policy.")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Failed to connect to RDS: {e}")
        sys.exit(1)

    api_calls = 0
    total_jobs = 0
    stop_reason = "completed"
    should_stop = False

    with mlflow.start_run(run_name=f"serpapi_{run_month}"):
        for job in jobs:
            if should_stop: break

            job_title = job["job_title"]
            priority = job["priority"]

            # Dynamically slice based on DB priority
            locations = slice_locations(all_locations, priority)

            logger.info(
                f"Job='{job_title}' | Priority={priority} | Locations={len(locations)}"
            )

            for location in locations:
                if should_stop: break
                page_token = None

                while True:
                    if api_calls >= MAX_API_CALLS:
                        stop_reason = "api_limit_reached"
                        logger.warning("API call limit reached")
                        should_stop = True
                        break

                    try:
                        response = fetch_jobs(job_title, location, page_token)
                        api_calls += 1
                        logger.info(f"API Progress: {api_calls}/{MAX_API_CALLS} | {job_title} @ {location}")
                    
                    except RuntimeError as e:
                        msg = str(e).lower()
                        if "run out of searches" in msg or "quota" in msg:
                            logger.warning("Quota reached! Stopping entire ingestion.")
                            stop_reason = "quota_exceeded"
                            should_stop = True
                        elif "429" in msg or "too many requests" in msg:
                            logger.error("SerpAPI rate limit hit")
                            stop_reason = "serpapi_rate_limit"
                            should_stop = True
                        else:
                            logger.error(f"Non-fatal SerpAPI error: {e}")
                        break
                    
                    if should_stop: break

                    # --- SAVE RAW JSON ---
                    filename = f"{safe_filename(job_title)}_{safe_filename(location)}_p{api_calls}.json"
                    with open(raw_dir / filename, "w", encoding="utf-8") as f:
                        json.dump(response, f, ensure_ascii=False, indent=2)

                    batch = response.get("jobs_results", [])
                    total_jobs += len(batch)
                    logger.info(f"Saved {len(batch)} jobs to {filename}")

                    page_token = response.get("next_page_token")
                    if not page_token:
                        break

                if should_stop: break
            if should_stop: break

        mlflow.log_param("run_month", run_month)
        mlflow.log_param("stop_reason", stop_reason)
        mlflow.log_metric("api_calls", api_calls)
        mlflow.log_metric("jobs_fetched", total_jobs)

    logger.info("Ingestion finished successfully.")

if __name__ == "__main__":
    main()
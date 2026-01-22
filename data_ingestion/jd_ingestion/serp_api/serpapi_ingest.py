import json
import yaml
import os
import mlflow

import sys
from pathlib import Path

# 1. Calculate the Project Root (4 levels up from this script)
# Script is at: Root/data_ingestion/jd_ingestion/serp_api/serpapi_ingest.py
project_root = Path(__file__).resolve().parent.parent.parent.parent

# 2. Add the Project Root to Python's search path
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

# NOW you can import your utils

from dotenv import load_dotenv
from utils.dates import current_run_month
from utils.paths import get_raw_run_dir, get_log_path, LOCATIONS_YAML_PATH, PARAMS_PATH
from utils.logger import setup_logger
from priority_scheduler import load_jobs_with_priority
from serpapi_client import fetch_jobs


#MAX_API_CALLS = 260
api_calls_made = 0
page_number = 1


def load_params():
    """Safety check to ensure params exist"""
    if not PARAMS_PATH.exists():
        raise FileNotFoundError(f"params.yaml missing at {PARAMS_PATH}")
    
    with open(PARAMS_PATH, "r") as f:
        return yaml.safe_load(f)
    
def slice_locations(locations: list, priority: str) -> list:
    L = len(locations)
    if L == 0: return []  # Safety check
    
    if priority == "High":
        return locations
    elif priority == "Medium":
        # Fix: Ensure at least 1 location is checked
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
    load_dotenv()  # ONLY here

    params = load_params()
    MAX_API_CALLS = params["ingestion"]["max_api_calls"]

    tracking_uri = os.getenv("MLFLOW_TRACKING_URI")
    if not tracking_uri:
        raise EnvironmentError("MLFLOW_TRACKING_URI not set")

    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment("serpapi_ingestion")

    run_month = current_run_month()
    raw_dir = get_raw_run_dir(run_month)
    raw_dir.mkdir(parents=True, exist_ok=True)

    logger = setup_logger(
        log_path=get_log_path(run_month),
        logger_name="serpapi_ingestion"
    )

    logger.info(f"Starting SerpAPI ingestion for {run_month}")

    with open(LOCATIONS_YAML_PATH, "r") as f:
        all_locations = yaml.safe_load(f)["locations"]

    jobs = load_jobs_with_priority()

    api_calls = 0
    total_jobs = 0
    stop_reason = "completed"
    should_stop = False

    with mlflow.start_run(run_name=f"serpapi_{run_month}"):

        for job in jobs:
            job_title = job["job_title"]
            priority = job["priority"]

            locations = slice_locations(all_locations, priority)

            logger.info(
                f"Job='{job_title}' | Priority={priority} | Locations={len(locations)}"
            )
            

            for location in locations:
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
                        if "429" in msg or "too many requests" in msg:
                            stop_reason = "serpapi_rate_limit"
                            should_stop = True
                            logger.error("SerpAPI rate limit hit")
                        else:
                            logger.exception("Non-fatal SerpAPI error")
                        break

                    filename = (
                            f"{safe_filename(job_title)}_"
                            f"{safe_filename(location)}_"
                            f"page{api_calls}.json"
                        )


                    with open(raw_dir / filename, "w", encoding="utf-8") as f:
                        json.dump(response, f, ensure_ascii=False, indent=2)

                    batch = response.get("jobs_results", [])
                    total_jobs += len(batch)

                    logger.info(f"Saved {len(batch)} jobs to {filename}")

                    page_token = response.get("next_page_token")
                    if not page_token:
                        break

                if should_stop:
                    break
            if should_stop:
                break

        mlflow.log_param("run_month", run_month)
        mlflow.log_param("stop_reason", stop_reason)
        mlflow.log_metric("api_calls", api_calls)
        mlflow.log_metric("jobs_fetched", total_jobs)

    logger.info("Ingestion finished")


if __name__ == "__main__":
    main()

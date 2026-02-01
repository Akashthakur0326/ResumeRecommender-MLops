import sys
import json
import pandas as pd
import yaml  # Added yaml import
from pathlib import Path
import re
from datetime import datetime

import os
import mlflow

from dotenv import load_dotenv

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from utils.logger import setup_logger
from utils.paths import get_raw_run_dir, get_processed_data_path, PARAMS_PATH # Added PARAMS_PATH
# Removed 'current_run_date' import to prevent date drift

# --- CONFIGURATION ---
REQUIRED_SCHEMA = [
    "job_id",
    "title",
    "company_name",
    "location",
    "description",
    "salary",
    "schedule_type",
    "posted_at",
    "search_term",
    "search_location",
    "ingestion_month",      
    "ingestion_timestamp",  
    "data_source",          
    "search_engine",
    "category",
    "job_link",             
    "apply_link"         
]

# Fail-Fast Thresholds
MIN_JOBS_THRESHOLD = 1

def load_params():
    """Load the single source of truth for the current batch ID."""
    if not PARAMS_PATH.exists():
        raise FileNotFoundError(f"params.yaml missing at {PARAMS_PATH}")
    
    with open(PARAMS_PATH, "r") as f:
        params = yaml.safe_load(f)
        # Ensure we get the string value even if yaml parses it as date object
        return str(params["ingest"]["current_month"])

def clean_text(text: str) -> str:
    """
    Advanced text normalization for ML/RAG.
    """
    if not text or not isinstance(text, str):
        return "Unknown"
    
    # 1. Replace newlines
    text = text.replace("\n", " ").replace("\r", " ")
    
    # 2. Remove common bullet points and non-ascii artifacts
    text = re.sub(r'[\u2022\u2026•·]', '', text)
    
    # 3. Collapse multiple spaces into one
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

def load_raw_json_files(raw_dir: Path, logger) -> pd.DataFrame:
    """Reads all JSON files and normalizes them into a raw DataFrame."""
    all_jobs = []
    
    if not raw_dir.exists():
        logger.error(f"Raw directory not found: {raw_dir}")
        raise FileNotFoundError(f"{raw_dir} does not exist")

    files = list(raw_dir.glob("*.json"))

    if not files:
        # Return empty list immediately if no files, main will handle exit
        return pd.DataFrame()

    for file_path in files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            # Extract Context (Search Parameters)
            search_params = data.get("search_parameters", {})
            search_term = search_params.get("q", "Unknown")
            search_loc = search_params.get("location_requested", "Unknown")
            
            metadata = data.get("search_metadata", {})
            fetch_time = metadata.get("created_at", datetime.now().isoformat())

            results = data.get("jobs_results", [])
            for job in results:
                extensions = job.get("detected_extensions", {})
                apply_options = job.get("apply_options", [])
                first_apply_link = apply_options[0].get("link") if apply_options else None

                job_entry = {
                    "job_id": job.get("job_id"),
                    "title": job.get("title"),
                    "company_name": job.get("company_name"),
                    "location": job.get("location"),
                    "description": job.get("description"),
                    "salary": extensions.get("salary"),
                    "schedule_type": extensions.get("schedule_type"),
                    "posted_at": extensions.get("posted_at"),
                    "job_link": job.get("share_link"),         
                    "apply_link": first_apply_link,             
                    "search_term": search_term,
                    "search_location": search_loc,
                    "ingestion_timestamp": fetch_time,
                }
                all_jobs.append(job_entry)
                
        except Exception as e:
            logger.warning(f"Failed to read {file_path.name}: {e}")

    return pd.DataFrame(all_jobs)

def transform_raw_data(df: pd.DataFrame, run_month: str) -> pd.DataFrame:
    """
    Pure transformation logic. 
    """
    if df.empty:
        return pd.DataFrame(columns=REQUIRED_SCHEMA)

    df = df.copy()
    
    # 2. Add Lineage Columns
    df["ingestion_month"] = run_month
    if "category" not in df.columns:
        df["category"] = None
    df["data_source"] = "serpapi"
    df["search_engine"] = "google_jobs"

    # 3. Normalization
    text_cols = ["description", "title", "company_name"]
    for col in text_cols:
        if col in df.columns:
            df[col] = df[col].apply(clean_text)

    # 4. Schema Enforcement
    for col in REQUIRED_SCHEMA:
        if col not in df.columns:
            df[col] = None

    # 5. Fail-Fast / Quality Checks
    df = df.dropna(subset=["job_id"])

    # 6. Formatting
    df = df[REQUIRED_SCHEMA]  # Enforce Order
    df["salary"] = df["salary"].fillna("Not mentioned")
    df.fillna("Unknown", inplace=True)

    # 7. Sorting
    df.sort_values(by=["job_id", "company_name"], inplace=True)
    df = df.drop_duplicates(subset=["job_id"])
    
    return df

def main():
    load_dotenv()
    mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI"))
    mlflow.set_experiment("data_processing_json_to_csv")

    # --- CRITICAL FIX: Read batch ID from params, do not generate it ---
    try:
        run_month = load_params()
    except Exception as e:
        # Fallback logger isn't setup yet, print to stderr
        print(f"❌ Failed to load params: {e}")
        sys.exit(1)

    processed_path = get_processed_data_path(run_month)
    if not str(processed_path).endswith(".csv"):
            processed_path = processed_path.with_suffix(".csv")

    log_path = processed_path.parent / "processing.log"
    
    logger = setup_logger(log_path, "data_processing")
    logger.info(f"Starting processing for batch ID: {run_month}")

    # --- DATA INTEGRITY CHECK ---
    raw_dir = get_raw_run_dir(run_month)
    
    if not raw_dir.exists():
        logger.warning(f"Raw directory {raw_dir} does not exist. Skipping.")
        sys.exit(0)

    raw_files = list(raw_dir.glob("*.json"))
    
    # 1. If there is absolutely no raw data
    if len(raw_files) == 0:
        logger.warning(f"No JSON files found in {raw_dir}. Creating empty Sentinel CSV.")
        
        empty_df = pd.DataFrame(columns=REQUIRED_SCHEMA)
        processed_path.parent.mkdir(parents=True, exist_ok=True)
        empty_df.to_csv(processed_path, index=False)
        
        with mlflow.start_run(run_name=f"process_{run_month}"):
            mlflow.log_metric("input_rows", 0)
            mlflow.log_metric("output_rows", 0)
            
        sys.exit(0)

    # 2. Check if we need to run (Idempotency)
    if processed_path.exists():
        try:
            existing_df = pd.read_csv(processed_path)
            # If CSV exists and has data, skip (unless you want to force re-runs)
            if len(existing_df) >= MIN_JOBS_THRESHOLD:
                logger.info(f"✅ Data integrity verified ({len(existing_df)} jobs). Skipping.")
                return 
        except Exception:
            logger.warning("Existing CSV is corrupt. Forcing run.")

    # --- START PROCESSING ---
    with mlflow.start_run(run_name=f"process_{run_month}"):
        # 1. Load Data
        df_raw = load_raw_json_files(raw_dir, logger)
        input_count = len(df_raw)

        # 2. Transform Data
        logger.info("Transforming and cleaning data...")
        df = transform_raw_data(df_raw, run_month)
        
        output_count = len(df)

        # 3. Save Output
        processed_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(processed_path, index=False)

        # 4. Metrics Calculation
        salary_mentioned = (df["salary"] != "Not mentioned").sum()
        salary_coverage = (salary_mentioned / output_count) * 100 if output_count > 0 else 0
        drop_rate = ((input_count - output_count) / input_count) * 100 if input_count > 0 else 0

        # Log to MLflow
        mlflow.log_metric("input_rows", input_count)
        mlflow.log_metric("output_rows", output_count)
        mlflow.log_metric("drop_rate_pct", round(drop_rate, 2))
        mlflow.log_metric("salary_coverage_pct", round(salary_coverage, 2))
        mlflow.log_artifact(str(processed_path))
        
        logger.info(f"Successfully processed {output_count} jobs.")

if __name__ == "__main__":
    main()
import sys
import json
import pandas as pd
from pathlib import Path
import re
from datetime import datetime

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from utils.logger import setup_logger
from utils.paths import get_raw_run_dir, get_processed_data_path
from utils.dates import current_run_month

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
    "llm_based_category",
    "job_link",             
    "apply_link"         
]



# Fail-Fast Thresholds
MIN_JOBS_THRESHOLD = 1

def clean_text(text: str) -> str:
    """
    Advanced text normalization for ML/RAG.
    1. Replaces newlines with spaces.
    2. Collapses multiple spaces.
    3. Removes bullet points and common unicode artifacts.
    """
    if not text or not isinstance(text, str):
        return "Unknown"
    
    # 1. Replace newlines
    text = text.replace("\n", " ").replace("\r", " ")
    
    # 2. Remove common bullet points and non-ascii artifacts
    # \u2022 (bullet), \u2013 (en dash), \u2014 (em dash)
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
        logger.error(f"No JSON files found in {raw_dir}")
        raise ValueError("Zero files to process. Pipeline stopped.")

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
                # Flatten extensions safely
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

def main():
    run_month = current_run_month()
    processed_path = get_processed_data_path(run_month)
    log_path = processed_path.parent / "processing.log"
    
    logger = setup_logger(log_path, "data_processing")
    logger.info(f"Starting processing for {run_month}")

    # 1. Load Data
    raw_dir = get_raw_run_dir(run_month)
    df = load_raw_json_files(raw_dir, logger)

    # --- FAIL-FAST CHECK 1: Volume ---
    if len(df) < MIN_JOBS_THRESHOLD:
        logger.critical(f"Extracted {len(df)} jobs. Threshold is {MIN_JOBS_THRESHOLD}.")
        raise ValueError("Insufficient data extracted. Stopping pipeline.")

    # 2. Add Lineage Columns & Placeholder
    df["ingestion_month"] = run_month
    df["llm_based_category"] = None # Matches REQUIRED_SCHEMA name
    
    df["data_source"] = "serpapi"
    df["search_engine"] = "google_jobs"

    # 3. Normalization (Text Cleaning)
    logger.info("Normalizing text fields...")
    text_cols = ["description", "title", "company_name"]
    for col in text_cols:
        df[col] = df[col].apply(clean_text)

    # 4. Schema Enforcement
    logger.info("Enforcing schema...")
    for col in REQUIRED_SCHEMA:
        if col not in df.columns:
            df[col] = None
    
    # 5. --- FAIL-FAST CHECK 2: Quality (MUST happen BEFORE fillna) ---
    df = df.dropna(subset=["job_id"])

    # 6. Final Formatting & Cleanup
    df = df[REQUIRED_SCHEMA] # Final Fixed Column Order
    df["salary"] = df["salary"].fillna("Not mentioned")
    df.fillna("Unknown", inplace=True) # Now safe to fill remaining NaNs

    # 7. Deterministic Sorting
    logger.info("Sorting data for deterministic output...")
    df.sort_values(by=["job_id", "company_name"], inplace=True)

    # 8. Save
    processed_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(processed_path, index=False)
    
    logger.info(f"Successfully processed {len(df)} jobs to {processed_path}")


if __name__ == "__main__":
    main()
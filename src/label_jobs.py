import os
import sys
from pathlib import Path
import pandas as pd
import mlflow.sklearn
from dotenv import load_dotenv

load_dotenv()

TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI")
mlflow.set_tracking_uri(TRACKING_URI)

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from utils.logger import setup_logger
# We now import get_processed_data_path and get_final_data_path directly
from utils.paths import get_processed_data_path, get_final_data_path, get_log_path
from utils.dates import current_run_date

def run_labeling_pipeline():
    # 1. Identify the Specific Target for this Run
    # This ensures we only label the data DVC is currently tracking/running
    run_month = current_run_date()
    
    # Get precise file paths (e.g., .../processed/serpapi/2026-01.csv)
    input_path = get_processed_data_path(run_month)
    output_path = get_final_data_path(run_month)
    
    log_file_path = get_log_path(run_month)
    logger = setup_logger(log_path=log_file_path, logger_name="job_labeler")
    
    # Ensure output directory exists for DVC
    output_path.parent.mkdir(parents=True, exist_ok=True)

    MODEL_NAME = "Job_Categorizer_Production"
    model_uri = f"models:/{MODEL_NAME}@champion"
    
    logger.info(f"📡 Pulling @champion from DagsHub: {TRACKING_URI}")
    
    try:
        model = mlflow.sklearn.load_model(model_uri)
        logger.info("💎 Model loaded successfully!")
    except Exception as e:
        logger.error(f"❌ Failed to load model: {str(e)}")
        return

    # 2. Validation: Ensure the specific input file exists
    if not input_path.exists():
        logger.error(f"⚠️ Source file {input_path} not found. Did the 'process' stage fail?")
        return

    logger.info(f"🔍 Processing data file: {input_path.name}")
    
    try:
        # Pandas will read it as a CSV
        df = pd.read_csv(input_path)

        # Basic Validation
        if 'title' not in df.columns:
            logger.error(f"❌ 'title' column missing in {input_path.name}")
            return
        
        if df.empty:
            logger.warning(f"⏩ {input_path.name} is empty. Skipping.")
            return

        # 3. Preprocessing (Same logic as before)
        X_input = (df['title'].fillna('') + " " + df['description'].fillna('')).astype(str)
        
        # 4. Inference
        df['category'] = model.predict(X_input)
        
        # 5. Save to the specific DVC-tracked output path
        # If input is processed/serpapi/2026-01.csv, output is final/serpapi/2026-01.csv
        df.to_csv(output_path, index=False)
        logger.info(f"✅ Saved {len(df)} labeled rows to {output_path}")

    except Exception as e:
        logger.error(f"❌ Could not process {input_path.name}: {str(e)}")

    logger.info("🏁 Labeling pipeline complete.")

if __name__ == "__main__":
    run_labeling_pipeline()
import os
import sys
from pathlib import Path
import pandas as pd
import mlflow.sklearn
from dotenv import load_dotenv
import yaml 

load_dotenv()

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from utils.logger import setup_logger
from utils.paths import get_processed_data_path, get_final_data_path, get_log_path, PARAMS_PATH

def load_params():
    """Load the single source of truth for the current batch ID."""
    if not PARAMS_PATH.exists():
        raise FileNotFoundError(f"params.yaml missing at {PARAMS_PATH}")
    
    with open(PARAMS_PATH, "r") as f:
        return yaml.safe_load(f)

def run_labeling_pipeline():
    # 1. Load Configuration
    try:
        params = load_params()
        # FIX: Use the deterministic batch ID from params, not the current clock time
        run_month = str(params["ingest"]["current_month"])
        
        MODEL_NAME = params['ml_models']['job_labeler']['name']
        VERSION = params['ml_models']['job_labeler']['version_alias']
    except Exception as e:
        print(f"❌ Configuration Error: {e}")
        sys.exit(1)

    # 2. Setup Logging
    log_file_path = get_log_path(run_month)
    logger = setup_logger(log_path=log_file_path, logger_name="job_labeler")
    
    # 3. Build Paths
    input_path = get_processed_data_path(run_month)
    output_path = get_final_data_path(run_month)
    
    # Ensure output directory exists for DVC
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 4. Load Model from DagsHub
    mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI"))
    model_uri = f"models:/{MODEL_NAME}@{VERSION}"
    
    logger.info(f"📡 Pulling @{VERSION} model from DagsHub...")
    
    try:
        model = mlflow.sklearn.load_model(model_uri)
        logger.info("💎 Model loaded successfully!")
    except Exception as e:
        logger.error(f"❌ Failed to load model from {model_uri}: {str(e)}")
        # Harsh truth: If the model fails to load, the pipeline MUST fail.
        sys.exit(1)

    # 5. Validation: Ensure the specific input file exists
    if not input_path.exists():
        logger.error(f"⚠️ Source file {input_path} not found. Did the 'process' stage fail?")
        sys.exit(1)

    logger.info(f"🔍 Processing data file: {input_path.name}")
    
    try:
        # Pandas will read it as a CSV
        df = pd.read_csv(input_path)

        # Basic Validation
        if 'title' not in df.columns:
            logger.error(f"❌ 'title' column missing in {input_path.name}")
            return
        
        if df.empty:
            logger.warning(f"⏩ {input_path.name} is empty. Creating empty output for DVC.")
            # Create the headers-only CSV so DVC is happy
            df.to_csv(output_path, index=False) 
            return

        # 6. Preprocessing (Same logic as before)
        # Note: Ensure this text handling exactly matches what the model was trained on!
        X_input = (df['title'].fillna('') + " " + df['description'].fillna('')).astype(str)
        
        # 7. Inference
        df['category'] = model.predict(X_input)
        
        # 8. Save to the specific DVC-tracked output path
        df.to_csv(output_path, index=False)
        logger.info(f"✅ Saved {len(df)} labeled rows to {output_path}")

    except Exception as e:
        logger.error(f"❌ Could not process {input_path.name}: {str(e)}")
        sys.exit(1)

    logger.info("🏁 Labeling pipeline complete.")

if __name__ == "__main__":
    run_labeling_pipeline()
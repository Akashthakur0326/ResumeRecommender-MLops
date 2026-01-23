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
from utils.paths import PROCESSED_SERPAPI_DIR, FINAL_DIR, get_log_path
from utils.dates import current_run_month

def run_labeling_pipeline():
    log_file_path = get_log_path(current_run_month())
    logger = setup_logger(log_path=log_file_path, logger_name="job_labeler")
    
    # Ensure output directory exists for DVC
    FINAL_DIR.mkdir(parents=True, exist_ok=True)

    MODEL_NAME = "Job_Categorizer_Production"
    model_uri = f"models:/{MODEL_NAME}@champion"
    
    logger.info(f"📡 Pulling @champion from DagsHub: {TRACKING_URI}")
    
    try:
        model = mlflow.sklearn.load_model(model_uri)
        logger.info("💎 Model loaded successfully!")
    except Exception as e:
        logger.error(f"❌ Failed to load model: {str(e)}")
        return

    if not PROCESSED_SERPAPI_DIR.exists():
        logger.warning(f"⚠️ Source directory {PROCESSED_SERPAPI_DIR} not found.")
        return

    # rglob("*") finds everything recursively. We then filter manually.
    for file_path in PROCESSED_SERPAPI_DIR.rglob("*"):
        
        # --- NEW LOGIC: Filter for files, ignore logs ---
        if file_path.is_file() and file_path.suffix != ".log":
            logger.info(f"🔍 Found data file: {file_path.name} (Suffix: {file_path.suffix})")
            
            try:
                # Pandas will read it as a CSV even without the .csv extension
                df = pd.read_csv(file_path)

                if 'title' not in df.columns:
                    continue
                
                if df.empty:
                    logger.warning(f"⏩ {file_path.name} is empty. Skipping.")
                    continue

                # Preprocessing
                X_input = (df['title'].fillna('') + " " + df['description'].fillna('')).astype(str)
                
                # Inference
                df['category'] = model.predict(X_input)
                
                # Maintain same folder structure in FINAL_DIR
                # If input is serpapi/2026-01, output is final/2026-01.csv
                relative_path = file_path.relative_to(PROCESSED_SERPAPI_DIR)
                output_path = (FINAL_DIR / relative_path).with_suffix(".csv")
                output_path.parent.mkdir(parents=True, exist_ok=True)
                
                df.to_csv(output_path, index=False)
                logger.info(f"✅ Saved {len(df)} labeled rows to {output_path}")

            except Exception as e:
                logger.error(f"❌ Could not process {file_path.name}: {str(e)}")

    logger.info("🏁 Labeling pipeline complete.")

if __name__ == "__main__":
    run_labeling_pipeline()
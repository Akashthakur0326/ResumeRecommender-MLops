import yaml
import sys
from pathlib import Path

# 1. Setup paths to reach root from src/
current_file = Path(__file__).resolve()
project_root = current_file.parent.parent
params_path = project_root / "params.yaml"

# 2. Add root to sys.path to import utils
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from utils.dates import current_run_month
from utils.logger import setup_logger

def main():
    # 3. Setup Logger
    # We use a dedicated log for param updates or reuse the general one
    log_dir = project_root / "logs" / "pipeline"
    log_dir.mkdir(parents=True, exist_ok=True)
    logger = setup_logger(log_dir / "pipeline_mgmt.log", "param_updater")

    logger.info("🚀 Starting params.yaml synchronization...")

    # 4. Load current params
    if params_path.exists():
        try:
            with open(params_path, "r") as f:
                params = yaml.safe_load(f) or {}
            logger.info(f"📂 Loaded existing params from {params_path}")
        except Exception as e:
            logger.error(f"❌ Failed to read params.yaml: {str(e)}")
            sys.exit(1)
    else:
        params = {}
        logger.warning("📝 params.yaml missing. Creating a new one.")

    # 5. Get current month and compare
    if "ingest" not in params:
        params["ingest"] = {}
    
    old_month = params["ingest"].get("current_month", "None")
    new_month = current_run_month()

    if old_month == new_month:
        logger.info(f"✅ Month is already up to date: {new_month}. No changes needed.")
    else:
        # 6. Update and Save
        params["ingest"]["current_month"] = new_month
        try:
            with open(params_path, "w") as f:
                yaml.safe_dump(params, f, default_flow_style=False)
            logger.info(f"🔄 Updated current_month: {old_month} ➔ {new_month}")
        except Exception as e:
            logger.error(f"❌ Failed to write to params.yaml: {str(e)}")
            sys.exit(1)

    logger.info("🏁 Parameter update process complete.")

if __name__ == "__main__":
    main()
import sys
import re
from pathlib import Path
from datetime import datetime

# 1. Setup paths
current_file = Path(__file__).resolve()
project_root = current_file.parent.parent
params_path = project_root / "params.yaml"

if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

# CHANGE 1: Import the new daily function (or just format it here directly)
from utils.dates import current_run_date 
from utils.logger import setup_logger

def main():
    log_dir = project_root / "logs" / "pipeline"
    log_dir.mkdir(parents=True, exist_ok=True)
    logger = setup_logger(log_dir / "pipeline_mgmt.log", "param_updater")

    if not params_path.exists():
        logger.error(f"❌ {params_path} not found!")
        return

    # CHANGE 2: Use the full date instead of just month
    # This makes the param "2026-01-28"
    new_batch_id = current_run_date()
    
    try:
        with open(params_path, "r", encoding="utf-8") as f:
            lines = [line.rstrip() for line in f.readlines()]
        
        new_lines = []
        found = False

        for line in lines:
            if "current_month:" in line:
                indent = re.match(r"^(\s*)", line).group(1)
                # CHANGE 3: Update the value
                line = f'{indent}current_month: "{new_batch_id}"'
                found = True
            new_lines.append(line)

        if not found:
            logger.warning("⚠️ 'current_month:' key not found!")
            return

        with open(params_path, "w", encoding="utf-8") as f:
            f.write("\n".join(new_lines) + "\n")
            
        logger.info(f"✅ params.yaml updated: current_month is now \"{new_batch_id}\"")

    except Exception as e:
        logger.error(f"❌ Update failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
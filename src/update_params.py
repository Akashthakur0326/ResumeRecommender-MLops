import sys
import re
from pathlib import Path

# 1. Setup paths
current_file = Path(__file__).resolve()
project_root = current_file.parent.parent
params_path = project_root / "params.yaml"

if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from utils.dates import current_run_month
from utils.logger import setup_logger

def main():
    log_dir = project_root / "logs" / "pipeline"
    log_dir.mkdir(parents=True, exist_ok=True)
    logger = setup_logger(log_dir / "pipeline_mgmt.log", "param_updater")

    if not params_path.exists():
        logger.error(f"❌ {params_path} not found!")
        return

    new_month = current_run_month()
    
    try:
        # 2. Read lines and strip trailing whitespace/newlines immediately
        with open(params_path, "r", encoding="utf-8") as f:
            lines = [line.rstrip() for line in f.readlines()]
        
        new_lines = []
        found = False

        for line in lines:
            # 3. Use a precise match for the key
            if "current_month:" in line:
                # Capture the leading indentation (whitespace) to keep the YAML valid
                indent = re.match(r"^(\s*)", line).group(1)
                line = f'{indent}current_month: "{new_month}"'
                found = True
            new_lines.append(line)

        if not found:
            logger.warning("⚠️ 'current_month:' key not found!")
            return

        # 4. Write back with a single newline joining them
        # This prevents the "stacking" of newlines
        with open(params_path, "w", encoding="utf-8") as f:
            f.write("\n".join(new_lines) + "\n")
            
        logger.info(f"✅ params.yaml updated: current_month is now \"{new_month}\"")

    except Exception as e:
        logger.error(f"❌ Update failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
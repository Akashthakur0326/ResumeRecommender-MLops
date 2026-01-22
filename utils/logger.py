import logging
import sys
from pathlib import Path

def setup_logger(
    log_path: Path, 
    logger_name: str = "mlops_pipeline",
    level: int = logging.INFO
) -> logging.Logger:
    """
    Highly dynamic logger for local and cloud environments.
    """
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(logger_name)
    logger.setLevel(level)
    
    # Avoid adding handlers if they already exist (better than clearing)
    if not logger.handlers:
        formatter = logging.Formatter(
            "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
        )

        # File Handler
        fh = logging.FileHandler(log_path, encoding="utf-8")
        fh.setFormatter(formatter)
        logger.addHandler(fh)

        # Console Handler
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(formatter)
        logger.addHandler(sh)

    return logger
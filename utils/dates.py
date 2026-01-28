from datetime import datetime, timezone

def current_run_month() -> str:
    # Use timezone-aware UTC now
    return datetime.now(timezone.utc).strftime("%Y-%m")

def current_run_date() -> str:
    """Returns YYYY-MM-DD (For daily testing runs)"""
    return datetime.now().strftime("%Y-%m-%d")
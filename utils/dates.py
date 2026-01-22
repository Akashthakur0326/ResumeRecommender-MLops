from datetime import datetime, timezone

def current_run_month() -> str:
    # Use timezone-aware UTC now
    return datetime.now(timezone.utc).strftime("%Y-%m")
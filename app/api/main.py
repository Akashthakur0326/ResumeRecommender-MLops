import sys
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List
from datetime import datetime

from fastapi import FastAPI, HTTPException, UploadFile, File, Request, Response
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

# --- PATH HACK ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

# --- IMPORTS ---
from app.services.score_resume import ResumeScorerService
from app.services.ai_insight import AIInsightEngine
from data_ingestion.resume_ingestion.factory import IngestorFactory
from src.parser.engine import ResumeParserEngine
from src.vector_db.client import PostgresClient
from utils.logger import setup_logger

# --- LOGGING ---
logger = setup_logger(PROJECT_ROOT / "logs" / "api.log", "api_main")

# ==========================================
# 1. METRICS DEFINITION
# ==========================================

# A. API Metrics
REQUEST_COUNT = Counter(
    "http_requests_total", 
    "Total HTTP requests", 
    ["method", "endpoint", "status"]
)

REQUEST_LATENCY = Histogram(
    "http_request_latency_seconds", 
    "Request latency in seconds", 
    ["endpoint"]
)

# B. Database Metrics (Business Logic)

# 1. Job Distribution (For Percentage Graph)
DB_JOB_DISTRIBUTION = Gauge(
    "db_job_category_count",
    "Count of jobs per category (Use for % calc in Grafana)",
    ["category"]
)

# 2. Volume
DB_TOTAL_ROWS = Gauge(
    "db_total_rows",
    "Total number of jobs in the Vector DB"
)

# 3. Role Definitions (Inventory)
# We set value=1 so Grafana can just list the keys
DB_ROLE_STATUS = Gauge(
    "db_role_definition_active",
    "Active role definitions in system",
    ["job_title"]
)

# 4. Locations (Inventory)
DB_LOCATION_STATUS = Gauge(
    "db_location_active",
    "Active target locations",
    ["location_name"]
)

# 5. Ingestion Policy (Staleness/Drift)
# Tracks how long a policy has been active (effective_duration_seconds)
# Labels capture the Metadata (Reason, Priority)
DB_POLICY_DURATION = Gauge(
    "db_ingestion_policy_duration_seconds",
    "Time since policy became effective",
    ["category", "reason", "priority"]
)

# ==========================================
# 2. MIDDLEWARE (Cardinality Safe)
# ==========================================
class PrometheusMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        status_code = 500
        
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception as e:
            raise e
        finally:
            duration = time.time() - start_time
            
            # Safe Route Extraction
            route = request.scope.get("route")
            endpoint = route.path if route else request.url.path
            
            if endpoint != "/metrics":
                REQUEST_COUNT.labels(
                    method=request.method, 
                    endpoint=endpoint, 
                    status=status_code
                ).inc()
                REQUEST_LATENCY.labels(endpoint=endpoint).observe(duration)

# ==========================================
# 3. HELPER: DB METRICS UPDATER (Complex)
# ==========================================
def update_db_metrics():
    """Queries Postgres to update Business Gauges."""
    db = None
    try:
        db = PostgresClient()
        try:
            with db.connect().cursor() as cur:
                # --- QUERY 1: JOB DISTRIBUTION ---
                cur.execute("SELECT category, COUNT(*) FROM job_embeddings GROUP BY category")
                rows = cur.fetchall()
                total_jobs = 0
                
                # Reset old values isn't possible easily in Prom without restart, 
                # but .set() overwrites existing.
                for category, count in rows:
                    if category:
                        DB_JOB_DISTRIBUTION.labels(category=category).set(count)
                        total_jobs += count
                DB_TOTAL_ROWS.set(total_jobs)

                # --- QUERY 2: ROLE DEFINITIONS ---
                # We assume all rows in role_definitions are "Active"
                cur.execute("SELECT job_title FROM role_definitions")
                roles = cur.fetchall()
                for (role_title,) in roles:
                    if role_title:
                        DB_ROLE_STATUS.labels(job_title=role_title).set(1)

                # --- QUERY 3: ACTIVE LOCATIONS ---
                cur.execute("SELECT location_name FROM locations_base WHERE is_active = TRUE")
                locs = cur.fetchall()
                for (loc_name,) in locs:
                    if loc_name:
                        DB_LOCATION_STATUS.labels(location_name=loc_name).set(1)

                # --- QUERY 4: INGESTION POLICY (Staleness) ---
                # We only want the CURRENTLY active policies (effective_to is NULL)
                cur.execute("""
                    SELECT internal_category, reason, priority, effective_from 
                    FROM ingestion_policy 
                    WHERE effective_to IS NULL
                """)
                policies = cur.fetchall()
                current_time = datetime.now()
                
                for (cat, reason, priority, eff_from) in policies:
                    if eff_from and cat:
                        # Calculate how many seconds this policy has been running
                        duration = (current_time - eff_from).total_seconds()
                        DB_POLICY_DURATION.labels(
                            category=cat, 
                            reason=reason or "None", 
                            priority=priority or "Normal"
                        ).set(duration)
            
            logger.info(f"✅ DB Metrics Updated: {total_jobs} jobs, {len(roles)} roles, {len(locs)} locations.")
            
        finally:
            db.close()
            
    except Exception as e:
        logger.warning(f"⚠️ Failed to update DB metrics: {e}")

# ==========================================
# 4. LIFESPAN
# ==========================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 API Starting...")
    try:
        app.state.scorer = ResumeScorerService()
        app.state.ai_engine = AIInsightEngine()
        print("✅ Models Loaded!")
    except Exception as e:
        logger.critical(f"❌ Critical Error: {e}")
        raise RuntimeError("Model loading failed") from e
    
    # Run once at startup
    update_db_metrics()
    
    yield
    
    print("🛑 API Shutting down.")
    if hasattr(app.state, "scorer"): app.state.scorer.close()
    if hasattr(app.state, "ai_engine"): app.state.ai_engine.close()

# ==========================================
# 5. APP INIT & ENDPOINTS
# ==========================================
app = FastAPI(title="Resume Intelligence API", version="1.0", lifespan=lifespan)
app.add_middleware(PrometheusMiddleware)

class InsightRequest(BaseModel):
    resume_text: str
    category: str
    user_skills: List[str]
    matched_jobs: List[str]
    gap_jobs: List[str]

MAX_FILE_SIZE = 5 * 1024 * 1024
def validate_file(file_bytes: bytes):
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large.")

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

# Manual Refresh for Drift Updates
@app.post("/api/v1/refresh_metrics")
def refresh_metrics():
    """Force update of DB Gauges (Call this after ingestion runs)"""
    update_db_metrics()
    return {"status": "metrics_refreshed"}

@app.get("/health")
def health(request: Request):
    return {"status": "healthy"}

@app.post("/api/v1/parse_resume")
def parse_resume_only(file: UploadFile = File(...)):
    try:
        file_bytes = file.file.read()
        validate_file(file_bytes)
        factory = IngestorFactory()
        ext = Path(file.filename).suffix.lower()
        ingestor = factory.get_ingestor(ext)
        raw_text = ingestor.extract(file_bytes)
        parser = ResumeParserEngine()
        structured_data = parser.parse(raw_text)
        structured_data["raw_text"] = raw_text
        return structured_data
    except Exception as e:
        logger.error(f"Parsing failed: {e}")
        raise HTTPException(status_code=500, detail="Parsing error")

@app.post("/api/v1/score_file")
def score_resume_file(request: Request, file: UploadFile = File(...)):
    scorer = getattr(request.app.state, "scorer", None)
    if not scorer:
        raise HTTPException(status_code=503, detail="Scorer Unavailable")
    try:
        file_bytes = file.file.read()
        validate_file(file_bytes)
        ext = Path(file.filename).suffix.lower()
        ingestor = IngestorFactory().get_ingestor(ext)
        raw_text = ingestor.extract(file_bytes)
        results = scorer.get_recommendations(raw_text)
        return results
    except Exception as e:
        logger.error(f"Scoring failed: {e}")
        raise HTTPException(status_code=500, detail="Scoring error")

@app.post("/api/v1/generate_insight")
def generate_insight(request: Request, payload: InsightRequest):
    ai_engine = getattr(request.app.state, "ai_engine", None)
    if not ai_engine:
        raise HTTPException(status_code=503, detail="AI Engine Unavailable")
    try:
        insight = ai_engine.generate_insight(
            resume_text=payload.resume_text,
            user_skills=payload.user_skills,
            category=payload.category,
            matched_jobs=payload.matched_jobs,
            gap_jobs=payload.gap_jobs
        )
        return insight
    except Exception as e:
        logger.error(f"Insight failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
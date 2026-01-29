import sys
import os
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException, UploadFile, File, Request
from typing import List, Dict, Any

# --- PATH HACK (Keep for Local, Remove later for Docker) ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

# Imports
from app.services.score_resume import ResumeScorerService
from data_ingestion.resume_ingestion.factory import IngestorFactory
from src.parser.engine import ResumeParserEngine
from utils.logger import setup_logger

# Initialize Logger
logger = setup_logger(PROJECT_ROOT / "logs" / "api.log", "api_main")


#lifespan defines a logic that runs before the app starts and after the app stops the yield statement sperates the two 
# --- LIFESPAN (Model Loading) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 API Starting: Loading ML Models into Memory...")
    try:
        # ATTACH TO APP STATE (Clean Dependency Injection)
        #app.state as a global storage locker that is attached to your FastAPI instance.
        app.state.scorer = ResumeScorerService()
        print("✅ Models Loaded! Ready to infer.")
    except Exception as e:
        logger.critical(f"❌ Critical Error during startup: {e}")
        # We don't yield here; we let the app crash if models fail (Fail Fast)
        raise RuntimeError("ML Model failed to load") from e
    yield
    print("🛑 API Shutting down.")
    # Clean up resources if needed
    del app.state.scorer

app = FastAPI(title="Resume Intelligence API", version="1.0", lifespan=lifespan)

# --- HELPER: BACKEND VALIDATION ---
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB Limit

def validate_file(file_bytes: bytes):
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large. Max size is 5MB.")

# --- ENDPOINT 1: PARSE ONLY ---
@app.post("/api/v1/parse_resume")
def parse_resume_only(file: UploadFile = File(...)):
    """
    Synchronous 'def' used so CPU-heavy parsing doesn't block the event loop.
    """
    try:
        # 1. Backend Validation
        file_bytes = file.file.read()
        validate_file(file_bytes)

        # 2. Ingest
        factory = IngestorFactory()
        ext = Path(file.filename).suffix.lower()
        ingestor = factory.get_ingestor(ext)
        raw_text = ingestor.extract(file_bytes)

        # 3. Parse
        parser = ResumeParserEngine()
        structured_data = parser.parse(raw_text)
        
        # 4. Return
        structured_data["raw_text"] = raw_text
        return structured_data
        
    except HTTPException as he:
        raise he # Re-raise known HTTP errors
    except Exception as e:
        logger.error(f"Parsing failed for {file.filename}: {e}")
        raise HTTPException(status_code=500, detail="Internal processing error.")

# --- ENDPOINT 2: SCORE FILE ---
@app.post("/api/v1/score_file")
def score_resume_file(request: Request, file: UploadFile = File(...)):
    """
    Uses Request object to access app.state.scorer
    """
    scorer = getattr(request.app.state, "scorer", None)
    if not scorer:
        raise HTTPException(status_code=503, detail="Service Unavailable: Model not initialized.")
    
    try:
        # 1. Validation
        file_bytes = file.file.read()
        validate_file(file_bytes)
        
        # 2. Ingest
        ext = Path(file.filename).suffix.lower()
        ingestor = IngestorFactory().get_ingestor(ext)
        raw_text = ingestor.extract(file_bytes)

        # 3. Score (Heavy ML)
        # This blocks the thread, but FastAPI handles it in a threadpool because we used 'def'
        results = scorer.get_recommendations(raw_text)
        return results

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Scoring failed for {file.filename}: {e}")
        raise HTTPException(status_code=500, detail="Error calculating scores.")

# Health check
@app.get("/health")
def health(request: Request):
    scorer_loaded = hasattr(request.app.state, "scorer")
    return {
        "status": "healthy", 
        "model_loaded": scorer_loaded
    }
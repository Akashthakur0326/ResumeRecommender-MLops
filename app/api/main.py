import sys
import os
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException, UploadFile, File, Request
from pydantic import BaseModel # New import
from typing import List

# Path Hack
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

# Imports
from app.services.score_resume import ResumeScorerService
from app.services.ai_insight import AIInsightEngine # ✅ Import here
from data_ingestion.resume_ingestion.factory import IngestorFactory
from src.parser.engine import ResumeParserEngine
from utils.logger import setup_logger

logger = setup_logger(PROJECT_ROOT / "logs" / "api.log", "api_main")

# --- LIFESPAN ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 API Starting...")
    try:
        app.state.scorer = ResumeScorerService()
        # ✅ Load AI Engine separately
        app.state.ai_engine = AIInsightEngine()
        print("✅ Models Loaded!")
    except Exception as e:
        logger.critical(f"❌ Critical Error: {e}")
        raise RuntimeError("Model loading failed") from e
    
    yield
    
    print("🛑 API Shutting down.")
    if hasattr(app.state, "scorer"): app.state.scorer.close()
    if hasattr(app.state, "ai_engine"): app.state.ai_engine.close()

app = FastAPI(title="Resume Intelligence API", version="1.0", lifespan=lifespan)

# --- MODELS ---
class InsightRequest(BaseModel):
    resume_text: str
    category: str
    user_skills: List[str]
    matched_jobs: List[str]
    gap_jobs: List[str]

# --- HELPER ---
MAX_FILE_SIZE = 5 * 1024 * 1024
def validate_file(file_bytes: bytes):
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large.")

# --- ENDPOINT 1: PARSE ---
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

# --- ENDPOINT 2: SCORE (FAST) ---
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
        
        # This is now FAST (No AI call)
        results = scorer.get_recommendations(raw_text)
        return results
    except Exception as e:
        logger.error(f"Scoring failed: {e}")
        raise HTTPException(status_code=500, detail="Scoring error")

# --- ENDPOINT 3: INSIGHT (ON DEMAND) ---
@app.post("/api/v1/generate_insight")
def generate_insight(request: Request, payload: InsightRequest):
    """
    Generates Graph+LLM analysis for a single category.
    """
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

@app.get("/health")
def health(request: Request):
    return {"status": "healthy"}
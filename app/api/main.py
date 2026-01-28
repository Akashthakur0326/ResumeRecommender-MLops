import sys
import os
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException, UploadFile, File
from typing import List, Dict, Any

# Fix Path to reach 'src' and 'data_ingestion'
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

# Global Singleton
scorer_service = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global scorer_service
    print("🚀 API Starting: Loading ML Models into Memory...")
    try:
        # Load the Scorer Service (loads Transformers into RAM)
        scorer_service = ResumeScorerService()
        print("✅ Models Loaded! Ready to infer.")
    except Exception as e:
        print(f"❌ Critical Error during startup: {e}")
    yield
    print("🛑 API Shutting down.")

app = FastAPI(title="Resume Intelligence API", version="1.0", lifespan=lifespan)

# --- ENDPOINT 1: PARSE ONLY ---
@app.post("/api/v1/parse_resume")
def parse_resume_only(file: UploadFile = File(...)):
    """
    Synchronous 'def' used so CPU-heavy parsing doesn't block the event loop.
    """
    try:
        factory = IngestorFactory()
        ext = Path(file.filename).suffix.lower()
        ingestor = factory.get_ingestor(ext)

        # In a 'def' route, we use .file.read() without await
        file_bytes = file.file.read() 

        # Extract raw text
        raw_text = ingestor.extract(file_bytes)

        # Parse into structured JSON
        parser = ResumeParserEngine()
        structured_data = parser.parse(raw_text)
        
        structured_data["raw_text"] = raw_text
        return structured_data
        
    except Exception as e:
        logger.error(f"Parsing failed for {file.filename}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during document parsing.")

# --- ENDPOINT 2: SCORE FILE ---
@app.post("/api/v1/score_file")
def score_resume_file(file: UploadFile = File(...)):
    """
    Standard 'def' allows FastAPI to handle this heavy ML task in a thread pool.
    """
    if not scorer_service:
        raise HTTPException(status_code=503, detail="Scoring model not loaded or initialized.")
    
    try:
        ext = Path(file.filename).suffix.lower()
        ingestor = IngestorFactory().get_ingestor(ext)
        
        # Read content
        file_bytes = file.file.read()
        raw_text = ingestor.extract(file_bytes)

        # ML Inference (Cosine Similarity + pgvector lookup)
        results = scorer_service.get_recommendations(raw_text)
        return results

    except Exception as e:
        logger.error(f"Scoring failed for {file.filename}: {e}")
        raise HTTPException(status_code=500, detail="Error calculating resume-job match scores.")

# Health check
@app.get("/health")
def health():
    return {
        "status": "healthy", 
        "model_loaded": scorer_service is not None
    }
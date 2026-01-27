# app/api/main.py
import sys
import os
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any

# Fix Path to reach 'src'
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PROJECT_ROOT))

from app.services.score_resume import ResumeScorerService

# Global Singleton
scorer_service = None

# 1. LIFESPAN: The "Load Once" Magic
#The model loads immediately when the Container starts (before any user visits)
@asynccontextmanager
async def lifespan(app: FastAPI):
    global scorer_service
    print("🚀 API Starting: Loading ML Models into Memory...")
    try:
        # This takes 2-3 seconds but happens ONLY ONCE
        scorer_service = ResumeScorerService()
        print("✅ Models Loaded! Ready to infer.")
    except Exception as e:
        print(f"❌ Critical Error: {e}")
    yield
    # Clean up code (if needed) goes here
    print("🛑 API Shutting down.")

app = FastAPI(title="Resume Intelligence API", version="1.0", lifespan=lifespan)

# 2. Pydantic Models (Data Validation)
class AnalyzeRequest(BaseModel):
    resume_text: str

# 3. The Endpoint
@app.post("/api/v1/score")
async def score_resume(payload: AnalyzeRequest):
    if not scorer_service:
        raise HTTPException(status_code=503, detail="Model not initialized yet.")
    
    try:
        # The service does the DB lookup + Math
        results = scorer_service.get_recommendations(payload.resume_text)
        
        if "error" in results:
            raise HTTPException(status_code=500, detail=results["error"])
            
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Health check for AWS Load Balancers
@app.get("/health")
def health():
    return {"status": "healthy", "model_ready": scorer_service is not None}
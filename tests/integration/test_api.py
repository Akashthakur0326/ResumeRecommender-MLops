"""
Prove your backend accepts requests and returns valid JSON.
"""

import pytest
from fastapi.testclient import TestClient
from app.api.main import app

# Initialize Client
# Note: We use the context manager to ensure startup/shutdown events run
@pytest.fixture
def client(mock_scorer):
    """
    Returns a TestClient where the 'lifespan' startup event 
    loads our MOCKED scorer instead of the real one.
    """
    with TestClient(app) as c:
        yield c

class TestResumeAPI:
    
    def test_health_check(self, client):
        """
        GIVEN the app is running
        WHEN /health is called
        THEN it should confirm the model (mocked) is loaded.
        """
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {
            "status": "healthy",
            "model_loaded": True
        }

    def test_score_resume_success(self, client, mock_ingestor):
        """
        GIVEN a valid PDF file
        WHEN /api/v1/score_file is called
        THEN it should return the mock scores defined in conftest.
        """
        # 1. Dummy File (Content doesn't matter because ingestor is mocked)
        files = {
            "file": ("test_resume.pdf", b"%PDF-1.4...", "application/pdf")
        }

        # 2. Action
        response = client.post("/api/v1/score_file", files=files)

        # 3. Assert
        assert response.status_code == 200
        data = response.json()
        
        # Validate the Structure
        assert data["status"] == "success"
        assert data["results"][0]["category"] == "Mocked DevOps"
        
        # Verify our Mock was actually called
        # This proves the API connected to the Service layer
        mock_ingestor.extract.assert_called_once()

    def test_score_resume_validation_error(self, client):
        """
        GIVEN a request with NO file
        WHEN /api/v1/score_file is called
        THEN it should return 422 Unprocessable Entity.
        """
        response = client.post("/api/v1/score_file") # No files argument
        assert response.status_code == 422

    def test_parse_only_endpoint(self, client, mock_ingestor):
        """
        GIVEN a file
        WHEN /api/v1/parse_resume is called
        THEN it should return extracted text and parsed JSON.
        """
        files = {"file": ("resume.pdf", b"dummy", "application/pdf")}
        
        # We need to mock the Parser Engine specifically for this endpoint too
        # or it will try to run the real Regex logic (which is fine, but mocking is safer)
        from unittest.mock import patch
        with patch("app.api.main.ResumeParserEngine") as MockParser:
            MockParser.return_value.parse.return_value = {"name": "Test User", "skills": ["Python"]}
            
            response = client.post("/api/v1/parse_resume", files=files)
            
            assert response.status_code == 200
            data = response.json()
            assert data["name"] == "Test User"
            assert "raw_text" in data
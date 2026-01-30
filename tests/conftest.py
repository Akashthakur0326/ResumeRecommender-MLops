# tests/conftest.py
import pytest
from unittest.mock import MagicMock, patch
import sys
from pathlib import Path

# Fix Import Paths
root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))

@pytest.fixture
def mock_scorer():
    """
    Mocks the heavy ResumeScorerService.
    Bypasses mpnet loading and DB connections.
    """
    with patch("app.api.main.ResumeScorerService") as MockService:
        # Create a fake instance
        mock_instance = MagicMock()
        
        # Define what the fake service returns
        mock_instance.get_recommendations.return_value = {
            "status": "success",
            "results": [
                {
                    "category": "Mocked DevOps",
                    "category_match_score": 0.95,
                    "reasoning": {"semantic_match": 0.9},
                    "recommended_jobs": []
                }
            ]
        }
        
        # When main.py calls ResumeScorerService(), return our fake
        MockService.return_value = mock_instance
        yield mock_instance

@pytest.fixture
def mock_ingestor():
    """
    Mocks the Ingestor to avoid reading real PDF bytes.
    """
    with patch("app.api.main.IngestorFactory") as MockFactory:
        mock_ingestor = MagicMock()
        mock_ingestor.extract.return_value = "This is dummy extracted text from a mock PDF."
        
        # Factory returns our mock ingestor
        MockFactory.return_value.get_ingestor.return_value = mock_ingestor
        yield mock_ingestor
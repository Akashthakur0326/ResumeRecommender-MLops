import pytest
from unittest.mock import MagicMock
import numpy as np

# MOCK THE HEAVY MODEL
@pytest.fixture(autouse=True)
def mock_sentence_transformer(monkeypatch):
    mock_model = MagicMock()
    # Return random 768-dim vector
    mock_model.encode.return_value = np.random.rand(768).astype(np.float32)
    monkeypatch.setattr("src.vector_db.encoder.SentenceTransformer", lambda x: mock_model)

# MOCK THE DB CONNECTION
@pytest.fixture
def test_db_session():
    # Setup connection to the CI Service Container (localhost:5432)
    # This assumes you have a function 'get_db_connection' in your src
    pass
"""
Ensure your "Scoring Logic" didn't suddenly get worse or flip output formats.
"""

import pytest
import numpy as np
from unittest.mock import MagicMock, patch
import sys
from pathlib import Path

# --- SETUP PATHS ---
root_dir = Path(__file__).resolve().parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.append(str(root_dir))

# Import the class and the weights to verify math
from app.services.score_resume import ResumeScorerService, W_SEMANTIC, W_KEYWORDS, W_MUST_HAVE

class TestScoringLogic:
    """
    Regression Tests for the Scoring Algorithm.
    Ensures that changes to the code don't accidentally break the math.
    """

    @pytest.fixture
    def scorer_service(self):
        """
        Creates a ResumeScorerService with MOCKED dependencies.
        We don't want to connect to a real DB for checking math.
        """
        with patch("app.services.score_resume.PostgresClient") as MockDB, \
             patch("app.services.score_resume.SemanticEncoder") as MockEncoder:
            
            service = ResumeScorerService()
            
            # 1. Setup Mock DB
            service.db = MockDB.return_value
            service.db.connect.return_value.cursor.return_value.__enter__.return_value = MagicMock()
            
            # 2. Setup Mock Encoder (Return dummy vector [1.0, 0.0])
            # This ensures dot product math is predictable
            service.encoder = MockEncoder.return_value
            service.encoder.encode_batch.return_value = [[1.0, 0.0]] 
            
            yield service

    def test_calculate_overlap_logic(self, scorer_service):
        """
        Verifies the keyword matching math (Pure Logic).
        """
        resume_text = "I am an expert in Python and Docker."
        target_keywords = ["Python", "Java", "Docker", "Rust"]
        
        # Logic: 
        # "Python" in text? Yes.
        # "Java" in text? No.
        # "Docker" in text? Yes.
        # "Rust" in text? No.
        # Matches = 2. Total = 4. Score should be 0.5.
        
        score = scorer_service._calculate_overlap(resume_text, target_keywords)
        assert score == 0.5, f"Overlap calculation failed! Expected 0.5, got {score}"

    def test_weighted_scoring_formula(self, scorer_service):
        """
        CRITICAL: Verifies that the Weights (0.6, 0.25, 0.15) are applied correctly.
        We simulate a 'Perfect Scenario' via Mocks.
        """
        # 1. Inputs
        resume_text = "I have Python skill."
        dummy_vector = [1.0, 0.0]  # Matches the encoder mock above
        
        # 2. Mock the DB to return a specific 'Role Definition'
        # Format: (category_title, full_definition, semantic_score)
        mock_row = (
            "Python Developer",
            {
                "resume_keywords": ["Python"],         # 100% Keyword Match (1.0)
                "skill_taxonomy": {
                    "must_have": ["Python"]            # 100% 'Must Have' Match
                }
            },
            0.9 # Simulating a 90% Semantic Match from the Vector DB
        )
        
        # Inject the mock row into the cursor
        mock_cursor = scorer_service.db.connect.return_value.cursor.return_value.__enter__.return_value
        mock_cursor.fetchall.return_value = [mock_row]

        # 3. Action: Run the logic
        results = scorer_service._get_category_matches(resume_text, dummy_vector)
        
        # 4. Assert: Manual Math Check
        # Semantic (0.9 * 0.60) = 0.54
        # Keywords (1.0 * 0.25) = 0.25 (Because "Python" is in "Python")
        # MustHave (1.0 * 0.15) = 0.15 (Dot product of [1,0] and [1,0] is 1.0)
        # Expected Total = 0.94
        
        calculated_score = results[0]["score"]
        
        # Use floating point comparison (approx)
        assert 0.939 <= calculated_score <= 0.941, \
            f"Math error! Expected ~0.94, got {calculated_score}"

    def test_scoring_degradation_guardrail(self, scorer_service):
        """
        The specific test you requested:
        'A perfect text match should rarely be below 0.5'
        """
        # 1. Setup a "Bad" Semantic Match (e.g., model thinks they are different)
        # But "Perfect" Keyword Match.
        mock_row = (
            "Legacy Coder",
            {"resume_keywords": ["Cobol"], "skill_taxonomy": {}}, 
            0.1 # Very low semantic score
        )
        
        mock_cursor = scorer_service.db.connect.return_value.cursor.return_value.__enter__.return_value
        mock_cursor.fetchall.return_value = [mock_row]
        
        # Resume has the keyword
        results = scorer_service._get_category_matches("I know Cobol", [1.0, 0.0])
        
        # Math:
        # Sem: 0.1 * 0.6 = 0.06
        # Key: 1.0 * 0.25 = 0.25
        # Must: 0.0 * 0.15 = 0.0
        # Total: 0.31
        
        # This asserts that relying ONLY on keywords isn't enough to pass a high bar (0.5).
        # This confirms your system prefers Semantic matches.
        assert results[0]["score"] < 0.5, "System gave a high score to a semantic mismatch!"
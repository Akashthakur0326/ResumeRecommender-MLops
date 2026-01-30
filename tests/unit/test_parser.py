import pytest
import sys
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.append(str(root_dir))

from src.parser.utils import extract_skills

class TestResumeParser:
    """
    Unit tests for utils.py
    """

    @pytest.fixture
    def mock_skills_db(self):
        """
        In Unit Tests, we MOCK the database/CSV. 
        We don't read the real file.
        """
        # MUST be lowercase to match your engine.py logic
        return ["python", "docker", "kubernetes", "ci/cd", "terraform", "aws", "azure"]

    @pytest.fixture
    def dummy_resume_text(self):
        return """
        John Doe
        Software Engineer
        Skills: Python, Docker, Kubernetes, CI/CD, Terraform.
        Experience: Worked on AWS and Azure cloud platforms.
        """

    def test_extract_skills_success(self, dummy_resume_text, mock_skills_db):
        """
        Checks if skills are extracted given a known skills list.
        """
        # 1. Action: PASS THE SKILLS LIST (This was your error)
        extracted = extract_skills(dummy_resume_text, mock_skills_db)

        # 2. Assertions
        assert isinstance(extracted, list)
        
        # 3. Logic Check: Expect LOWERCASE because your utils.py does .lower()
        expected_skills = ["python", "docker", "ci/cd"]
        for skill in expected_skills:
            assert skill in extracted, f"Failed to extract {skill}"

    def test_extract_skills_empty_input(self, mock_skills_db):
        """Ensures the parser handles empty input gracefully."""
        assert extract_skills("", mock_skills_db) == []
        assert extract_skills("I like pizza", mock_skills_db) == []

    def test_extract_skills_case_insensitivity(self, mock_skills_db):
        """
        Input is mixed case, DB is lowercase. 
        Output should be normalized to lowercase.
        """
        text = "I know PYTHON and DoCkEr"
        extracted = extract_skills(text, mock_skills_db)
        
        # Implementation returns the token found in the list (which is lowercase)
        assert "python" in extracted
        assert "docker" in extracted
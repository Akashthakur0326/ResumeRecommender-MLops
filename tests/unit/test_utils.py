import pytest
import logging
import sys
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

# --- SETUP PATHS ---
root_dir = Path(__file__).resolve().parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.append(str(root_dir))

from utils.dates import current_run_month, current_run_date
from utils.logger import setup_logger
from utils.paths import get_raw_run_dir, get_processed_data_path, get_model_path, BASE_DIR

# --- 1. TESTS FOR dates.py ---
class TestDatesUtils:
    """
    We mock 'datetime' so these tests work forever, not just today.
    """

    @patch("utils.dates.datetime")
    def test_current_run_month(self, mock_datetime):
        # 1. Setup: Freeze time to a specific UTC instant
        # We must set both .now() and .now(timezone.utc) behavior
        mock_now = MagicMock()
        mock_now.strftime.return_value = "2025-05"
        mock_datetime.now.return_value = mock_now
        
        # 2. Action
        result = current_run_month()
        
        # 3. Assert
        assert result == "2025-05"
        # Ensure it was called with UTC timezone (Crucial for Cloud/Servers)
        mock_datetime.now.assert_called_with(timezone.utc)

    @patch("utils.dates.datetime")
    def test_current_run_date(self, mock_datetime):
        # 1. Setup
        mock_now = MagicMock()
        mock_now.strftime.return_value = "2025-05-20"
        mock_datetime.now.return_value = mock_now

        # 2. Action
        result = current_run_date()

        # 3. Assert
        assert result == "2025-05-20"


# --- 2. TESTS FOR logger.py ---
class TestLoggerUtils:
    """
    Uses 'tmp_path' (Pytest built-in) to avoid writing real log files during testing.
    """
    
    def test_setup_logger_creates_file(self, tmp_path):
        # 1. Setup: Create a temporary path for the log
        fake_log_dir = tmp_path / "logs"
        fake_log_file = fake_log_dir / "test.log"
        
        # 2. Action
        logger = setup_logger(fake_log_file, "test_logger")
        
        # 3. Assert: Check Object
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test_logger"
        assert logger.level == logging.INFO
        
        # 4. Assert: Check Side Effects (File Creation)
        # Your function does log_path.parent.mkdir(), so the folder should exist
        assert fake_log_dir.exists()
        
        # 5. Assert: Check Handlers
        # Should have 2 handlers: FileHandler and StreamHandler
        assert len(logger.handlers) == 2 
        assert any(isinstance(h, logging.FileHandler) for h in logger.handlers)
        assert any(isinstance(h, logging.StreamHandler) for h in logger.handlers)

    def test_logger_singleton_behavior(self, tmp_path):
        """
        Ensures we don't add duplicate handlers if we call setup_logger twice.
        This prevents duplicate log lines like:
        INFO: Hello
        INFO: Hello
        """
        log_file = tmp_path / "test.log"
        
        # Call twice
        logger1 = setup_logger(log_file, "repeat_logger")
        logger2 = setup_logger(log_file, "repeat_logger")
        
        # Should still only have 2 handlers, not 4
        assert len(logger1.handlers) == 2


# --- 3. TESTS FOR paths.py ---
class TestPathUtils:
    
    def test_base_dir_resolution(self):
        """
        CRITICAL: Ensures BASE_DIR is actually pointing to the project root.
        We check if specific known files exist relative to it.
        """
        # "tests" folder should exist in the root
        assert (BASE_DIR / "tests").exists()
        # "utils" folder should exist
        assert (BASE_DIR / "utils").exists()

    def test_directory_helpers_ensure_creation(self, tmp_path):
        """
        Tests if get_raw_run_dir actually creates the folder if missing.
        We patch the global constants in paths.py to point to tmp_path
        so we don't mess up your real C: drive.
        """
        # We need to patch the DATA_DIR inside utils.paths
        with patch("utils.paths.DATA_DIR", tmp_path):
            test_month = "2099-12"
            
            # 1. Action
            result_path = get_raw_run_dir(test_month)
            
            # 2. Assert
            expected_path = tmp_path / "raw" / "serpapi" / test_month
            assert result_path == expected_path
            assert result_path.exists()
            assert result_path.is_dir()

    def test_get_processed_data_path_structure(self, tmp_path):
        with patch("utils.paths.DATA_DIR", tmp_path):
            test_month = "2025-01"
            result = get_processed_data_path(test_month)
            
            # Should return a .csv file path
            assert result.suffix == ".csv"
            assert result.name == "2025-01.csv"
            # Parent folder should be created
            assert result.parent.exists()

    def test_get_model_path(self):
        # Logic check only (no side effects)
        result = get_model_path("bert-base")
        assert result == BASE_DIR / "models" / "bert-base"
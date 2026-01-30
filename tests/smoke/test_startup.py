"""
for params test 
"""

import os
import sys
import yaml
import pytest
from pathlib import Path

# --- 1. SETUP PATHS (Crucial for CI) ---
# We ensure the test can see the project root, no matter where pytest is run from.
curr_dir = Path(__file__).resolve().parent
project_root = curr_dir.parent.parent  # Go up: smoke -> tests -> root

if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

class TestProjectStartup:
    """
    Smoke Tests: Run these FIRST. 
    If these fail, do not bother running Unit or Integration tests.
    """

    def test_critical_configuration_files(self):
        """
        Ensures params.yaml and dvc.yaml exist AND are valid YAML.
        """
        # 1. Check Params
        params_path = project_root / "params.yaml"
        assert params_path.exists(), f"CRITICAL: params.yaml is missing at {params_path}"
        
        # 2. Check Validity (This catches indentation errors)
        try:
            with open(params_path, "r") as f:
                config = yaml.safe_load(f)
            
            # 3. Check for mandatory keys (Fail fast if 'ingest' is missing)
            assert "ingest" in config, "params.yaml is missing the 'ingest' section!"
            assert "ml_models" in config, "params.yaml is missing 'ml_models'!"
            
        except yaml.YAMLError as e:
            pytest.fail(f"params.yaml is corrupt/invalid: {e}")

        # 4. Check DVC
        dvc_path = project_root / "dvc.yaml"
        assert dvc_path.exists(), "dvc.yaml is missing! Pipeline cannot run."

    def test_backend_imports(self):
        """
        Checks if the FastAPI backend compiles without SyntaxErrors 
        or Circular Import crashes.
        """
        try:
            from app.api.main import app
            assert app is not None
        except ImportError as e:
            pytest.fail(f"Backend failed to import. Check paths or dependencies. Error: {e}")
        except Exception as e:
             pytest.fail(f"Backend crashed during startup imports: {e}")

    def test_ui_imports(self):
        """
        Checks if the Streamlit UI compiles. 
        We rely on the fact that importing a streamlit script usually 
        doesn't execute the UI loop immediately, just the definitions.
        """
        try:
            # We mock sys.argv to prevent Streamlit from thinking it's running via CLI
            # This avoids weird flag parsing errors during import
            with patch("sys.argv", ["streamlit", "run"]):
                from ui import app
        except ImportError as e:
            # Warn but don't fail hard if UI deps aren't perfect in Backend CI
             print(f"⚠️ UI Import Warning: {e}")
        except Exception as e:
             # Syntax errors in UI should fail the smoke test
             pytest.fail(f"UI code has syntax errors: {e}")

# Needed for the UI mock
from unittest.mock import patch
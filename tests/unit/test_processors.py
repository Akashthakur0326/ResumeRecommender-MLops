"""
Ensures your JSON-to-CSV cleaning doesn't corrupt data before it hits the DB.
"""

import pytest
import pandas as pd
import sys
from pathlib import Path

# --- SETUP PARENT IMPORTS ---
# This ensures we can import from data_ingestion
root_dir = Path(__file__).resolve().parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.append(str(root_dir))

# Import the SPECIFIC function we just created
from data_ingestion.processors.process_data import transform_raw_data, REQUIRED_SCHEMA

class TestDataProcessor:
    
    @pytest.fixture
    def dummy_raw_df(self):
        """Creates a minimal DataFrame mimicking what load_raw_json_files returns."""
        data = [
            # Case 1: Good Data
            {
                "job_id": "101",
                "title": "DevOps Engineer",
                "company_name": "  Tech Corp  \n", # Dirty text
                "description": "Know AWS.",
                "search_term": "devops",
                "search_location": "Remote"
            },
            # Case 2: Bad Data (Missing job_id -> Should be dropped)
            {
                "job_id": None, 
                "title": "Ghost Job",
                "company_name": "Ghost Corp"
            },
            # Case 3: Duplicate (Should be deduped)
            {
                "job_id": "101", # Same ID as Case 1
                "title": "DevOps Engineer",
                "company_name": "Tech Corp"
            }
        ]
        return pd.DataFrame(data)

    def test_json_normalization_logic(self, dummy_raw_df):
        """
        Tests if the transform_raw_data function:
        1. Cleans text
        2. Drops invalid rows
        3. Removes duplicates
        4. Enforces Schema
        """
        test_month = "2026-01"
        
        # 1. Action - Use the test_month variable here!
        processed_df = transform_raw_data(dummy_raw_df, run_month=test_month)

        # 2. Assertions
        
        # A. Check ingestion_month (Uses the variable we passed)
        assert processed_df.iloc[0]["ingestion_month"] == test_month

        # B. Check Drop Logic
        assert len(processed_df) == 1, f"Expected 1 row, got {len(processed_df)}"
        
        # C. Check Text Cleaning
        cleaned_company = processed_df.iloc[0]["company_name"]
        assert cleaned_company == "Tech Corp"

        # D. Check Default values
        assert processed_df.iloc[0]["salary"] == "Not mentioned"

        # E. Check Column Order matches REQUIRED_SCHEMA
        assert list(processed_df.columns) == REQUIRED_SCHEMA
import pytest
import psycopg2
from unittest.mock import MagicMock, patch
import sys
from pathlib import Path

# --- SETUP PATHS ---
root_dir = Path(__file__).resolve().parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.append(str(root_dir))

from src.vector_db.client import PostgresClient

class TestPostgresClient:
    """
    Tests the Database Connector logic, specifically the 
    Retry Mechanism for Docker race conditions.
    """

    @patch("src.vector_db.client.psycopg2.connect")
    @patch("src.vector_db.client.time.sleep")  # Mock sleep to run tests instantly
    def test_connect_retry_logic_success(self, mock_sleep, mock_connect):
        """
        Scenario: DB is offline for the first 2 attempts, then comes online.
        Expectation: Client should retry and eventually return a connection.
        """
        # 1. Setup Mock Behavior
        # Attempt 1: Fail (OperationalError)
        # Attempt 2: Fail (OperationalError)
        # Attempt 3: Success (Return a Mock Connection)
        mock_conn_instance = MagicMock()
        mock_connect.side_effect = [
            psycopg2.OperationalError("Connection refused"),
            psycopg2.OperationalError("Network unreachable"),
            mock_conn_instance
        ]

        # 2. Action
        client = PostgresClient()
        conn = client.connect()

        # 3. Assertions
        assert conn == mock_conn_instance
        assert mock_connect.call_count == 3  # It tried 3 times
        assert mock_sleep.call_count == 2    # It slept twice
        print("\n✅ Retry logic verified: Survived 2 failures.")

    @patch("src.vector_db.client.psycopg2.connect")
    @patch("src.vector_db.client.time.sleep")
    def test_connect_retry_logic_failure(self, mock_sleep, mock_connect):
        """
        Scenario: DB is permanently down.
        Expectation: Client should raise ConnectionError after max retries.
        """
        # 1. Setup: Always fail
        mock_connect.side_effect = psycopg2.OperationalError("Fatal Error")

        # 2. Action & Assert
        client = PostgresClient()
        
        with pytest.raises(ConnectionError) as excinfo:
            client.connect()
        
        assert "Failed to connect to DB after 5 attempts" in str(excinfo.value)
        assert mock_connect.call_count == 5

    @patch("src.vector_db.client.psycopg2.connect")
    def test_get_cursor(self, mock_connect):
        """
        Tests if get_cursor automatically establishes a connection.
        """
        # 1. Setup
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        # 2. Action
        client = PostgresClient()
        cursor = client.get_cursor()

        # 3. Assert
        assert cursor == mock_cursor
        mock_conn.cursor.assert_called_once()
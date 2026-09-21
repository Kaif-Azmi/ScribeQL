from unittest.mock import patch, MagicMock
from app.db.session import get_app_connection, get_demo_ro_connection, check_db_health


def test_check_db_health_success():
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.fetchone.return_value = (1,)
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    with patch("psycopg.connect", return_value=mock_conn):
        assert check_db_health() is True


def test_check_db_health_failure():
    with patch("psycopg.connect", side_effect=Exception("Connection refused")):
        assert check_db_health() is False


def test_demo_ro_connection_security_configuration():
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    with patch("psycopg.connect", return_value=mock_conn):
        with get_demo_ro_connection() as conn:
            assert conn == mock_conn

        # Verify read-only and timeout enforcement statements were issued
        executed_statements = [call[0][0] for call in mock_cur.execute.call_args_list]
        assert "SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY;" in executed_statements
        assert "SET statement_timeout = '15s';" in executed_statements
        assert "SET lock_timeout = '3s';" in executed_statements

        # Verify rollback was called to ensure execution isolation
        mock_conn.rollback.assert_called_once()
        mock_conn.close.assert_called_once()

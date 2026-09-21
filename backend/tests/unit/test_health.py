from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_api_health_endpoint_healthy():
    with patch("app.api.router.check_db_health", return_value=True):
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        assert "X-Request-ID" in response.headers


def test_api_health_endpoint_unhealthy():
    with patch("app.api.router.check_db_health", return_value=False):
        response = client.get("/api/health")
        assert response.status_code == 503
        assert response.json() == {
            "error": {
                "type": "dependency_unavailable",
                "message": "Database is unreachable."
            }
        }
        assert "X-Request-ID" in response.headers


def test_root_health_alias():
    with patch("app.api.router.check_db_health", return_value=True):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        assert "X-Request-ID" in response.headers

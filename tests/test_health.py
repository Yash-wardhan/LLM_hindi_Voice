from fastapi.testclient import TestClient


class TestHealthEndpoints:
    def test_health_check_returns_200(self, client: TestClient) -> None:
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_check_response_schema(self, client: TestClient) -> None:
        data = client.get("/health").json()
        assert data["status"] == "ok"
        assert "app_name" in data
        assert "version" in data
        assert "timestamp" in data
        assert "uptime_seconds" in data

    def test_liveness_probe(self, client: TestClient) -> None:
        response = client.get("/health/live")
        assert response.status_code == 200
        assert response.json() == {"status": "alive"}

    def test_readiness_probe(self, client: TestClient) -> None:
        response = client.get("/health/ready")
        # 200 when all checks pass
        assert response.status_code in (200, 503)
        data = response.json()
        assert "status" in data
        assert "checks" in data

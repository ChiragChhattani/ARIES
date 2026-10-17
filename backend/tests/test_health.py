"""
Tests for the health check endpoint.

Uses FastAPI's TestClient which simulates HTTP requests
without needing a running server. This is faster and more
reliable than starting uvicorn for each test.
"""


class TestHealthEndpoint:
    """Test the GET /health endpoint."""

    def test_health_returns_200(self, test_client):
        """Health endpoint should return 200 OK."""
        response = test_client.get("/health")
        assert response.status_code == 200

    def test_health_response_structure(self, test_client):
        """Health response should contain required fields."""
        response = test_client.get("/health")
        data = response.json()

        assert "status" in data
        assert "app_name" in data
        assert "version" in data
        assert "environment" in data
        assert "timestamp" in data

    def test_health_status_healthy(self, test_client):
        """Health status should be 'healthy'."""
        response = test_client.get("/health")
        data = response.json()
        assert data["status"] == "healthy"

    def test_health_app_name(self, test_client):
        """App name should match configuration."""
        response = test_client.get("/health")
        data = response.json()
        assert data["app_name"] == "ARIES"

    def test_health_no_secrets_exposed(self, test_client):
        """Health endpoint must NEVER expose API keys or secrets."""
        response = test_client.get("/health")
        data = response.json()
        response_text = str(data)
        assert "sk-" not in response_text
        assert "api_key" not in response_text.lower()
        assert "password" not in response_text.lower()

    def test_correlation_id_header(self, test_client):
        """Response should include X-Correlation-ID header."""
        response = test_client.get("/health")
        assert "X-Correlation-ID" in response.headers

    def test_custom_correlation_id_preserved(self, test_client):
        """When client sends X-Correlation-ID, server should echo it back."""
        custom_id = "test-corr-12345"
        response = test_client.get(
            "/health",
            headers={"X-Correlation-ID": custom_id},
        )
        assert response.headers.get("X-Correlation-ID") == custom_id

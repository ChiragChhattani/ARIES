"""
Tests for the Interviews REST API endpoints and URL routing.

Verifies:
1. /api/v1/interviews endpoint returns 200 for listing and 201 for creation.
2. Request payload matching the frontend format successfully deserializes.
3. Endpoints without /api/v1 prefix return 404 (protecting against URL prefix regressions).
"""

import pytest


class TestInterviewsApi:
    """Test suite for interview endpoints."""

    def test_list_interviews_returns_200(self, test_client):
        """GET /api/v1/interviews returns 200 and a session list."""
        response = test_client.get("/api/v1/interviews")
        assert response.status_code == 200
        data = response.json()
        assert "sessions" in data
        assert "total" in data

    def test_missing_api_v1_prefix_returns_404(self, test_client):
        """
        GET/POST /interviews without /api/v1 prefix must return 404.
        Confirms that requests must be routed through /api/v1.
        """
        get_res = test_client.get("/interviews")
        assert get_res.status_code == 404

        post_res = test_client.post("/interviews", json={})
        assert post_res.status_code == 404

    def test_create_interview_frontend_payload(self, test_client):
        """
        POST /api/v1/interviews with the exact payload structure sent by
        the frontend createInterview() function must return 201 Created.
        """
        frontend_payload = {
            "job_description": {
                "field": "software_engineering",
                "custom_field_name": "",
                "title": "Senior Full-Stack Engineer",
                "description": "We are seeking a seasoned Full-Stack Engineer to architect scalable distributed systems and build modern web applications." + ("." * 20),
                "required_skills": ["React", "Python", "FastAPI"],
                "experience_level": "senior",
                "difficulty": "hard",
                "competencies": [
                    {
                        "name": "System Architecture",
                        "description": "Ability to design scalable and distributed systems",
                        "weight": 1.0,
                        "required": True,
                    },
                    {
                        "name": "Code Quality",
                        "description": "Writing testable, maintainable, and clean code",
                        "weight": 1.0,
                        "required": True,
                    },
                ],
            },
            "settings": {
                "difficulty": "hard",
                "experience_level": "senior",
                "max_questions": 5,
                "timeout_minutes": 30,
            },
            "candidate_identifier": "Anonymous Candidate",
        }

        response = test_client.post("/api/v1/interviews", json=frontend_payload)
        assert response.status_code == 201
        data = response.json()
        assert "session_id" in data
        assert data["job_title"] == "Senior Full-Stack Engineer"
        assert data["status"] == "CONFIGURED"
        assert data["max_questions"] == 5

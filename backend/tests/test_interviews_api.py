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

    def test_start_interview_success(self, test_client, monkeypatch):
        """
        POST /api/v1/interviews/{session_id}/start generates the first question,
        transitions state to IN_PROGRESS, and returns 200.
        """
        res = test_client.post("/api/v1/interviews", json={
            "job_description": {
                "field": "software_engineering",
                "custom_field_name": "",
                "title": "Backend Dev",
                "description": "A" * 60,
                "competencies": [{"name": "Python", "description": "Python knowledge"}]
            }
        })
        assert res.status_code == 201
        session_id = res.json()["session_id"]

        from app.schemas.agent_outputs import NextQuestion
        mock_question = NextQuestion(
            question_text="Tell me about your Python experience.",
            rationale="Opening question",
            competency_targeted="Python",
            is_followup=False,
            expected_good_answer_elements=["experience", "projects"]
        )

        from unittest.mock import AsyncMock
        monkeypatch.setattr(
            "app.agents.interviewer.InterviewerAgentAdapter.generate_next_question",
            AsyncMock(return_value=mock_question)
        )

        start_res = test_client.post(f"/api/v1/interviews/{session_id}/start")
        assert start_res.status_code == 200
        data = start_res.json()
        assert data["status"] == "IN_PROGRESS"
        assert len(data["transcript"]) == 1
        assert data["transcript"][0]["content"] == "Tell me about your Python experience."

    def test_start_interview_session_not_found(self, test_client):
        """Starting a non-existent session returns 404 with SESSION_NOT_FOUND code."""
        res = test_client.post("/api/v1/interviews/non-existent-session-id/start")
        assert res.status_code == 404
        assert res.json()["detail"]["code"] == "SESSION_NOT_FOUND"

    def test_start_interview_invalid_state(self, test_client, monkeypatch):
        """Starting an already started interview returns 400 with INVALID_STATE code."""
        res = test_client.post("/api/v1/interviews", json={
            "job_description": {
                "field": "software_engineering",
                "custom_field_name": "",
                "title": "Backend Dev",
                "description": "A" * 60,
                "competencies": [{"name": "Python", "description": "Python knowledge"}]
            }
        })
        session_id = res.json()["session_id"]

        from app.schemas.agent_outputs import NextQuestion
        mock_question = NextQuestion(
            question_text="Tell me about your Python experience.",
            rationale="Opening question",
            competency_targeted="Python",
            is_followup=False,
            expected_good_answer_elements=["experience", "projects"]
        )
        from unittest.mock import AsyncMock
        monkeypatch.setattr(
            "app.agents.interviewer.InterviewerAgentAdapter.generate_next_question",
            AsyncMock(return_value=mock_question)
        )

        start_res = test_client.post(f"/api/v1/interviews/{session_id}/start")
        assert start_res.status_code == 200

        # Attempt to start again
        second_start = test_client.post(f"/api/v1/interviews/{session_id}/start")
        assert second_start.status_code == 400
        assert second_start.json()["detail"]["code"] == "INVALID_STATE"

    def test_start_interview_groq_auth_error_returns_503(self, test_client, monkeypatch):
        """Groq authentication failure returns 503 AI_NOT_CONFIGURED."""
        res = test_client.post("/api/v1/interviews", json={
            "job_description": {
                "field": "software_engineering",
                "custom_field_name": "",
                "title": "Backend Dev",
                "description": "A" * 60,
                "competencies": [{"name": "Python", "description": "Python knowledge"}]
            }
        })
        session_id = res.json()["session_id"]

        import httpx
        import groq
        from unittest.mock import AsyncMock
        req = httpx.Request("POST", "https://api.groq.com")
        resp = httpx.Response(401, request=req)
        monkeypatch.setattr(
            "app.agents.interviewer.InterviewerAgentAdapter.generate_next_question",
            AsyncMock(side_effect=groq.AuthenticationError("Invalid API Key", response=resp, body=None))
        )

        start_res = test_client.post(f"/api/v1/interviews/{session_id}/start")
        assert start_res.status_code == 503
        data = start_res.json()
        assert data["detail"]["code"] == "AI_NOT_CONFIGURED"

    def test_start_interview_groq_rate_limit_returns_429(self, test_client, monkeypatch):
        """Groq rate limit returns 429 AI_RATE_LIMIT."""
        res = test_client.post("/api/v1/interviews", json={
            "job_description": {
                "field": "software_engineering",
                "custom_field_name": "",
                "title": "Backend Dev",
                "description": "A" * 60,
                "competencies": [{"name": "Python", "description": "Python knowledge"}]
            }
        })
        session_id = res.json()["session_id"]

        import httpx
        import groq
        from unittest.mock import AsyncMock
        req = httpx.Request("POST", "https://api.groq.com")
        resp = httpx.Response(429, request=req)
        monkeypatch.setattr(
            "app.agents.interviewer.InterviewerAgentAdapter.generate_next_question",
            AsyncMock(side_effect=groq.RateLimitError("Rate limit exceeded", response=resp, body=None))
        )

        start_res = test_client.post(f"/api/v1/interviews/{session_id}/start")
        assert start_res.status_code == 429
        data = start_res.json()
        assert data["detail"]["code"] == "AI_RATE_LIMIT"

    def test_start_interview_groq_connection_error_returns_503(self, test_client, monkeypatch):
        """Groq connection error returns 503 AI_UNAVAILABLE."""
        res = test_client.post("/api/v1/interviews", json={
            "job_description": {
                "field": "software_engineering",
                "custom_field_name": "",
                "title": "Backend Dev",
                "description": "A" * 60,
                "competencies": [{"name": "Python", "description": "Python knowledge"}]
            }
        })
        session_id = res.json()["session_id"]

        import httpx
        import groq
        from unittest.mock import AsyncMock
        req = httpx.Request("POST", "https://api.groq.com")
        monkeypatch.setattr(
            "app.agents.interviewer.InterviewerAgentAdapter.generate_next_question",
            AsyncMock(side_effect=groq.APIConnectionError(request=req))
        )

        start_res = test_client.post(f"/api/v1/interviews/{session_id}/start")
        assert start_res.status_code == 503
        data = start_res.json()
        assert data["detail"]["code"] == "AI_UNAVAILABLE"

    def test_start_interview_groq_model_not_found_returns_502(self, test_client, monkeypatch):
        """Groq model not found error returns 502 AI_MODEL_NOT_FOUND."""
        res = test_client.post("/api/v1/interviews", json={
            "job_description": {
                "field": "software_engineering",
                "custom_field_name": "",
                "title": "Backend Dev",
                "description": "A" * 60,
                "competencies": [{"name": "Python", "description": "Python knowledge"}]
            }
        })
        session_id = res.json()["session_id"]

        import httpx
        import groq
        from unittest.mock import AsyncMock
        req = httpx.Request("POST", "https://api.groq.com")
        resp = httpx.Response(404, request=req)
        monkeypatch.setattr(
            "app.agents.interviewer.InterviewerAgentAdapter.generate_next_question",
            AsyncMock(side_effect=groq.NotFoundError("Model not found", response=resp, body=None))
        )

        start_res = test_client.post(f"/api/v1/interviews/{session_id}/start")
        assert start_res.status_code == 502
        data = start_res.json()
        assert data["detail"]["code"] == "AI_MODEL_NOT_FOUND"

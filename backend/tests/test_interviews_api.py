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

    def test_submit_answer_rest_endpoint_success(self, test_client, monkeypatch):
        """POST /api/v1/interviews/{session_id}/answer submits an answer and returns next question."""
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
        from unittest.mock import AsyncMock

        mock_q1 = NextQuestion(
            question_text="Q1: Tell me about Python.",
            rationale="Rationale 1",
            competency_targeted="Python",
            is_followup=False,
            expected_good_answer_elements=["basics"]
        )
        monkeypatch.setattr(
            "app.agents.interviewer.InterviewerAgentAdapter.generate_next_question",
            AsyncMock(return_value=mock_q1)
        )
        test_client.post(f"/api/v1/interviews/{session_id}/start")

        # Now submit answer via REST
        mock_q2 = NextQuestion(
            question_text="Q2: How do generators work?",
            rationale="Rationale 2",
            competency_targeted="Python",
            is_followup=False,
            expected_good_answer_elements=["yield"]
        )
        monkeypatch.setattr(
            "app.agents.interviewer.InterviewerAgentAdapter.generate_next_question",
            AsyncMock(return_value=mock_q2)
        )

        ans_res = test_client.post(f"/api/v1/interviews/{session_id}/answer", json={
            "answer": "Python is a dynamic interpreted language with clean syntax."
        })
        assert ans_res.status_code == 200
        data = ans_res.json()
        assert data["questions_asked"] == 2
        assert len(data["transcript"]) == 3  # Q1, A1, Q2
        assert data["transcript"][1]["content"] == "Python is a dynamic interpreted language with clean syntax."
        assert data["transcript"][2]["content"] == "Q2: How do generators work?"

    def test_submit_empty_answer_rejected(self, test_client, monkeypatch):
        """Empty or whitespace-only answer returns 400."""
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
        from unittest.mock import AsyncMock

        mock_q = NextQuestion(
            question_text="Q1",
            rationale="R1",
            competency_targeted="Python",
            is_followup=False,
            expected_good_answer_elements=["a"]
        )
        monkeypatch.setattr(
            "app.agents.interviewer.InterviewerAgentAdapter.generate_next_question",
            AsyncMock(return_value=mock_q)
        )
        test_client.post(f"/api/v1/interviews/{session_id}/start")

        # Empty answer
        ans_res = test_client.post(f"/api/v1/interviews/{session_id}/answer", json={"answer": "   "})
        assert ans_res.status_code == 400
        assert ans_res.json()["detail"]["code"] == "ORCHESTRATOR_ERROR"

    def test_log_proctoring_event_api(self, test_client):
        """POST /api/v1/interviews/{session_id}/events logs events atomically."""
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

        ev_res = test_client.post(f"/api/v1/interviews/{session_id}/events", json={
            "event_type": "tab_switch",
            "details": "User switched tabs"
        })
        assert ev_res.status_code == 200
        assert ev_res.json() == {"status": "logged"}

        # Verify event appears in session
        get_res = test_client.get(f"/api/v1/interviews/{session_id}")
        assert get_res.status_code == 200
        events = get_res.json()["proctoring_events"]
        assert len(events) == 1
        assert events[0]["event_type"] == "tab_switch"

    def test_submit_answer_rest_idempotent_with_last_question(self, test_client, monkeypatch):
        """Resubmitting an answer with last_question for an already-advanced question is idempotent."""
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
        from unittest.mock import AsyncMock

        mock_q1 = NextQuestion(
            question_text="Q1: Tell me about Python.",
            rationale="R1", competency_targeted="Python", is_followup=False,
            expected_good_answer_elements=["basics"]
        )
        mock_q2 = NextQuestion(
            question_text="Q2: What is asyncio?",
            rationale="R2", competency_targeted="Python", is_followup=False,
            expected_good_answer_elements=["event loop"]
        )
        monkeypatch.setattr(
            "app.agents.interviewer.InterviewerAgentAdapter.generate_next_question",
            AsyncMock(side_effect=[mock_q1, mock_q2])
        )
        test_client.post(f"/api/v1/interviews/{session_id}/start")

        # Submit answer to Q1
        first_res = test_client.post(f"/api/v1/interviews/{session_id}/answer", json={
            "answer": "I have 5 years experience.",
            "last_question": "Q1: Tell me about Python."
        })
        assert first_res.status_code == 200
        assert first_res.json()["questions_asked"] == 2
        assert len(first_res.json()["transcript"]) == 3

        # Resubmit duplicate answer to Q1 (e.g. client fallback / retry)
        dup_res = test_client.post(f"/api/v1/interviews/{session_id}/answer", json={
            "answer": "I have 5 years experience.",
            "last_question": "Q1: Tell me about Python."
        })
        assert dup_res.status_code == 200
        # Transcript and question count must NOT increase
        assert dup_res.json()["questions_asked"] == 2
        assert len(dup_res.json()["transcript"]) == 3
        assert dup_res.json()["transcript"][-1]["content"] == "Q2: What is asyncio?"

    def _create_completed_session(self, test_client, monkeypatch):
        """Helper to create a session and advance it through questions to COMPLETED."""
        res = test_client.post("/api/v1/interviews", json={
            "job_description": {
                "field": "software_engineering",
                "custom_field_name": "",
                "title": "Backend Dev",
                "description": "A" * 60,
                "competencies": [{"name": "Python", "description": "Python knowledge"}]
            },
            "settings": {"max_questions": 3}
        })
        session_id = res.json()["session_id"]
        from app.schemas.agent_outputs import NextQuestion
        from unittest.mock import AsyncMock

        mock_q = NextQuestion(
            question_text="Q: Tell me about your experience.",
            rationale="R", competency_targeted="Python", is_followup=False,
            expected_good_answer_elements=["basics"]
        )
        monkeypatch.setattr(
            "app.agents.interviewer.InterviewerAgentAdapter.generate_next_question",
            AsyncMock(return_value=mock_q)
        )
        test_client.post(f"/api/v1/interviews/{session_id}/start")
        test_client.post(f"/api/v1/interviews/{session_id}/answer", json={"answer": "Ans 1"})
        test_client.post(f"/api/v1/interviews/{session_id}/answer", json={"answer": "Ans 2"})
        last_res = test_client.post(f"/api/v1/interviews/{session_id}/answer", json={"answer": "Ans 3"})
        assert last_res.json()["status"] == "COMPLETED"
        return session_id

    def test_evaluate_interview_success(self, test_client, monkeypatch):
        """Evaluating a completed interview returns 200 and transitions to REPORT_READY."""
        session_id = self._create_completed_session(test_client, monkeypatch)

        from app.schemas.agent_outputs import EvaluationReport, CompetencyEvaluation
        from unittest.mock import AsyncMock

        mock_report = EvaluationReport(
            competency_evaluations=[
                CompetencyEvaluation(
                    competency_name="Python",
                    score=4,
                    rationale="Demonstrated solid comprehension.",
                    evidence_excerpts=['Candidate: "Ans 1"'],
                    missing_evidence=""
                )
            ],
            strengths=["Consistent Python answers."],
            areas_for_improvement=["Could elaborate on system design."],
            questions_for_human_reviewer=["Ask about GIL architecture."]
        )
        monkeypatch.setattr(
            "app.agents.evaluator.EvaluatorAgentAdapter.generate_evaluation",
            AsyncMock(return_value=mock_report)
        )

        res = test_client.post(f"/api/v1/interviews/{session_id}/evaluate")
        assert res.status_code == 200
        data = res.json()
        assert len(data["competency_evaluations"]) == 1
        assert data["competency_evaluations"][0]["competency_name"] == "Python"
        assert data["competency_evaluations"][0]["score"] == 4

        # Verify session state in backend
        session_res = test_client.get(f"/api/v1/interviews/{session_id}")
        assert session_res.json()["status"] == "REPORT_READY"

    def test_evaluate_interview_repeated_requests_idempotent(self, test_client, monkeypatch):
        """Subsequent evaluate calls return cached report without re-running evaluation agent."""
        session_id = self._create_completed_session(test_client, monkeypatch)

        from app.schemas.agent_outputs import EvaluationReport, CompetencyEvaluation
        from unittest.mock import AsyncMock

        mock_report = EvaluationReport(
            competency_evaluations=[
                CompetencyEvaluation(
                    competency_name="Python",
                    score=5,
                    rationale="Flawless answers.",
                    evidence_excerpts=[],
                    missing_evidence=""
                )
            ],
            strengths=["Python master"],
            areas_for_improvement=[],
            questions_for_human_reviewer=[]
        )
        mock_eval = AsyncMock(return_value=mock_report)
        monkeypatch.setattr(
            "app.agents.evaluator.EvaluatorAgentAdapter.generate_evaluation",
            mock_eval
        )

        first_res = test_client.post(f"/api/v1/interviews/{session_id}/evaluate")
        assert first_res.status_code == 200
        assert mock_eval.call_count == 1

        # Second evaluate call
        second_res = test_client.post(f"/api/v1/interviews/{session_id}/evaluate")
        assert second_res.status_code == 200
        assert second_res.json()["competency_evaluations"][0]["score"] == 5
        # Must NOT have called the evaluator agent again
        assert mock_eval.call_count == 1

    def test_evaluate_interview_groq_api_failure_preserves_completed_status(self, test_client, monkeypatch):
        """Groq API failure returns 503 and leaves session in COMPLETED so it can be retried."""
        session_id = self._create_completed_session(test_client, monkeypatch)

        import httpx
        import groq
        from unittest.mock import AsyncMock

        req = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
        mock_eval = AsyncMock(side_effect=groq.APIConnectionError(request=req))
        monkeypatch.setattr(
            "app.agents.evaluator.EvaluatorAgentAdapter.generate_evaluation",
            mock_eval
        )

        err_res = test_client.post(f"/api/v1/interviews/{session_id}/evaluate")
        assert err_res.status_code == 503
        assert err_res.json()["detail"]["code"] == "AI_UNAVAILABLE"

        # Crucial check: session must NOT be bricked into FAILED; it must remain COMPLETED for retry
        session_res = test_client.get(f"/api/v1/interviews/{session_id}")
        assert session_res.json()["status"] == "COMPLETED"

        # Now simulate a retry succeeding
        from app.schemas.agent_outputs import EvaluationReport, CompetencyEvaluation
        mock_eval.side_effect = None
        mock_eval.return_value = EvaluationReport(
            competency_evaluations=[
                CompetencyEvaluation(
                    competency_name="Python", score=4, rationale="Good", evidence_excerpts=[]
                )
            ]
        )
        retry_res = test_client.post(f"/api/v1/interviews/{session_id}/evaluate")
        assert retry_res.status_code == 200
        assert test_client.get(f"/api/v1/interviews/{session_id}").json()["status"] == "REPORT_READY"

    def test_evaluate_interview_malformed_model_output(self, test_client, monkeypatch):
        """Malformed LLM JSON output returns 502 AI_INVALID_OUTPUT and preserves COMPLETED."""
        session_id = self._create_completed_session(test_client, monkeypatch)

        import json
        from unittest.mock import AsyncMock

        mock_eval = AsyncMock(side_effect=json.JSONDecodeError("Invalid JSON from LLM", "", 0))
        monkeypatch.setattr(
            "app.agents.evaluator.EvaluatorAgentAdapter.generate_evaluation",
            mock_eval
        )

        res = test_client.post(f"/api/v1/interviews/{session_id}/evaluate")
        assert res.status_code == 502
        assert res.json()["detail"]["code"] == "AI_INVALID_OUTPUT"

        # Session remains COMPLETED
        session_res = test_client.get(f"/api/v1/interviews/{session_id}")
        assert session_res.json()["status"] == "COMPLETED"

    def test_evaluate_interview_invalid_state(self, test_client):
        """Calling evaluate on a session that has not reached COMPLETED returns 400 INVALID_STATE."""
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
        # Session is CONFIGURED, not COMPLETED
        eval_res = test_client.post(f"/api/v1/interviews/{session_id}/evaluate")
        assert eval_res.status_code == 400
        assert eval_res.json()["detail"]["code"] == "INVALID_STATE"

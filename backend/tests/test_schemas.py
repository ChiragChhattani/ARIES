"""
Tests for Pydantic schemas.

These tests verify that:
1. Valid data is accepted and parsed correctly
2. Invalid data produces clear validation errors
3. Enums constrain values to allowed sets
4. Default values and factories work
5. Custom validators run (e.g., rubric scale ordering)

TESTING PHILOSOPHY:
- Test the boundaries: What's the minimum valid input? Maximum?
- Test the happy path: Does a well-formed request parse correctly?
- Test the sad path: Does garbage input produce a helpful error?
"""

import pytest
from pydantic import ValidationError

from app.schemas.common import InterviewStatus, SessionType, WebSocketEventType, ProctoringEventType
from app.schemas.job import Competency, JobDescription
from app.schemas.rubric import RubricLevel, EvaluationRubric, get_default_rubric
from app.schemas.interview import (
    InterviewCreateRequest,
    InterviewSettings,
    InterviewSession,
    TranscriptEntry,
)


# ============================================================
# ENUM TESTS
# ============================================================

class TestEnums:
    """Test that enums contain expected values and serialize correctly."""

    def test_interview_status_values(self):
        """All 9 lifecycle states should exist."""
        assert len(InterviewStatus) == 9
        assert InterviewStatus.CREATED == "CREATED"
        assert InterviewStatus.REPORT_READY == "REPORT_READY"

    def test_session_type_values(self):
        """REAL and SIMULATED should be the only session types."""
        assert len(SessionType) == 2
        assert SessionType.REAL == "REAL"
        assert SessionType.SIMULATED == "SIMULATED"

    def test_websocket_event_types(self):
        """WebSocket events should include key lifecycle events."""
        assert WebSocketEventType.CONNECTION_ESTABLISHED == "connection_established"
        assert WebSocketEventType.QUESTION_GENERATED == "question_generated"
        assert WebSocketEventType.ERROR == "error"

    def test_proctoring_event_types(self):
        """Proctoring events should include tab_switch, window_blur, copy_paste_attempt, and camera/face events."""
        assert len(ProctoringEventType) == 6
        assert ProctoringEventType.tab_switch == "tab_switch"
        assert ProctoringEventType.window_blur == "window_blur"
        assert ProctoringEventType.copy_paste_attempt == "copy_paste_attempt"
        assert ProctoringEventType.face_missing == "face_missing"
        assert ProctoringEventType.multiple_faces == "multiple_faces"
        assert ProctoringEventType.camera_disconnected == "camera_disconnected"


# ============================================================
# COMPETENCY TESTS
# ============================================================

class TestCompetency:
    """Test competency validation."""

    def test_valid_competency(self):
        c = Competency(
            name="Problem Solving",
            description="Ability to break down complex problems into smaller parts",
        )
        assert c.name == "Problem Solving"
        assert c.weight == 1.0  # Default
        assert c.required is True  # Default

    def test_competency_name_too_short(self):
        with pytest.raises(ValidationError) as exc_info:
            Competency(name="X", description="A" * 10)
        assert "String should have at least 2 characters" in str(exc_info.value)

    def test_competency_weight_bounds(self):
        """Weight must be between 0.1 and 5.0."""
        with pytest.raises(ValidationError):
            Competency(name="Test", description="A" * 10, weight=0.05)
        with pytest.raises(ValidationError):
            Competency(name="Test", description="A" * 10, weight=6.0)

    def test_competency_with_sample_questions(self):
        c = Competency(
            name="System Design",
            description="Ability to design scalable systems",
            sample_questions=["Design a URL shortener"],
        )
        assert len(c.sample_questions) == 1


# ============================================================
# JOB DESCRIPTION TESTS
# ============================================================

class TestJobDescription:
    """Test job description validation."""

    def test_valid_job_description(self):
        jd = JobDescription(
            title="Senior Backend Engineer",
            description="We are looking for a senior backend engineer " * 5,
            competencies=[
                Competency(name="Python", description="Strong Python programming skills"),
            ],
        )
        assert jd.title == "Senior Backend Engineer"

    def test_job_description_requires_competencies(self):
        """At least one competency is required."""
        with pytest.raises(ValidationError):
            JobDescription(
                title="Test",
                description="A" * 50,
                competencies=[],
            )

    def test_job_description_short_description(self):
        """Description must be at least 50 characters."""
        with pytest.raises(ValidationError):
            JobDescription(
                title="Test",
                description="Too short",
                competencies=[
                    Competency(name="Test", description="A" * 10),
                ],
            )


# ============================================================
# RUBRIC TESTS
# ============================================================

class TestRubric:
    """Test evaluation rubric validation."""

    def test_default_rubric(self):
        """The default rubric should be a valid 5-point scale."""
        rubric = get_default_rubric()
        assert len(rubric.scale) == 5
        assert rubric.scale[0].score == 1
        assert rubric.scale[-1].score == 5
        assert rubric.version == "1.0"

    def test_rubric_scale_must_be_sorted(self):
        """Scale scores must be in ascending order."""
        with pytest.raises(ValidationError, match="sorted"):
            EvaluationRubric(
                scale=[
                    RubricLevel(score=3, label="Mid", description="A" * 10 + " medium"),
                    RubricLevel(score=1, label="Low", description="A" * 10 + " lowest"),
                    RubricLevel(score=5, label="High", description="A" * 10 + " highest"),
                ],
            )

    def test_rubric_scale_unique_scores(self):
        """Duplicate scores should be rejected."""
        with pytest.raises(ValidationError, match="unique"):
            EvaluationRubric(
                scale=[
                    RubricLevel(score=1, label="Low", description="A" * 10 + " lowest"),
                    RubricLevel(score=1, label="Also Low", description="A" * 10 + " also low"),
                    RubricLevel(score=3, label="High", description="A" * 10 + " highest"),
                ],
            )

    def test_rubric_minimum_scale_levels(self):
        """Rubric needs at least 3 levels."""
        with pytest.raises(ValidationError):
            EvaluationRubric(
                scale=[
                    RubricLevel(score=1, label="Bad", description="A" * 10 + " bad"),
                    RubricLevel(score=5, label="Good", description="A" * 10 + " good"),
                ],
            )


# ============================================================
# INTERVIEW SESSION TESTS
# ============================================================

class TestInterviewSession:
    """Test interview session models."""

    def _make_job_description(self) -> JobDescription:
        """Helper to create a valid job description."""
        return JobDescription(
            title="Software Engineer",
            description="Looking for a software engineer with strong coding skills " * 4,
            competencies=[
                Competency(name="Coding", description="Strong programming fundamentals"),
                Competency(name="Design", description="Software design and architecture skills"),
            ],
        )

    def test_session_creation_defaults(self):
        """A new session should have sensible defaults."""
        session = InterviewSession(job_description=self._make_job_description())
        assert session.status == InterviewStatus.CREATED
        assert session.session_type == SessionType.REAL
        assert session.questions_asked == 0
        assert len(session.session_id) > 0  # UUID generated
        assert session.transcript == []

    def test_session_id_unique(self):
        """Each session should get a unique ID."""
        jd = self._make_job_description()
        s1 = InterviewSession(job_description=jd)
        s2 = InterviewSession(job_description=jd)
        assert s1.session_id != s2.session_id

    def test_interview_settings_defaults(self):
        """Default settings should match our configured defaults."""
        settings = InterviewSettings()
        assert settings.max_questions == 10
        assert settings.timeout_minutes == 45
        assert settings.allow_followups is True

    def test_interview_settings_validation(self):
        """Settings should reject out-of-range values."""
        with pytest.raises(ValidationError):
            InterviewSettings(max_questions=100)
        with pytest.raises(ValidationError):
            InterviewSettings(timeout_minutes=1)


class TestInterviewCreateRequest:
    """Test the API request model for creating interviews."""

    def test_valid_create_request(self):
        request = InterviewCreateRequest(
            job_description=JobDescription(
                title="Data Scientist",
                description="We need a data scientist who can build ML models and analyze data " * 3,
                competencies=[
                    Competency(name="Machine Learning", description="ML model development and deployment"),
                ],
            ),
        )
        assert request.rubric is None  # Will use default
        assert request.settings.session_type == SessionType.REAL

    def test_create_request_with_custom_rubric(self):
        request = InterviewCreateRequest(
            job_description=JobDescription(
                title="Data Scientist",
                description="We need a data scientist who can build ML models and analyze data " * 3,
                competencies=[
                    Competency(name="ML", description="Machine learning skills"),
                ],
            ),
            rubric=get_default_rubric(),
        )
        assert request.rubric is not None
        assert len(request.rubric.scale) == 5


class TestTranscriptEntry:
    """Test transcript entry validation."""

    def test_valid_entry(self):
        entry = TranscriptEntry(
            speaker="interviewer",
            content="Tell me about your experience with Python.",
        )
        assert entry.speaker == "interviewer"
        assert entry.timestamp is not None

    def test_empty_content_rejected(self):
        with pytest.raises(ValidationError):
            TranscriptEntry(speaker="candidate", content="")


# ============================================================
# NEW INTERVIEW FIELD TESTS
# ============================================================

from app.schemas.job import InterviewField, ExperienceLevel, DifficultyLevel

class TestInterviewFieldSchema:
    """Test the new InterviewField and related enum fields on JobDescription."""

    def _make_base_job(self) -> dict:
        return {
            "title": "Quantum Engineer",
            "description": "Looking for a quantum computing expert who can write Q# code and understand physics.",
            "competencies": [
                {"name": "Quantum Logic", "description": "Understanding of qubits and logic gates"}
            ]
        }

    def test_field_default_is_software_engineering(self):
        jd = JobDescription(**self._make_base_job())
        assert jd.field == InterviewField.SOFTWARE_ENGINEERING

    def test_custom_field_requires_name(self):
        data = self._make_base_job()
        data["field"] = InterviewField.CUSTOM
        data["custom_field_name"] = "   "
        with pytest.raises(ValidationError, match="custom_field_name is required"):
            JobDescription(**data)

    def test_custom_field_with_name_works(self):
        data = self._make_base_job()
        data["field"] = InterviewField.CUSTOM
        data["custom_field_name"] = "Quantum Computing"
        jd = JobDescription(**data)
        assert jd.field == InterviewField.CUSTOM
        assert jd.custom_field_name == "Quantum Computing"

    def test_experience_level_enum(self):
        assert len(ExperienceLevel) == 4
        assert ExperienceLevel.FRESHER == "fresher"
        assert ExperienceLevel.SENIOR == "senior"

    def test_difficulty_level_enum(self):
        assert len(DifficultyLevel) == 3
        assert DifficultyLevel.EASY == "easy"
        assert DifficultyLevel.HARD == "hard"

    def test_known_field_works(self):
        data = self._make_base_job()
        data["field"] = InterviewField.GENERATIVE_AI
        jd = JobDescription(**data)
        assert jd.field == InterviewField.GENERATIVE_AI

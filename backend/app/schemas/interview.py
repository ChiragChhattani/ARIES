"""
Interview session schemas — request, response, and internal models.

These schemas define the data contracts for creating, managing,
and inspecting interview sessions through the API.

SEPARATION OF CONCERNS:
- InterviewCreateRequest: What the API caller sends (no server-generated fields)
- InterviewSettings: Configuration knobs for the interview
- InterviewSession: Full internal representation (includes server-generated fields)
- InterviewResponse: What the API returns (may omit internal details)
- TranscriptEntry: A single line in the interview conversation
"""

from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, Field

from .common import InterviewStatus, InterviewStage, SessionType, ProctoringEventType
from .job import JobDescription
from .rubric import EvaluationRubric, get_default_rubric
from .agent_outputs import EvaluationReport


class InterviewSettings(BaseModel):
    """
    Configuration for how the interview should be conducted.

    These are knobs the user can adjust, with sensible defaults.
    """
    max_questions: int = Field(
        default=10,
        ge=3,
        le=50,
        description="Maximum number of questions to ask",
    )
    timeout_minutes: int = Field(
        default=45,
        ge=5,
        le=180,
        description="Maximum interview duration in minutes",
    )
    allow_followups: bool = Field(
        default=True,
        description="Whether the interviewer can ask follow-up questions",
    )
    max_followups_per_question: int = Field(
        default=2,
        ge=0,
        le=5,
        description="Maximum follow-up questions per main question",
    )
    session_type: SessionType = Field(
        default=SessionType.REAL,
        description="REAL for human candidates, SIMULATED for testing",
    )


class InterviewCreateRequest(BaseModel):
    """
    Request body for POST /api/v1/interviews.

    This is what the frontend sends when creating a new interview.
    The server generates session_id, timestamps, and status.
    """
    job_description: JobDescription
    rubric: EvaluationRubric | None = Field(
        default=None,
        description="Custom evaluation rubric. If not provided, the default 5-point rubric is used.",
    )
    settings: InterviewSettings = Field(
        default_factory=InterviewSettings,
        description="Interview configuration. Defaults are used if not specified.",
    )
    candidate_identifier: str = Field(
        default="",
        max_length=100,
        description="Optional pseudonymous candidate reference. Do NOT use real names or PII.",
    )


class TranscriptEntry(BaseModel):
    """
    A single entry in the interview transcript.

    Records who said what, when, and in response to which question.
    """
    speaker: str = Field(description="Who spoke: 'interviewer', 'candidate', or 'system'")
    content: str = Field(
        min_length=1,
        max_length=10000,
        description="What was said",
    )
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    question_id: str = Field(
        default="",
        description="Links this entry to a specific question (for evidence tracking)",
    )
    stage: InterviewStage = Field(
        default=InterviewStage.CORE,
        description="Which interview stage this belongs to",
    )


class ProctoringEvent(BaseModel):
    """Records a proctoring event during the interview."""
    event_type: ProctoringEventType
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    details: str = ""


class InterviewSession(BaseModel):
    """
    Full internal representation of an interview session.

    This is the authoritative state — not the LLM's conversation history.
    All decisions about "where are we in the interview" come from this model.
    """
    session_id: str = Field(default_factory=lambda: str(uuid4()))
    status: InterviewStatus = Field(default=InterviewStatus.CREATED)
    session_type: SessionType = Field(default=SessionType.REAL)

    # Configuration
    job_description: JobDescription
    rubric: EvaluationRubric = Field(default_factory=get_default_rubric)
    settings: InterviewSettings = Field(default_factory=InterviewSettings)
    candidate_identifier: str = ""

    # Interview state
    current_stage: InterviewStage = Field(default=InterviewStage.INTRODUCTION)
    current_question_index: int = Field(default=0)
    questions_asked: int = Field(default=0)
    followups_asked_for_current: int = Field(default=0)
    competencies_covered: list[str] = Field(default_factory=list)

    # Transcript
    transcript: list[TranscriptEntry] = Field(default_factory=list)

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    completed_at: datetime | None = None

    # Metadata
    rubric_version: str = "1.0"
    proctoring_events: list[ProctoringEvent] = Field(default_factory=list)
    
    # Final Result
    evaluation_report: EvaluationReport | None = None


class InterviewResponse(BaseModel):
    """
    API response for interview session data.

    This is what the frontend receives. It includes everything
    needed to display the session but omits internal-only fields.
    """
    session_id: str
    status: InterviewStatus
    session_type: SessionType
    job_title: str
    candidate_identifier: str
    questions_asked: int
    current_stage: InterviewStage
    competencies_covered: list[str]
    max_questions: int
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    
    # Allow fetching the transcript and report if available
    transcript: list[TranscriptEntry] = Field(default_factory=list)
    proctoring_events: list[ProctoringEvent] = Field(default_factory=list)
    evaluation_report: dict | None = None


class InterviewListResponse(BaseModel):
    """Response for listing multiple interviews."""
    sessions: list[InterviewResponse]
    total: int

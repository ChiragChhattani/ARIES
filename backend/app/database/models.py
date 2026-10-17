"""
SQLAlchemy database models.

We use a hybrid approach for storing interview sessions:
- Queryable fields (status, candidate_identifier) are standard SQL columns.
- Deeply nested objects (transcript, job description) are stored as JSON.
This prevents us from needing 7+ joined tables just to load one interview,
while still allowing us to query by status or date.
"""

from datetime import datetime, timezone
import json
from typing import Any

from sqlalchemy import String, DateTime, Enum, JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.schemas.common import InterviewStatus, SessionType, InterviewStage


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""
    pass


class InterviewRecord(Base):
    """
    Database representation of an Interview Session.
    
    This is intentionally separate from the Pydantic InterviewSession.
    The Repository layer handles converting between the two.
    """
    __tablename__ = "interview_sessions"

    # Indexed/Queryable columns
    session_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    status: Mapped[InterviewStatus] = mapped_column(Enum(InterviewStatus), index=True)
    session_type: Mapped[SessionType] = mapped_column(Enum(SessionType))
    candidate_identifier: Mapped[str] = mapped_column(String(100), default="", index=True)
    
    # State tracking
    current_stage: Mapped[InterviewStage] = mapped_column(Enum(InterviewStage))
    current_question_index: Mapped[int] = mapped_column(default=0)
    questions_asked: Mapped[int] = mapped_column(default=0)
    followups_asked_for_current: Mapped[int] = mapped_column(default=0)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # JSON Document columns for complex nested structures
    job_description: Mapped[dict[str, Any]] = mapped_column(JSON)
    rubric: Mapped[dict[str, Any]] = mapped_column(JSON)
    settings: Mapped[dict[str, Any]] = mapped_column(JSON)
    competencies_covered: Mapped[list[str]] = mapped_column(JSON, default=list)
    transcript: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    proctoring_events: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    
    # Optional final report
    evaluation_report: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

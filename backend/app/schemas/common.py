"""
Common schemas shared across the application.

Contains enums, base models, and reusable types.
These are the "vocabulary" of the application — every component
speaks the same language by importing from here.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


# ============================================================
# ENUMS — Finite sets of allowed values
# ============================================================

class InterviewStatus(str, Enum):
    """
    Interview lifecycle states. Implements a state machine.

    Why str, Enum? By inheriting from str, these values serialize
    to JSON as strings ("CREATED", not 0) — much more debuggable.

    State transitions (defined in state_machine.py in Phase 3):
        CREATED → CONFIGURED → IN_PROGRESS → COMPLETED → EVALUATING → REPORT_READY
                                    ↓              ↑
                                  PAUSED ──────────┘
        Any state → FAILED
        Any state (except REPORT_READY) → CANCELLED
    """
    CREATED = "CREATED"
    CONFIGURED = "CONFIGURED"
    IN_PROGRESS = "IN_PROGRESS"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    EVALUATING = "EVALUATING"
    REPORT_READY = "REPORT_READY"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class SessionType(str, Enum):
    """Distinguishes real interviews from simulated test sessions."""
    REAL = "REAL"
    SIMULATED = "SIMULATED"


class InterviewStage(str, Enum):
    """Progression stages within an interview."""
    INTRODUCTION = "INTRODUCTION"
    WARMUP = "WARMUP"
    CORE = "CORE"
    DEEP_DIVE = "DEEP_DIVE"
    CLOSING = "CLOSING"


class WebSocketEventType(str, Enum):
    """Types of real-time events sent over WebSocket."""
    CONNECTION_ESTABLISHED = "connection_established"
    STATUS_UPDATED = "status_updated"
    QUESTION_GENERATED = "question_generated"
    ANSWER_RECEIVED = "answer_received"
    PROCESSING_STARTED = "processing_started"
    FOLLOWUP_GENERATED = "followup_generated"
    INTERVIEW_PAUSED = "interview_paused"
    INTERVIEW_RESUMED = "interview_resumed"
    INTERVIEW_COMPLETED = "interview_completed"
    EVALUATION_STARTED = "evaluation_started"
    REPORT_READY = "report_ready"
    ERROR = "error"


class ProctoringEventType(str, Enum):
    """Types of proctoring events detected during the interview."""
    tab_switch = "tab_switch"
    window_blur = "window_blur"
    copy_paste_attempt = "copy_paste_attempt"
    face_missing = "face_missing"
    multiple_faces = "multiple_faces"
    camera_disconnected = "camera_disconnected"


# ============================================================
# BASE MODELS — Shared patterns for all schemas
# ============================================================

class TimestampMixin(BaseModel):
    """Adds created_at and updated_at timestamps."""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class APIResponse(BaseModel):
    """Standard wrapper for all API responses."""
    success: bool = True
    message: str = "OK"
    data: Any = None


class ErrorResponse(BaseModel):
    """Standard error response format."""
    success: bool = False
    error_code: str = Field(description="Machine-readable error code")
    message: str = Field(description="Human-readable error description")
    details: dict[str, Any] | None = Field(
        default=None,
        description="Additional error context (validation errors, etc.)",
    )


class PaginatedResponse(BaseModel):
    """Wrapper for paginated list responses."""
    success: bool = True
    data: list[Any]
    total: int
    page: int = 1
    page_size: int = 20


# ============================================================
# WEBSOCKET EVENT — Base model for all WS messages
# ============================================================

class WebSocketEvent(BaseModel):
    """
    Base model for WebSocket messages.

    Every message sent over WebSocket has:
    - event_type: What happened (from WebSocketEventType enum)
    - session_id: Which interview session this relates to
    - timestamp: When the event occurred
    - payload: Event-specific data (different per event type)
    """
    event_type: WebSocketEventType
    session_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    payload: dict[str, Any] = Field(default_factory=dict)

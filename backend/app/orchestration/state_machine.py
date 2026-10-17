"""
Interview Lifecycle State Machine.

Enforces strict rules about what actions are allowed based on the
current state of the interview. This prevents race conditions and
corrupted states (e.g., trying to answer a question when the interview
is already completed).
"""

from app.schemas.common import InterviewStatus

class StateMachineError(Exception):
    """Raised when an invalid state transition is attempted."""
    pass


class InterviewStateMachine:
    """
    Rules engine for interview state transitions.
    
    Valid paths:
    CREATED -> CONFIGURED -> IN_PROGRESS -> COMPLETED -> EVALUATING -> REPORT_READY
    Any state (except REPORT_READY) -> CANCELLED
    Any state -> FAILED
    IN_PROGRESS <-> PAUSED
    """
    
    VALID_TRANSITIONS = {
        InterviewStatus.CREATED: {InterviewStatus.CONFIGURED, InterviewStatus.CANCELLED, InterviewStatus.FAILED},
        InterviewStatus.CONFIGURED: {InterviewStatus.IN_PROGRESS, InterviewStatus.CANCELLED, InterviewStatus.FAILED},
        InterviewStatus.IN_PROGRESS: {InterviewStatus.PAUSED, InterviewStatus.COMPLETED, InterviewStatus.CANCELLED, InterviewStatus.FAILED},
        InterviewStatus.PAUSED: {InterviewStatus.IN_PROGRESS, InterviewStatus.CANCELLED, InterviewStatus.FAILED},
        InterviewStatus.COMPLETED: {InterviewStatus.EVALUATING, InterviewStatus.CANCELLED, InterviewStatus.FAILED},
        InterviewStatus.EVALUATING: {InterviewStatus.REPORT_READY, InterviewStatus.FAILED},
        InterviewStatus.REPORT_READY: {InterviewStatus.FAILED}, # Terminal success state
        InterviewStatus.CANCELLED: set(), # Terminal state
        InterviewStatus.FAILED: set(),    # Terminal state
    }
    
    @classmethod
    def validate_transition(cls, current_status: InterviewStatus, new_status: InterviewStatus) -> None:
        """
        Validates if a transition is legal.
        
        Raises:
            StateMachineError: If the transition is not allowed.
        """
        if new_status not in cls.VALID_TRANSITIONS.get(current_status, set()):
            raise StateMachineError(
                f"Invalid state transition from {current_status.value} to {new_status.value}"
            )
            
    @classmethod
    def can_process_answer(cls, current_status: InterviewStatus) -> bool:
        """Helper to check if we can receive candidate answers right now."""
        return current_status == InterviewStatus.IN_PROGRESS

"""
The Orchestrator.

This is the central service layer of ARIES. It connects the Database (Repository),
the validation logic (State Machine), and the LLM wrappers (Agents).

No HTTP or WebSocket logic belongs here — this is pure business logic.
"""

from datetime import datetime, timezone
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.common import InterviewStatus
from app.schemas.interview import InterviewCreateRequest, InterviewSession, TranscriptEntry
from app.schemas.agent_outputs import EvaluationReport
from app.orchestration.state_machine import InterviewStateMachine, StateMachineError
from app.repositories.interview import InterviewRepository
from app.agents.interviewer import InterviewerAgentAdapter
from app.agents.evaluator import EvaluatorAgentAdapter
from app.observability.logging import get_logger
from app.utils.sanitization import sanitize_text, normalize_identifier
from app.memory.mem0_service import CandidateMemoryService

logger = get_logger(__name__)

class OrchestratorError(Exception):
    """Custom exception for orchestration failures."""
    pass


class InterviewOrchestrator:
    
    def __init__(self, db_session: AsyncSession):
        self.repo = InterviewRepository(db_session)
        
    async def create_interview(self, request: InterviewCreateRequest) -> InterviewSession:
        """Creates a new interview session."""
        
        logger.info("Creating new interview session")
        
        # Sanitize inputs to prevent payload bloat
        request.job_description.title = sanitize_text(request.job_description.title, max_length=200)
        request.job_description.description = sanitize_text(request.job_description.description, max_length=8000)
        request.candidate_identifier = normalize_identifier(request.candidate_identifier)
        
        session = InterviewSession(
            session_id=str(uuid.uuid4()),
            job_description=request.job_description,
            settings=request.settings,
            candidate_identifier=request.candidate_identifier,
        )
        
        if request.rubric:
            session.rubric = request.rubric
            
        # State machine transition (implicit CREATED -> CONFIGURED since we have the data)
        InterviewStateMachine.validate_transition(session.status, InterviewStatus.CONFIGURED)
        session.status = InterviewStatus.CONFIGURED
        
        return await self.repo.save(session)
        
    async def start_interview(self, session_id: str) -> InterviewSession:
        """Starts the interview and generates the first question."""
        
        session = await self.repo.get_by_id(session_id)
        if not session:
            raise OrchestratorError(f"Session {session_id} not found")
            
        InterviewStateMachine.validate_transition(session.status, InterviewStatus.IN_PROGRESS)
        
        logger.info(f"Starting interview {session_id}")
        session.status = InterviewStatus.IN_PROGRESS
        session.started_at = datetime.now(timezone.utc)
        
        # Generate the first question
        interviewer = InterviewerAgentAdapter(job=session.job_description)
        next_q = await interviewer.generate_next_question(
            transcript=session.transcript,
            questions_remaining=session.settings.max_questions
        )
        
        # Append question to transcript
        session.transcript.append(
            TranscriptEntry(
                speaker="interviewer",
                content=next_q.question_text,
                stage=session.current_stage
            )
        )
        session.questions_asked += 1
        
        return await self.repo.save(session)
        
    async def handle_candidate_answer(
        self, session_id: str, answer_text: str, client_last_question: str | None = None
    ) -> InterviewSession:
        """Processes a candidate's answer and generates the next move."""
        
        session = await self.repo.get_by_id(session_id)
        if not session:
            raise OrchestratorError(f"Session {session_id} not found")
            
        if not InterviewStateMachine.can_process_answer(session.status):
            raise StateMachineError(f"Cannot accept answers in state {session.status.value}")
            
        # Reject empty or whitespace-only answers without advancing the interview
        cleaned_answer = answer_text.strip() if answer_text else ""
        if not cleaned_answer:
            raise OrchestratorError("Candidate answer cannot be empty or whitespace.")

        # Guard against duplicate submission during disconnect / fallback:
        # If client specifies the question it was answering, check if the session has
        # already moved past it (e.g. earlier WebSocket request succeeded before disconnect).
        if client_last_question:
            current_q = None
            for entry in reversed(session.transcript):
                if entry.speaker == "interviewer":
                    current_q = entry.content
                    break
            if current_q and current_q.strip() != client_last_question.strip():
                logger.info(
                    f"Idempotent answer skipped for session {session_id}: "
                    f"client answered '{client_last_question[:40]}...', but session is at '{current_q[:40]}...'"
                )
                return session

        # Prevent duplicate candidate turn while previous turn is still pending
        if session.transcript and session.transcript[-1].speaker == "candidate":
            raise StateMachineError("A candidate answer has already been submitted and is currently being processed.")

        # 1. Save candidate answer
        session.transcript.append(
            TranscriptEntry(speaker="candidate", content=cleaned_answer, stage=session.current_stage)
        )
        
        # 2. Check if all allowed main questions have been asked and answered
        if session.questions_asked >= session.settings.max_questions:
            return await self._terminate_interview(session)

        # 3. Extract context for the LLM
        asked_questions = [entry.content for entry in session.transcript if entry.speaker == "interviewer"]
        followups_remaining = (
            session.settings.max_followups_per_question - session.followups_asked_for_current
            if session.settings.allow_followups else 0
        )

        # 4. Generate next question
        interviewer = InterviewerAgentAdapter(job=session.job_description)
        next_q = await interviewer.generate_next_question(
            transcript=session.transcript,
            questions_remaining=max(0, session.settings.max_questions - session.questions_asked),
            followups_remaining=followups_remaining,
            asked_questions=asked_questions
        )

        # Enforce follow-up constraints: if followups not allowed or exhausted, force is_followup=False
        if next_q.is_followup and (not session.settings.allow_followups or followups_remaining <= 0):
            next_q.is_followup = False

        # Guard against duplicate questions
        if any(next_q.question_text.strip().lower() == prev_q.strip().lower() for prev_q in asked_questions):
            logger.warning(f"Interviewer generated duplicate question: {next_q.question_text}. Adjusting.")
            uncovered = [c.name for c in session.job_description.competencies if c.name not in session.competencies_covered]
            comp_name = uncovered[0] if uncovered else (session.job_description.competencies[0].name if session.job_description.competencies else "General")
            next_q.question_text = f"Could you provide another specific example demonstrating your experience with {comp_name}?"
            next_q.competency_targeted = comp_name
            next_q.is_followup = False

        # If it's a main question and we are at max questions, terminate
        if not next_q.is_followup and session.questions_asked >= session.settings.max_questions:
            return await self._terminate_interview(session)

        # 5. Save interviewer response
        session.transcript.append(
            TranscriptEntry(speaker="interviewer", content=next_q.question_text, stage=session.current_stage)
        )

        if next_q.is_followup:
            session.followups_asked_for_current += 1
        else:
            session.questions_asked += 1
            session.followups_asked_for_current = 0
            if next_q.competency_targeted not in session.competencies_covered:
                session.competencies_covered.append(next_q.competency_targeted)

        return await self.repo.save(session)
        
    async def _terminate_interview(self, session: InterviewSession) -> InterviewSession:
        """Helper to mark an interview as completed."""
        logger.info(f"Max questions reached for {session.session_id}. Completing interview.")
        session.transcript.append(
            TranscriptEntry(speaker="interviewer", content="Thank you, that concludes our interview.", stage=session.current_stage)
        )
        InterviewStateMachine.validate_transition(session.status, InterviewStatus.COMPLETED)
        session.status = InterviewStatus.COMPLETED
        session.completed_at = datetime.now(timezone.utc)
        return await self.repo.save(session)
        
    async def evaluate_interview(self, session_id: str) -> EvaluationReport:
        """Runs the Evaluation Agent on a completed interview."""
        
        session = await self.repo.get_by_id(session_id)
        if not session:
            raise OrchestratorError(f"Session {session_id} not found")
            
        InterviewStateMachine.validate_transition(session.status, InterviewStatus.EVALUATING)
        session.status = InterviewStatus.EVALUATING
        await self.repo.save(session)
        
        logger.info(f"Evaluating interview {session_id}")
        
        try:
            evaluator = EvaluatorAgentAdapter(job=session.job_description, rubric=session.rubric)
            report = await evaluator.generate_evaluation(transcript=session.transcript)
            
            # Save the final state
            InterviewStateMachine.validate_transition(session.status, InterviewStatus.REPORT_READY)
            session.status = InterviewStatus.REPORT_READY
            session.evaluation_report = report
            await self.repo.save(session)
            
            # Fire and forget memory extraction if candidate is known
            if session.candidate_identifier and session.candidate_identifier != "Anonymous":
                try:
                    mem_service = CandidateMemoryService()
                    mem_service.extract_and_store_insights(session.candidate_identifier, session.transcript)
                except Exception as e:
                    logger.error(f"Mem0 extraction failed non-fatally: {e}")
            
            return report
            
        except Exception as e:
            # Handle failure
            logger.error(f"Evaluation failed: {e}")
            InterviewStateMachine.validate_transition(session.status, InterviewStatus.FAILED)
            session.status = InterviewStatus.FAILED
            await self.repo.save(session)
            raise

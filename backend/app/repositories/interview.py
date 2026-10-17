"""
Repository layer for Interview Sessions.

Isolates database access from business logic. The Orchestrator shouldn't
know about SQLAlchemy syntax or JSON serialization details.
"""

from typing import Sequence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import InterviewRecord
from app.schemas.interview import InterviewSession, ProctoringEvent

class InterviewRepository:
    """CRUD operations for Interview Sessions."""
    
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, session_id: str) -> InterviewSession | None:
        """Fetch an interview by ID and convert it to a Pydantic model."""
        stmt = select(InterviewRecord).where(InterviewRecord.session_id == session_id)
        result = await self.db.execute(stmt)
        record = result.scalar_one_or_none()
        
        if not record:
            return None
            
        return self._to_pydantic(record)

    async def save(self, session: InterviewSession) -> InterviewSession:
        """Save a Pydantic InterviewSession to the database."""
        # Check if it exists
        stmt = select(InterviewRecord).where(InterviewRecord.session_id == session.session_id)
        result = await self.db.execute(stmt)
        record = result.scalar_one_or_none()
        
        # Pydantic -> JSON dicts
        # mode="json" ensures datetimes and enums are serialized correctly
        job_json = session.job_description.model_dump(mode="json")
        rubric_json = session.rubric.model_dump(mode="json")
        settings_json = session.settings.model_dump(mode="json")
        transcript_json = [t.model_dump(mode="json") for t in session.transcript]
        eval_report_json = session.evaluation_report.model_dump(mode="json") if session.evaluation_report else None
        proctoring_events_json = [
            e.model_dump(mode="json") if hasattr(e, "model_dump") else e 
            for e in getattr(session, "proctoring_events", [])
        ]
        
        if not record:
            # Create new
            record = InterviewRecord(
                session_id=session.session_id,
                status=session.status,
                session_type=session.session_type,
                candidate_identifier=session.candidate_identifier,
                current_stage=session.current_stage,
                current_question_index=session.current_question_index,
                questions_asked=session.questions_asked,
                followups_asked_for_current=session.followups_asked_for_current,
                created_at=session.created_at,
                started_at=session.started_at,
                completed_at=session.completed_at,
                job_description=job_json,
                rubric=rubric_json,
                settings=settings_json,
                competencies_covered=session.competencies_covered,
                transcript=transcript_json,
                proctoring_events=proctoring_events_json,
                evaluation_report=eval_report_json
            )
            self.db.add(record)
        else:
            # Update existing
            record.status = session.status
            record.current_stage = session.current_stage
            record.current_question_index = session.current_question_index
            record.questions_asked = session.questions_asked
            record.followups_asked_for_current = session.followups_asked_for_current
            record.started_at = session.started_at
            record.completed_at = session.completed_at
            record.competencies_covered = session.competencies_covered
            record.transcript = transcript_json
            record.proctoring_events = proctoring_events_json
            record.evaluation_report = eval_report_json
            
        await self.db.flush() # Send SQL to DB but don't commit yet (let route handler commit)
        return session
        
    def _to_pydantic(self, record: InterviewRecord) -> InterviewSession:
        """Convert SQLAlchemy model back to Pydantic domain model."""
        raw_events = getattr(record, "proctoring_events", None) or []
        proctoring_events = [
            ProctoringEvent(**e) if isinstance(e, dict) else e 
            for e in raw_events
        ]
        return InterviewSession(
            session_id=record.session_id,
            status=record.status,
            session_type=record.session_type,
            candidate_identifier=record.candidate_identifier,
            current_stage=record.current_stage,
            current_question_index=record.current_question_index,
            questions_asked=record.questions_asked,
            followups_asked_for_current=record.followups_asked_for_current,
            created_at=record.created_at,
            updated_at=record.updated_at,
            started_at=record.started_at,
            completed_at=record.completed_at,
            job_description=record.job_description,
            rubric=record.rubric,
            settings=record.settings,
            competencies_covered=record.competencies_covered,
            transcript=record.transcript,
            proctoring_events=proctoring_events,
            evaluation_report=record.evaluation_report
        )

"""
REST API Routes for Interviews.

Exposes CRUD and action endpoints for the Orchestrator.
"""

import json
import logging
import openai

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

logger = logging.getLogger(__name__)

from app.database.engine import get_db_session
from app.database.models import InterviewRecord
from app.schemas.interview import (
    InterviewCreateRequest, 
    InterviewResponse, 
    InterviewListResponse,
    InterviewSession
)
from app.schemas.agent_outputs import EvaluationReport
from app.schemas.common import WebSocketEventType
from app.orchestration.orchestrator import InterviewOrchestrator, OrchestratorError
from app.orchestration.state_machine import StateMachineError
from app.api.websocket import manager

router = APIRouter(prefix="/api/v1/interviews", tags=["Interviews"])

def _to_response(session: InterviewSession) -> InterviewResponse:
    """Helper to convert internal session state to public API response."""
    return InterviewResponse(
        session_id=session.session_id,
        status=session.status,
        session_type=session.session_type,
        job_title=session.job_description.title,
        candidate_identifier=session.candidate_identifier,
        questions_asked=session.questions_asked,
        current_stage=session.current_stage,
        competencies_covered=session.competencies_covered,
        max_questions=session.settings.max_questions,
        created_at=session.created_at,
        updated_at=session.updated_at,
        started_at=session.started_at,
        completed_at=session.completed_at,
        transcript=session.transcript,
        proctoring_events=session.proctoring_events,
        evaluation_report=session.evaluation_report.model_dump() if session.evaluation_report else None,
    )

@router.post("", response_model=InterviewResponse, status_code=201)
async def create_interview(request: InterviewCreateRequest, db: AsyncSession = Depends(get_db_session)):
    """Create a new interview session."""
    orchestrator = InterviewOrchestrator(db)
    session = await orchestrator.create_interview(request)
    return _to_response(session)

@router.get("", response_model=InterviewListResponse)
async def list_interviews(db: AsyncSession = Depends(get_db_session)):
    """List all interviews (stub implementation for MVP)."""
    stmt = select(InterviewRecord).order_by(InterviewRecord.created_at.desc())
    result = await db.execute(stmt)
    records = result.scalars().all()
    
    # We cheat a bit here by doing manual conversion to avoid loading full Pydantic models for lists
    sessions = []
    for r in records:
        sessions.append(InterviewResponse(
            session_id=r.session_id,
            status=r.status,
            session_type=r.session_type,
            job_title=r.job_description.get("title", "Unknown Role"),
            candidate_identifier=r.candidate_identifier,
            questions_asked=r.questions_asked,
            current_stage=r.current_stage,
            competencies_covered=r.competencies_covered,
            max_questions=r.settings.get("max_questions", 10),
            created_at=r.created_at,
            updated_at=r.updated_at,
            started_at=r.started_at,
            completed_at=r.completed_at,
            transcript=[],
            evaluation_report=None
        ))
        
    return InterviewListResponse(sessions=sessions, total=len(sessions))

@router.get("/{session_id}", response_model=InterviewSession)
async def get_interview(session_id: str, db: AsyncSession = Depends(get_db_session)):
    """Get full details of a specific interview (including transcript)."""
    orchestrator = InterviewOrchestrator(db)
    session = await orchestrator.repo.get_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Interview not found")
    return session

@router.post("/{session_id}/start", response_model=InterviewResponse)
async def start_interview(session_id: str, db: AsyncSession = Depends(get_db_session)):
    """Start the interview and generate the first question."""
    try:
        orchestrator = InterviewOrchestrator(db)
        session = await orchestrator.start_interview(session_id)
        
        # Broadcast the new question to the UI
        last_question = session.transcript[-1].content
        await manager.send_event(session_id, WebSocketEventType.QUESTION_GENERATED, {"question": last_question})
        await manager.send_event(session_id, WebSocketEventType.STATUS_UPDATED, {"status": session.status})
        
        return _to_response(session)
    except openai.AuthenticationError as e:
        logger.exception("AI Authentication Error")
        raise HTTPException(status_code=503, detail={"code": "AI_NOT_CONFIGURED", "message": "The AI service is not configured. Please check the server configuration."})
    except openai.APITimeoutError as e:
        logger.exception("AI Timeout Error")
        raise HTTPException(status_code=504, detail={"code": "AI_TIMEOUT", "message": "The AI took too long to respond. Please try again."})
    except openai.RateLimitError as e:
        logger.exception("AI Rate Limit Error")
        raise HTTPException(status_code=429, detail={"code": "AI_RATE_LIMIT", "message": "AI rate limit exceeded. Please try again shortly."})
    except StateMachineError as e:
        logger.exception("State Machine Error")
        raise HTTPException(status_code=400, detail={"code": "INVALID_STATE", "message": str(e)})
    except OrchestratorError as e:
        logger.exception("Orchestrator Error")
        raise HTTPException(status_code=404, detail={"code": "SESSION_NOT_FOUND", "message": "This interview session does not exist or has expired."})
    except Exception as e:
        logger.exception("Server Error")
        raise HTTPException(status_code=500, detail={"code": "SERVER_ERROR", "message": "The interview could not be started. Please try again."})

@router.post("/{session_id}/evaluate", response_model=EvaluationReport)
async def evaluate_interview(session_id: str, db: AsyncSession = Depends(get_db_session)):
    """Run the evaluation agent on a completed interview."""
    try:
        # Broadcast to UI that evaluation is starting
        await manager.send_event(session_id, WebSocketEventType.EVALUATION_STARTED, {})
        
        orchestrator = InterviewOrchestrator(db)
        report = await orchestrator.evaluate_interview(session_id)
        
        # Broadcast that report is ready
        await manager.send_event(session_id, WebSocketEventType.REPORT_READY, {"report": report.model_dump()})
        await manager.send_event(session_id, WebSocketEventType.STATUS_UPDATED, {"status": "REPORT_READY"})
        
        return report
    except StateMachineError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except OrchestratorError as e:
        raise HTTPException(status_code=404, detail=str(e))

from app.schemas.interview import ProctoringEvent

@router.post("/{session_id}/events", response_model=dict)
async def log_proctoring_event(
    session_id: str, 
    event: ProctoringEvent, 
    db: AsyncSession = Depends(get_db_session)
):
    """Log a proctoring or anti-cheating event from the client."""
    orchestrator = InterviewOrchestrator(db)
    session = await orchestrator.repo.get_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Interview not found")
    
    session.proctoring_events.append(event)
    await orchestrator.repo.save(session)
    return {"status": "logged"}


# =====================================================================
# WEBSOCKET ROUTE
# =====================================================================

@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str, db: AsyncSession = Depends(get_db_session)):
    """
    WebSocket endpoint for live interview interaction.
    The client connects here, and sends JSON messages when the candidate answers.
    """
    await manager.connect(websocket, session_id)
    
    try:
        while True:
            # Wait for client to send a message (candidate answer)
            data = await websocket.receive_text()
            payload = json.loads(data)
            
            if payload.get("type") == "submit_answer":
                answer_text = payload.get("answer")
                
                # Notify UI we are processing
                await manager.send_event(session_id, WebSocketEventType.PROCESSING_STARTED, {})
                
                # Call orchestrator
                orchestrator = InterviewOrchestrator(db)
                try:
                    session = await orchestrator.handle_candidate_answer(session_id, answer_text)
                    
                    # Look at the last entry in the transcript
                    last_entry = session.transcript[-1]
                    
                    if session.status == "COMPLETED":
                        await manager.send_event(session_id, WebSocketEventType.INTERVIEW_COMPLETED, {"conclusion": last_entry.content})
                    else:
                        await manager.send_event(session_id, WebSocketEventType.QUESTION_GENERATED, {"question": last_entry.content})
                        
                    await manager.send_event(session_id, WebSocketEventType.STATUS_UPDATED, {"status": session.status})
                    
                    # We MUST commit the session manually here since WebSockets 
                    # don't trigger the typical FastAPI HTTP dependency teardown commit
                    await db.commit()
                    
                except StateMachineError as e:
                    await manager.send_event(session_id, WebSocketEventType.ERROR, {"message": str(e)})
                    await db.rollback()
                except OrchestratorError as e:
                    await manager.send_event(session_id, WebSocketEventType.ERROR, {"message": str(e)})
                    await db.rollback()
                except Exception as e:
                    await manager.send_event(session_id, WebSocketEventType.ERROR, {"message": "Internal processing error"})
                    await db.rollback()
                    
    except WebSocketDisconnect:
        manager.disconnect(session_id)

"""
Integration tests for the Orchestrator workflow.

We test the complete lifecycle:
CREATE -> START -> HANDLE ANSWERS -> COMPLETE -> EVALUATE
using a real SQLite database but mocked AI agents.
"""

import pytest
import pytest_asyncio
from unittest.mock import patch, AsyncMock
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.database.models import Base
from app.schemas.interview import InterviewCreateRequest, InterviewSettings, ProctoringEvent
from app.schemas.job import JobDescription, Competency
from app.schemas.common import InterviewStatus, ProctoringEventType
from app.orchestration.orchestrator import InterviewOrchestrator, OrchestratorError
from app.orchestration.state_machine import StateMachineError
from app.schemas.agent_outputs import NextQuestion, EvaluationReport, CompetencyEvaluation


# =================================================================
# FIXTURES (Real DB, Mocked AI)
# =================================================================

@pytest_asyncio.fixture
async def db_session():
    """Provides a fresh in-memory SQLite database for each test."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    
    async with session_factory() as session:
        yield session
        
    await engine.dispose()


@pytest.fixture
def create_request():
    return InterviewCreateRequest(
        job_description=JobDescription(
            title="Backend Dev",
            description="Looking for an amazing backend engineer. Must know APIs. Must know databases. Must know Python.",
            competencies=[Competency(name="Python", description="Writes good Python code")]
        ),
        settings=InterviewSettings(max_questions=3), # Short interview for testing
        candidate_identifier="Test Candidate"
    )

# =================================================================
# TESTS
# =================================================================

@pytest.mark.asyncio
async def test_full_interview_lifecycle(db_session, create_request):
    """Test the complete happy path of an interview."""
    orchestrator = InterviewOrchestrator(db_session)
    
    # 1. CREATE
    session = await orchestrator.create_interview(create_request)
    assert session.status == InterviewStatus.CONFIGURED
    assert session.session_id is not None
    
    # 2. START (Mock the agent)
    mock_q1 = NextQuestion(
        question_text="Q1", rationale="R1", competency_targeted="Python", 
        is_followup=False, expected_good_answer_elements=["A"]
    )
    
    with patch('app.agents.interviewer.InterviewerAgentAdapter.generate_next_question', new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = mock_q1
        
        session = await orchestrator.start_interview(session.session_id)
        
        assert session.status == InterviewStatus.IN_PROGRESS
        assert session.questions_asked == 1
        assert len(session.transcript) == 1
        assert session.transcript[0].speaker == "interviewer"
        assert session.transcript[0].content == "Q1"
        
    # 3. HANDLE ANSWER 1
    mock_q2 = NextQuestion(
        question_text="Q2", rationale="R2", competency_targeted="Python", 
        is_followup=False, expected_good_answer_elements=["B"]
    )
    
    with patch('app.agents.interviewer.InterviewerAgentAdapter.generate_next_question', new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = mock_q2
        
        session = await orchestrator.handle_candidate_answer(session.session_id, "A1")
        
        assert session.questions_asked == 2
        assert len(session.transcript) == 3 # Q1, A1, Q2
        assert session.transcript[1].speaker == "candidate"
        assert session.transcript[1].content == "A1"
        
    # 4. HANDLE ANSWER 2
    mock_q3 = NextQuestion(
        question_text="Q3", rationale="R3", competency_targeted="Python", 
        is_followup=False, expected_good_answer_elements=["C"]
    )
    with patch('app.agents.interviewer.InterviewerAgentAdapter.generate_next_question', new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = mock_q3
        session = await orchestrator.handle_candidate_answer(session.session_id, "A2")
        
    assert session.questions_asked == 3
    
    # 5. HANDLE ANSWER 3 (Should trigger completion since max_questions=3)
    session = await orchestrator.handle_candidate_answer(session.session_id, "A3")
    
    assert session.status == InterviewStatus.COMPLETED
    assert len(session.transcript) == 7 # Q1, A1, Q2, A2, Q3, A3, Conclusion
    assert session.transcript[-1].speaker == "interviewer"
    assert "concludes" in session.transcript[-1].content.lower()
    
    # 6. EVALUATE
    mock_report = EvaluationReport(
        competency_evaluations=[
            CompetencyEvaluation(
                competency_name="Python", score=5, rationale="Great", 
                evidence_excerpts=["A1"], missing_evidence="None"
            )
        ],
        strengths=["Good"], areas_for_improvement=["None"], questions_for_human_reviewer=[]
    )
    
    with patch('app.agents.evaluator.EvaluatorAgentAdapter.generate_evaluation', new_callable=AsyncMock) as mock_eval:
        mock_eval.return_value = mock_report
        
        report = await orchestrator.evaluate_interview(session.session_id)
        
        assert report.competency_evaluations[0].score == 5
        
        # Check final DB state
        final_session = await orchestrator.repo.get_by_id(session.session_id)
        assert final_session.status == InterviewStatus.REPORT_READY


@pytest.mark.asyncio
async def test_state_machine_blocks_invalid_actions(db_session, create_request):
    """Test that the state machine prevents actions out of order."""
    orchestrator = InterviewOrchestrator(db_session)
    session = await orchestrator.create_interview(create_request)
    
    # Session is currently CONFIGURED. 
    # We should NOT be able to handle an answer yet.
    with pytest.raises(StateMachineError):
        await orchestrator.handle_candidate_answer(session.session_id, "Hello?")
        
    # We should NOT be able to evaluate yet.
    with pytest.raises(StateMachineError):
        await orchestrator.evaluate_interview(session.session_id)


@pytest.mark.asyncio
async def test_reject_empty_and_whitespace_answers(db_session, create_request):
    """Test that empty or whitespace-only answers are rejected without advancing state."""
    orchestrator = InterviewOrchestrator(db_session)
    session = await orchestrator.create_interview(create_request)
    
    mock_q1 = NextQuestion(
        question_text="Tell me about your Python experience.",
        rationale="Assess Python competency",
        competency_targeted="Python",
        is_followup=False,
        expected_good_answer_elements=["projects", "libraries"]
    )
    with patch('app.agents.interviewer.InterviewerAgentAdapter.generate_next_question', new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = mock_q1
        session = await orchestrator.start_interview(session.session_id)

    assert session.questions_asked == 1
    assert len(session.transcript) == 1

    # Empty string should raise OrchestratorError
    with pytest.raises(OrchestratorError, match="empty or whitespace"):
        await orchestrator.handle_candidate_answer(session.session_id, "")

    # Whitespace-only string should raise OrchestratorError
    with pytest.raises(OrchestratorError, match="empty or whitespace"):
        await orchestrator.handle_candidate_answer(session.session_id, "   \n\t  ")

    # State must NOT have advanced
    current_session = await orchestrator.repo.get_by_id(session.session_id)
    assert current_session.questions_asked == 1
    assert len(current_session.transcript) == 1
    assert current_session.status == InterviewStatus.IN_PROGRESS


@pytest.mark.asyncio
async def test_short_answers_and_completion_flow(db_session, create_request):
    """Test short answers ('yes', 'no', 'I don't know') successfully advance questions and complete."""
    orchestrator = InterviewOrchestrator(db_session)
    session = await orchestrator.create_interview(create_request)
    
    # 1. Start with Q1
    mock_q1 = NextQuestion(
        question_text="Have you used Python in production?",
        rationale="R1", competency_targeted="Python", is_followup=False,
        expected_good_answer_elements=["yes/no"]
    )
    with patch('app.agents.interviewer.InterviewerAgentAdapter.generate_next_question', new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = mock_q1
        session = await orchestrator.start_interview(session.session_id)

    # 2. Answer "yes" -> Q2
    mock_q2 = NextQuestion(
        question_text="Do you have experience with async programming in Python?",
        rationale="R2", competency_targeted="Python", is_followup=False,
        expected_good_answer_elements=["asyncio"]
    )
    with patch('app.agents.interviewer.InterviewerAgentAdapter.generate_next_question', new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = mock_q2
        session = await orchestrator.handle_candidate_answer(session.session_id, "yes")

    assert session.questions_asked == 2
    assert session.transcript[1].content == "yes"
    assert session.transcript[2].content == mock_q2.question_text

    # 3. Answer "no" -> Q3
    mock_q3 = NextQuestion(
        question_text="Can you describe how garbage collection works in Python?",
        rationale="R3", competency_targeted="Python", is_followup=False,
        expected_good_answer_elements=["ref count", "cycle detector"]
    )
    with patch('app.agents.interviewer.InterviewerAgentAdapter.generate_next_question', new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = mock_q3
        session = await orchestrator.handle_candidate_answer(session.session_id, "no")

    assert session.questions_asked == 3
    assert session.transcript[3].content == "no"
    assert session.transcript[4].content == mock_q3.question_text

    # 4. Answer "I don't know" to Q3 -> should complete interview (max_questions = 3)
    session = await orchestrator.handle_candidate_answer(session.session_id, "I don't know")

    assert session.status == InterviewStatus.COMPLETED
    assert session.completed_at is not None
    assert session.transcript[5].content == "I don't know"
    assert "concludes" in session.transcript[6].content.lower()


@pytest.mark.asyncio
async def test_duplicate_question_prevention(db_session, create_request):
    """Test that if the LLM adapter proposes a duplicate question, the orchestrator adjusts it."""
    orchestrator = InterviewOrchestrator(db_session)
    session = await orchestrator.create_interview(create_request)
    
    mock_q1 = NextQuestion(
        question_text="What is a decorator in Python?",
        rationale="R1", competency_targeted="Python", is_followup=False,
        expected_good_answer_elements=["wrapper"]
    )
    with patch('app.agents.interviewer.InterviewerAgentAdapter.generate_next_question', new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = mock_q1
        session = await orchestrator.start_interview(session.session_id)

    # LLM returns an identical question to Q1
    duplicate_q = NextQuestion(
        question_text="what is a decorator in python?",  # case-insensitive duplicate
        rationale="R2", competency_targeted="Python", is_followup=False,
        expected_good_answer_elements=["wrapper"]
    )
    with patch('app.agents.interviewer.InterviewerAgentAdapter.generate_next_question', new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = duplicate_q
        session = await orchestrator.handle_candidate_answer(session.session_id, "It is a function that takes another function.")

    # Must NOT have repeated the exact question
    second_question = session.transcript[2].content
    assert second_question.lower() != "what is a decorator in python?"
    assert session.questions_asked == 2


@pytest.mark.asyncio
async def test_proctoring_events_persist_and_reload(db_session, create_request):
    """Test that proctoring events survive saving and reloading from the database."""
    orchestrator = InterviewOrchestrator(db_session)
    session = await orchestrator.create_interview(create_request)

    # Initially empty
    assert len(session.proctoring_events) == 0

    # Add a tab switch event
    event1 = ProctoringEvent(
        event_type=ProctoringEventType.tab_switch,
        details="Candidate navigated away from window"
    )
    session.proctoring_events.append(event1)
    await orchestrator.repo.save(session)

    # Reload from fresh query
    reloaded = await orchestrator.repo.get_by_id(session.session_id)
    assert reloaded is not None
    assert len(reloaded.proctoring_events) == 1
    assert reloaded.proctoring_events[0].event_type == ProctoringEventType.tab_switch
    assert reloaded.proctoring_events[0].details == "Candidate navigated away from window"

    # Add a second event (copy-paste attempt)
    event2 = ProctoringEvent(
        event_type=ProctoringEventType.copy_paste_attempt,
        details="paste attempted in answer box"
    )
    reloaded.proctoring_events.append(event2)
    await orchestrator.repo.save(reloaded)

    # Reload again
    reloaded2 = await orchestrator.repo.get_by_id(session.session_id)
    assert len(reloaded2.proctoring_events) == 2
    assert reloaded2.proctoring_events[1].event_type == ProctoringEventType.copy_paste_attempt


@pytest.mark.asyncio
async def test_proctoring_events_survive_evaluation_and_report_retrieval(db_session, create_request):
    """Test that proctoring events are preserved when an interview finishes and evaluates."""
    orchestrator = InterviewOrchestrator(db_session)
    session = await orchestrator.create_interview(create_request)

    # Mock first question
    mock_q = NextQuestion(
        question_text="Q1", rationale="R1", competency_targeted="Python",
        is_followup=False, expected_good_answer_elements=["A"]
    )
    with patch('app.agents.interviewer.InterviewerAgentAdapter.generate_next_question', new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = mock_q
        session = await orchestrator.start_interview(session.session_id)

    # Add proctoring events during the interview
    session.proctoring_events.append(
        ProctoringEvent(event_type=ProctoringEventType.face_missing, details="No face visible for 12s")
    )
    session.proctoring_events.append(
        ProctoringEvent(event_type=ProctoringEventType.multiple_faces, details="2 faces detected")
    )
    await orchestrator.repo.save(session)

    # Conclude interview by setting status to COMPLETED
    session.status = InterviewStatus.COMPLETED
    await orchestrator.repo.save(session)

    # Mock evaluation
    mock_report = EvaluationReport(
        competency_evaluations=[
            CompetencyEvaluation(
                competency_name="Python", score="Not Assessed", rationale="Insufficient depth",
                evidence_excerpts=[], missing_evidence="No details"
            )
        ],
        strengths=[], areas_for_improvement=["Practice core concepts"], questions_for_human_reviewer=[]
    )
    with patch('app.agents.evaluator.EvaluatorAgentAdapter.generate_evaluation', new_callable=AsyncMock) as mock_eval:
        mock_eval.return_value = mock_report
        report = await orchestrator.evaluate_interview(session.session_id)
        assert report is not None

    # Verify session reloaded from database retains proctoring events and evaluation report
    final_session = await orchestrator.repo.get_by_id(session.session_id)
    assert final_session.status == InterviewStatus.REPORT_READY
    assert len(final_session.proctoring_events) == 2
    assert final_session.proctoring_events[0].event_type == ProctoringEventType.face_missing
    assert final_session.proctoring_events[1].event_type == ProctoringEventType.multiple_faces
    assert final_session.evaluation_report is not None



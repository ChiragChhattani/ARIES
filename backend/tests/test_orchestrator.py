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
from app.schemas.interview import InterviewCreateRequest, InterviewSettings, ProctoringEvent, TranscriptEntry
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


@pytest.mark.asyncio
async def test_interview_continuation_through_five_question_limit(db_session):
    """
    Regression test: Verifies that the interview progresses through all 5 questions
    with normal answers, short answers, and 'I don't know', terminating only when
    the 5-question limit is reached.
    """
    from app.schemas.job import InterviewField
    orchestrator = InterviewOrchestrator(db_session)
    request = InterviewCreateRequest(
        job_description=JobDescription(
            title="Software Engineer",
            field=InterviewField.SOFTWARE_ENGINEERING,
            description="A" * 60,
            competencies=[
                Competency(name="Data Structures", description="Arrays, maps, trees"),
                Competency(name="Algorithms", description="Sorting, searching"),
                Competency(name="System Design", description="Distributed systems"),
            ]
        ),
        settings=InterviewSettings(max_questions=5),
        candidate_identifier="Test Candidate"
    )
    session = await orchestrator.create_interview(request)
    assert session.status == InterviewStatus.CONFIGURED

    # Q1
    q1 = NextQuestion(
        question_text="Explain how hash tables handle collisions.",
        rationale="Assess hash table internals",
        competency_targeted="Data Structures",
        is_followup=False,
        expected_good_answer_elements=["chaining", "open addressing"]
    )
    with patch('app.agents.interviewer.InterviewerAgentAdapter.generate_next_question', new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = q1
        session = await orchestrator.start_interview(session.session_id)

    assert session.status == InterviewStatus.IN_PROGRESS
    assert session.questions_asked == 1
    assert len(session.transcript) == 1

    # Turn 1: Normal answer -> generates Q2
    q2 = NextQuestion(
        question_text="What is the time complexity of quicksort in the worst case?",
        rationale="Assess sorting algorithms",
        competency_targeted="Algorithms",
        is_followup=False,
        expected_good_answer_elements=["O(n^2)", "pivot selection"]
    )
    with patch('app.agents.interviewer.InterviewerAgentAdapter.generate_next_question', new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = q2
        session = await orchestrator.handle_candidate_answer(
            session.session_id,
            "Hash tables use chaining with linked lists or open addressing with linear probing to resolve collisions."
        )

    assert session.status == InterviewStatus.IN_PROGRESS
    assert session.questions_asked == 2
    assert len(session.transcript) == 3

    # Turn 2: Short answer ("Yes, O(n log n) average.") -> generates Q3
    q3 = NextQuestion(
        question_text="How would you design a rate limiter for an API?",
        rationale="Assess system design",
        competency_targeted="System Design",
        is_followup=False,
        expected_good_answer_elements=["token bucket", "Redis"]
    )
    with patch('app.agents.interviewer.InterviewerAgentAdapter.generate_next_question', new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = q3
        session = await orchestrator.handle_candidate_answer(
            session.session_id,
            "Worst case is O(n^2), average is O(n log n)."
        )

    assert session.status == InterviewStatus.IN_PROGRESS
    assert session.questions_asked == 3
    assert len(session.transcript) == 5

    # Turn 3: "I don't know" answer -> does NOT stop interview, moves to Q4
    q4 = NextQuestion(
        question_text="Can you explain the difference between a process and a thread?",
        rationale="Assess OS fundamentals",
        competency_targeted="Data Structures",
        is_followup=False,
        expected_good_answer_elements=["shared memory", "isolation"]
    )
    with patch('app.agents.interviewer.InterviewerAgentAdapter.generate_next_question', new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = q4
        session = await orchestrator.handle_candidate_answer(
            session.session_id,
            "I don't know"
        )

    assert session.status == InterviewStatus.IN_PROGRESS
    assert session.questions_asked == 4
    assert len(session.transcript) == 7

    # Turn 4: Normal answer -> generates Q5 (5th main question)
    q5 = NextQuestion(
        question_text="What are database indexes and how do B-trees work?",
        rationale="Assess database indexing",
        competency_targeted="System Design",
        is_followup=False,
        expected_good_answer_elements=["B-tree", "lookup speed"]
    )
    with patch('app.agents.interviewer.InterviewerAgentAdapter.generate_next_question', new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = q5
        session = await orchestrator.handle_candidate_answer(
            session.session_id,
            "A process has its own address space, while threads share the process memory."
        )

    assert session.status == InterviewStatus.IN_PROGRESS
    assert session.questions_asked == 5
    assert len(session.transcript) == 9

    # Turn 5: 5th answer submitted -> interview terminates at max_questions=5 limit
    session = await orchestrator.handle_candidate_answer(
        session.session_id,
        "Indexes speed up reads using balanced search trees like B+ trees."
    )

    assert session.status == InterviewStatus.COMPLETED
    assert session.questions_asked == 5
    # Transcript has 10 entries: Q1, A1, Q2, A2, Q3, A3, Q4, A4, Q5, A5 + conclusion = 11 entries
    assert len(session.transcript) == 11
    assert session.transcript[-1].speaker == "interviewer"
    assert "conclude" in session.transcript[-1].content.lower()


@pytest.mark.asyncio
async def test_tab_switch_proctoring_event_does_not_block_or_terminate_interview(db_session, create_request):
    """
    Verifies that logging tab-switch or window-blur events does not stop question generation,
    does not terminate the interview prematurely, and does not corrupt transcript data.
    """
    orchestrator = InterviewOrchestrator(db_session)
    session = await orchestrator.create_interview(create_request)

    q1 = NextQuestion(
        question_text="Q1", rationale="R1", competency_targeted="Python",
        is_followup=False, expected_good_answer_elements=["A"]
    )
    with patch('app.agents.interviewer.InterviewerAgentAdapter.generate_next_question', new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = q1
        session = await orchestrator.start_interview(session.session_id)

    # Candidate switches tabs while reading Q1
    tab_event = ProctoringEvent(
        event_type=ProctoringEventType.tab_switch,
        details="document.visibilityState became hidden (tab switched)"
    )
    added = await orchestrator.repo.add_proctoring_event(session.session_id, tab_event)
    assert added is True

    # Interview must remain IN_PROGRESS
    reloaded = await orchestrator.repo.get_by_id(session.session_id)
    assert reloaded.status == InterviewStatus.IN_PROGRESS
    assert reloaded.questions_asked == 1
    assert len(reloaded.transcript) == 1
    assert len(reloaded.proctoring_events) == 1

    # Candidate returns and submits answer 1
    q2 = NextQuestion(
        question_text="Q2", rationale="R2", competency_targeted="Python",
        is_followup=False, expected_good_answer_elements=["B"]
    )
    with patch('app.agents.interviewer.InterviewerAgentAdapter.generate_next_question', new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = q2
        session = await orchestrator.handle_candidate_answer(session.session_id, "Answer 1 after tab switch")

    assert session.status == InterviewStatus.IN_PROGRESS
    assert session.questions_asked == 2
    assert len(session.transcript) == 3

    # Candidate triggers window blur
    blur_event = ProctoringEvent(
        event_type=ProctoringEventType.window_blur,
        details="Window lost focus"
    )
    await orchestrator.repo.add_proctoring_event(session.session_id, blur_event)

    # Candidate submits answer 2
    q3 = NextQuestion(
        question_text="Q3", rationale="R3", competency_targeted="Python",
        is_followup=False, expected_good_answer_elements=["C"]
    )
    with patch('app.agents.interviewer.InterviewerAgentAdapter.generate_next_question', new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = q3
        session = await orchestrator.handle_candidate_answer(session.session_id, "Answer 2")

    assert session.status == InterviewStatus.IN_PROGRESS
    assert session.questions_asked == 3

    # Final DB check: both proctoring events logged, all questions intact
    final_session = await orchestrator.repo.get_by_id(session.session_id)
    assert len(final_session.proctoring_events) == 2
    assert len(final_session.transcript) == 5


@pytest.mark.asyncio
async def test_idempotent_answer_does_not_advance_or_duplicate(db_session, create_request):
    """Test that submitting an answer for an already-answered question (during disconnect/fallback) is idempotent."""
    orchestrator = InterviewOrchestrator(db_session)
    session = await orchestrator.create_interview(create_request)

    q1 = NextQuestion(
        question_text="What is Python?", rationale="R1", competency_targeted="Python",
        is_followup=False, expected_good_answer_elements=["Language"]
    )
    with patch('app.agents.interviewer.InterviewerAgentAdapter.generate_next_question', new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = q1
        session = await orchestrator.start_interview(session.session_id)

    # Turn 1: Process answer for Q1 -> advances to Q2
    q2 = NextQuestion(
        question_text="What is asyncio?", rationale="R2", competency_targeted="Python",
        is_followup=False, expected_good_answer_elements=["Event loop"]
    )
    with patch('app.agents.interviewer.InterviewerAgentAdapter.generate_next_question', new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = q2
        session = await orchestrator.handle_candidate_answer(
            session.session_id, "Python is a language", client_last_question="What is Python?"
        )

    assert session.questions_asked == 2
    assert len(session.transcript) == 3
    assert session.transcript[-1].content == "What is asyncio?"

    # Fallback/retry arrives with answer to Q1 again (client_last_question="What is Python?")
    idempotent_session = await orchestrator.handle_candidate_answer(
        session.session_id, "Python is a language", client_last_question="What is Python?"
    )

    # MUST NOT advance to Q3, MUST NOT add another transcript entry
    assert idempotent_session.questions_asked == 2
    assert len(idempotent_session.transcript) == 3
    assert idempotent_session.transcript[-1].content == "What is asyncio?"


@pytest.mark.asyncio
async def test_consecutive_candidate_answers_rejected(db_session, create_request):
    """Test that submitting a candidate answer when previous candidate answer is already pending raises StateMachineError."""
    orchestrator = InterviewOrchestrator(db_session)
    session = await orchestrator.create_interview(create_request)

    q1 = NextQuestion(
        question_text="What is Python?", rationale="R1", competency_targeted="Python",
        is_followup=False, expected_good_answer_elements=["Language"]
    )
    with patch('app.agents.interviewer.InterviewerAgentAdapter.generate_next_question', new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = q1
        session = await orchestrator.start_interview(session.session_id)

    # Artificially simulate an uncompleted turn where candidate answer is in transcript
    session.transcript.append(
        TranscriptEntry(speaker="candidate", content="First answer", stage=session.current_stage)
    )
    await orchestrator.repo.save(session)

    # Submitting another answer while speaker is still candidate should be blocked
    with pytest.raises(StateMachineError, match="already been submitted"):
        await orchestrator.handle_candidate_answer(session.session_id, "Second answer")


@pytest.mark.asyncio
async def test_orchestrator_evaluate_retry_preserves_completed(db_session, create_request):
    """When evaluation agent throws, orchestrator reverts status to COMPLETED so it can be retried."""
    orchestrator = InterviewOrchestrator(db_session)
    session = await orchestrator.create_interview(create_request)
    session.status = InterviewStatus.COMPLETED
    session.transcript.append(
        TranscriptEntry(speaker="interviewer", content="Question 1")
    )
    session.transcript.append(
        TranscriptEntry(speaker="candidate", content="Answer 1")
    )
    await orchestrator.repo.save(session)

    # First attempt fails with an exception
    with patch('app.agents.evaluator.EvaluatorAgentAdapter.generate_evaluation', new_callable=AsyncMock) as mock_eval:
        mock_eval.side_effect = RuntimeError("Evaluation LLM timeout")

        with pytest.raises(RuntimeError, match="Evaluation LLM timeout"):
            await orchestrator.evaluate_interview(session.session_id)

        # Status must have reverted to COMPLETED rather than permanently FAILED
        reloaded = await orchestrator.repo.get_by_id(session.session_id)
        assert reloaded.status == InterviewStatus.COMPLETED

    # Second attempt succeeds
    mock_report = EvaluationReport(
        competency_evaluations=[
            CompetencyEvaluation(
                competency_name="Python", score=5, rationale="Great",
                evidence_excerpts=["Answer 1"], missing_evidence=""
            )
        ],
        strengths=["Solid knowledge"], areas_for_improvement=[], questions_for_human_reviewer=[]
    )
    with patch('app.agents.evaluator.EvaluatorAgentAdapter.generate_evaluation', new_callable=AsyncMock) as mock_eval:
        mock_eval.return_value = mock_report
        report = await orchestrator.evaluate_interview(session.session_id)
        assert report.competency_evaluations[0].score == 5

        final = await orchestrator.repo.get_by_id(session.session_id)
        assert final.status == InterviewStatus.REPORT_READY


@pytest.mark.asyncio
async def test_orchestrator_evaluate_idempotency_returns_cached_report(db_session, create_request):
    """Calling evaluate on a session that is already REPORT_READY returns cached report without re-evaluating."""
    orchestrator = InterviewOrchestrator(db_session)
    session = await orchestrator.create_interview(create_request)

    existing_report = EvaluationReport(
        competency_evaluations=[
            CompetencyEvaluation(
                competency_name="Python", score=4, rationale="Cached",
                evidence_excerpts=[], missing_evidence=""
            )
        ]
    )
    session.status = InterviewStatus.REPORT_READY
    session.evaluation_report = existing_report
    await orchestrator.repo.save(session)

    with patch('app.agents.evaluator.EvaluatorAgentAdapter.generate_evaluation', new_callable=AsyncMock) as mock_eval:
        report = await orchestrator.evaluate_interview(session.session_id)
        assert report.competency_evaluations[0].score == 4
        # Agent should not have been called
        assert mock_eval.call_count == 0

"""
Tests for the Agent Adapters.

We use `unittest.mock.AsyncMock` to patch the AutoGen `AssistantAgent.run` method.
This prevents the tests from making actual network calls to OpenAI, ensuring
tests are fast, deterministic, and free.
"""

import json
import pytest
from unittest.mock import AsyncMock, patch

from autogen_agentchat.messages import TextMessage
from autogen_agentchat.base import TaskResult

from app.schemas.job import JobDescription, Competency
from app.schemas.rubric import get_default_rubric
from app.schemas.interview import TranscriptEntry
from app.schemas.agent_outputs import NextQuestion, EvaluationReport, CompetencyEvaluation
from app.agents.candidate_simulator import CandidateAnswer

# =================================================================
# TEST FIXTURES
# =================================================================

@pytest.fixture
def sample_job():
    return JobDescription(
        title="Backend Developer",
        description="We are looking for a backend developer who will write cool APIs in Python. "
                    "You will build distributed systems and work with microservices architecture.",
        competencies=[
            Competency(
                name="Python", 
                description="Demonstrates deep understanding of Python async, decorators, and generators."
            )
        ]
    )

@pytest.fixture
def sample_transcript():
    return [
        TranscriptEntry(speaker="interviewer", content="Hello, let's start."),
        TranscriptEntry(speaker="candidate", content="Hi, I'm ready.")
    ]

# Helper to create a fake AutoGen TaskResult
def create_mock_task_result(json_content: dict) -> TaskResult:
    message = TextMessage(content=json.dumps(json_content), source="assistant")
    return TaskResult(messages=[message])

# =================================================================
# AGENT TESTS
# =================================================================

@pytest.mark.asyncio
@patch("app.agents.interviewer.is_groq", return_value=False)
async def test_interviewer_agent(mock_is_groq, sample_job, sample_transcript):
    """Test that the InterviewerAdapter parses a valid JSON response correctly."""
    from app.agents.interviewer import InterviewerAgentAdapter
    
    adapter = InterviewerAgentAdapter(job=sample_job)
    
    mock_response = {
        "question_text": "How do you handle async in Python?",
        "rationale": "Testing core competency.",
        "competency_targeted": "Python",
        "is_followup": False,
        "expected_good_answer_elements": ["asyncio", "await"]
    }
    
    with patch.object(adapter._agent, 'run', new_callable=AsyncMock) as mock_run:
        mock_run.return_value = create_mock_task_result(mock_response)
        
        result = await adapter.generate_next_question(
            transcript=sample_transcript,
            questions_remaining=5
        )
        
        # Verify the adapter called AutoGen's run method
        mock_run.assert_called_once()
        
        # Verify it successfully parsed the Pydantic model
        assert isinstance(result, NextQuestion)
        assert result.question_text == "How do you handle async in Python?"
        assert result.is_followup is False

@pytest.mark.asyncio
@patch("app.agents.evaluator.is_groq", return_value=False)
async def test_evaluator_agent(mock_is_groq, sample_job, sample_transcript):
    """Test that the EvaluatorAdapter generates a valid EvaluationReport."""
    from app.agents.evaluator import EvaluatorAgentAdapter
    
    adapter = EvaluatorAgentAdapter(job=sample_job, rubric=get_default_rubric())
    
    mock_response = {
        "competency_evaluations": [
            {
                "competency_name": "Python",
                "score": 4,
                "rationale": "Good answer.",
                "evidence_excerpts": ["I used asyncio"],
                "missing_evidence": "Didn't mention Tasks"
            }
        ],
        "strengths": ["Clear communication"],
        "areas_for_improvement": ["Advanced async concepts"],
        "questions_for_human_reviewer": []
    }
    
    with patch.object(adapter._agent, 'run', new_callable=AsyncMock) as mock_run:
        mock_run.return_value = create_mock_task_result(mock_response)
        
        result = await adapter.generate_evaluation(transcript=sample_transcript)
        
        assert isinstance(result, EvaluationReport)
        assert len(result.competency_evaluations) == 1
        assert result.competency_evaluations[0].score == 4

@pytest.mark.asyncio
@patch("app.agents.candidate_simulator.is_groq", return_value=False)
async def test_candidate_simulator(mock_is_groq, sample_job, sample_transcript):
    """Test that the CandidateSimulator parses the answer text correctly."""
    from app.agents.candidate_simulator import CandidateSimulatorAdapter
    
    adapter = CandidateSimulatorAdapter(job=sample_job, persona="Junior Dev")
    
    # The agent is supposed to return CandidateAnswer schema
    mock_response = {
        "answer_text": "I think I would use a for loop."
    }
    
    with patch.object(adapter._agent, 'run', new_callable=AsyncMock) as mock_run:
        mock_run.return_value = create_mock_task_result(mock_response)
        
        result = await adapter.generate_answer(
            transcript=sample_transcript,
            current_question="How do you iterate?"
        )
        
        assert result == "I think I would use a for loop."


@pytest.mark.asyncio
@patch("app.agents.evaluator.is_groq", return_value=False)
async def test_evaluator_handles_not_assessed_and_verbatim_quotes(mock_is_groq, sample_job):
    """Test that the EvaluatorAdapter handles 'Not Assessed', verbatim quote evidence, and human review questions."""
    from app.agents.evaluator import EvaluatorAgentAdapter
    
    transcript = [
        TranscriptEntry(speaker="interviewer", content="Have you implemented microservices with Python?"),
        TranscriptEntry(speaker="candidate", content="yes")
    ]
    
    adapter = EvaluatorAgentAdapter(job=sample_job, rubric=get_default_rubric())
    
    mock_response = {
        "competency_evaluations": [
            {
                "competency_name": "Python",
                "score": "Not Assessed",
                "rationale": "Candidate affirmed familiarity with 'yes' but was not asked to demonstrate technical depth.",
                "evidence_excerpts": ['Candidate answered: "yes"'],
                "missing_evidence": "Concrete examples of microservices implementation or architecture."
            }
        ],
        "strengths": ["Confirmed familiarity with Python concepts."],
        "areas_for_improvement": ["Should provide detailed technical examples and explanations rather than yes/no affirmations."],
        "questions_for_human_reviewer": [
            "Can you describe a specific microservice you built using Python and how you handled asynchronous communication?"
        ]
    }
    
    with patch.object(adapter._agent, 'run', new_callable=AsyncMock) as mock_run:
        mock_run.return_value = create_mock_task_result(mock_response)
        result = await adapter.generate_evaluation(transcript=transcript)
        
        assert isinstance(result, EvaluationReport)
        assert result.competency_evaluations[0].score == "Not Assessed"
        assert 'Candidate answered: "yes"' in result.competency_evaluations[0].evidence_excerpts
        assert len(result.strengths) == 1
        assert len(result.areas_for_improvement) == 1
        assert len(result.questions_for_human_reviewer) == 1


def test_evaluator_system_prompt_includes_role_rubric_context(sample_job):
    """Verify that evaluator prompt includes role, experience level, difficulty, and rubric."""
    from app.prompts.evaluator import get_evaluator_system_prompt
    
    sample_job.title = "Lead AI Engineer"
    sample_job.required_skills = ["PyTorch", "Transformers", "Distributed Training"]
    prompt = get_evaluator_system_prompt(sample_job, get_default_rubric())
    
    assert "Lead AI Engineer" in prompt
    assert "PyTorch, Transformers, Distributed Training" in prompt
    assert "ROLE-SPECIFIC COMPETENCIES TO EVALUATE" in prompt
    assert "DISTINGUISH \"Not Assessed\" FROM LOW SCORES" in prompt
    assert "NEVER FABRICATE" in prompt


def test_interviewer_prompt_followup_rule_targets_genuine_gaps(sample_job):
    """Verify that interviewer prompt instructs follow-ups to target genuine evidence gaps."""
    from app.prompts.interviewer import get_interviewer_system_prompt
    
    prompt = get_interviewer_system_prompt(sample_job)
    assert "genuine evidence gap" in prompt
    assert "Do NOT ask a follow-up merely because follow-ups remain" in prompt


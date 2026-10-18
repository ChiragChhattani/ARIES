"""
Structured output schemas for Agent responses.

These Pydantic models define the exact JSON shapes we expect
the LLMs to return. By forcing the LLM to output these schemas,
we bridge the gap between non-deterministic text generation and
strict, deterministic Python code.
"""

from pydantic import BaseModel, Field

class NextQuestion(BaseModel):
    """Output schema for the Interviewer Agent."""
    question_text: str = Field(
        description="The actual text of the question to ask the candidate."
    )
    rationale: str = Field(
        description="Brief explanation of WHY you are asking this question and what evidence you hope to gather."
    )
    competency_targeted: str = Field(
        description="The name of the primary competency this question assesses."
    )
    is_followup: bool = Field(
        description="True if this is a follow-up to the candidate's previous answer, False if it's a new topic."
    )
    expected_good_answer_elements: list[str] = Field(
        description="2-3 key points you expect a strong candidate to mention."
    )

class CompetencyEvaluation(BaseModel):
    """Evaluation for a single competency (used by Evaluator Agent)."""
    competency_name: str = Field(description="Name of the competency being evaluated")
    score: int | str = Field(
        description="Numeric score based strictly on the rubric (e.g., 1-5). Use 'Not Assessed' if completely insufficient evidence."
    )
    rationale: str = Field(
        description="Detailed explanation of why this score was given."
    )
    evidence_excerpts: list[str] = Field(
        default_factory=list,
        description="Direct quotes or specific references from the transcript that justify this score."
    )
    missing_evidence: str = Field(
        default="",
        description="What the candidate failed to mention that prevented a higher score."
    )

class EvaluationReport(BaseModel):
    """Final output schema for the Evaluator Agent."""
    competency_evaluations: list[CompetencyEvaluation] = Field(
        default_factory=list,
        description="Individual evaluations for each required competency."
    )
    strengths: list[str] = Field(
        default_factory=list,
        description="2-3 standout strengths demonstrated by the candidate."
    )
    areas_for_improvement: list[str] = Field(
        default_factory=list,
        description="2-3 areas where the candidate showed weakness or lacked depth."
    )
    questions_for_human_reviewer: list[str] = Field(
        default_factory=list,
        description="Areas of uncertainty where a human recruiter should probe deeper in the next round."
    )

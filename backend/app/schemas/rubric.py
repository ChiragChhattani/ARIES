"""
Evaluation rubric schemas.

The rubric defines HOW candidates are scored. It must be:
- Transparent: The candidate (or a reviewer) can see what "a 4 out of 5" means
- Job-related: Criteria must connect to actual job requirements
- Configurable: Different jobs can have different rubrics
- Deterministic in aggregation: The LLM evaluates per-competency,
  but the final score is computed by a deterministic function, not the LLM

WHY NOT LET THE LLM ASSIGN FINAL SCORES?
-----------------------------------------
LLMs are good at qualitative assessment ("this answer shows strong problem
solving because...") but unreliable at consistent quantitative scoring.
If you ask GPT-4o to score the same answer twice, you might get 4/5 and 3/5.

Our approach: The LLM provides per-competency scores with justification,
then a deterministic Python function computes the weighted average. This
makes the scoring auditable and reproducible.
"""

from pydantic import BaseModel, Field, field_validator


class RubricLevel(BaseModel):
    """
    One level on the scoring scale.

    Example for a 1-5 scale:
        RubricLevel(score=4, label="Strong", description="Demonstrates clear competency...")
    """
    score: int = Field(ge=1, le=5, description="Numeric score")
    label: str = Field(
        min_length=1,
        max_length=50,
        description="Short label (e.g., 'Excellent', 'Adequate', 'Insufficient')",
    )
    description: str = Field(
        min_length=10,
        max_length=300,
        description="What this score level means — what evidence would you see?",
    )


class EvaluationRubric(BaseModel):
    """
    The complete scoring rubric for an interview.

    Contains the scale definition (what each score means) and
    configuration for how scores are aggregated.
    """
    name: str = Field(
        default="Standard Technical Interview Rubric",
        min_length=2,
        max_length=200,
    )
    version: str = Field(
        default="1.0",
        max_length=20,
        description="Rubric version for audit trail. Change when rubric criteria change.",
    )
    scale: list[RubricLevel] = Field(
        min_length=3,
        max_length=10,
        description="Scoring scale from lowest to highest",
    )
    min_evidence_threshold: int = Field(
        default=1,
        ge=1,
        le=5,
        description="Minimum number of evidence excerpts required to assign a confident score. "
                    "If fewer excerpts exist, the evaluation must flag uncertainty.",
    )
    insufficient_evidence_label: str = Field(
        default="Insufficient Evidence",
        description="Label to use when the evaluator cannot confidently score a competency",
    )

    @field_validator("scale")
    @classmethod
    def validate_scale_ordering(cls, v: list[RubricLevel]) -> list[RubricLevel]:
        """Ensure scale scores are unique and sorted ascending."""
        scores = [level.score for level in v]
        if len(scores) != len(set(scores)):
            raise ValueError("Rubric scale scores must be unique")
        if scores != sorted(scores):
            raise ValueError("Rubric scale must be sorted from lowest to highest score")
        return v


def get_default_rubric() -> EvaluationRubric:
    """
    Returns a sensible default 5-point rubric.

    This is used when the user doesn't provide a custom rubric.
    It follows standard behavioral interview scoring conventions.
    """
    return EvaluationRubric(
        name="Standard Interview Rubric",
        version="1.0",
        scale=[
            RubricLevel(
                score=1,
                label="Insufficient",
                description="No relevant evidence provided. Candidate could not address "
                            "the competency or gave responses unrelated to the question.",
            ),
            RubricLevel(
                score=2,
                label="Basic",
                description="Limited evidence of competency. Answers were vague, lacked "
                            "specifics, or showed only surface-level understanding.",
            ),
            RubricLevel(
                score=3,
                label="Adequate",
                description="Acceptable evidence of competency. Candidate provided relevant "
                            "examples but lacked depth, detail, or clear impact.",
            ),
            RubricLevel(
                score=4,
                label="Strong",
                description="Clear evidence of competency. Candidate provided specific "
                            "examples with context, actions taken, and measurable outcomes.",
            ),
            RubricLevel(
                score=5,
                label="Exceptional",
                description="Outstanding evidence of competency. Candidate demonstrated "
                            "deep expertise, strategic thinking, and significant impact "
                            "with concrete, verifiable examples.",
            ),
        ],
        min_evidence_threshold=2,
    )

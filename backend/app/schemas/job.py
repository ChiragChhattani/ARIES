"""
Job description and competency schemas.

These models represent what the interviewer needs to know:
- What job is the candidate being interviewed for?
- What competencies should be assessed?
- What does "good" look like for each competency?
"""

from pydantic import BaseModel, Field, model_validator
from enum import Enum


class InterviewField(str, Enum):
    SOFTWARE_ENGINEERING = "software_engineering"
    FRONTEND_DEVELOPMENT = "frontend_development"
    BACKEND_DEVELOPMENT = "backend_development"
    FULLSTACK_DEVELOPMENT = "fullstack_development"
    AI_ML = "ai_ml"
    GENERATIVE_AI = "generative_ai"
    DATA_SCIENCE = "data_science"
    DATA_ENGINEERING = "data_engineering"
    DEVOPS_CLOUD = "devops_cloud"
    CYBERSECURITY = "cybersecurity"
    ELECTRICAL_ENGINEERING = "electrical_engineering"
    ELECTRONICS_EMBEDDED = "electronics_embedded"
    MECHANICAL_ENGINEERING = "mechanical_engineering"
    CIVIL_ENGINEERING = "civil_engineering"
    PRODUCT_MANAGEMENT = "product_management"
    BUSINESS_ANALYST = "business_analyst"
    UI_UX_DESIGN = "ui_ux_design"
    QA_TESTING = "qa_testing"
    HR_RECRUITMENT = "hr_recruitment"
    CUSTOM = "custom"


class ExperienceLevel(str, Enum):
    FRESHER = "fresher"
    JUNIOR = "junior"
    MID_LEVEL = "mid_level"
    SENIOR = "senior"


class DifficultyLevel(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class Competency(BaseModel):
    """
    A single skill or competency to assess during the interview.

    Example:
        Competency(
            name="System Design",
            description="Ability to design scalable distributed systems",
            weight=1.5,
            required=True,
            sample_questions=["Describe how you'd design a URL shortener"]
        )
    """
    name: str = Field(
        min_length=2,
        max_length=100,
        description="Name of the competency (e.g., 'Problem Solving')",
    )
    description: str = Field(
        min_length=10,
        max_length=500,
        description="What this competency means in the context of this job",
    )
    weight: float = Field(
        default=1.0,
        ge=0.1,
        le=5.0,
        description="Relative importance weight. Higher = more important.",
    )
    required: bool = Field(
        default=True,
        description="Whether this competency must be assessed. If True, the interviewer "
                    "must ask at least one question targeting this competency.",
    )
    sample_questions: list[str] = Field(
        default_factory=list,
        max_length=5,
        description="Optional example questions for this competency. The interviewer "
                    "uses these as inspiration, not as a rigid script.",
    )


class JobDescription(BaseModel):
    """
    The job being interviewed for.

    This provides the context the Interviewer Agent needs to generate
    relevant, job-specific questions rather than generic ones.
    """
    title: str = Field(
        min_length=1,
        max_length=200,
        description="Job title (e.g., 'Senior Backend Engineer')",
    )
    description: str = Field(
        min_length=50,
        max_length=5000,
        description="Full job description including responsibilities and requirements",
    )
    department: str = Field(
        default="",
        max_length=100,
        description="Department or team (optional)",
    )
    level: str = Field(
        default="",
        max_length=50,
        description="Seniority level (e.g., 'Senior', 'Staff', 'Junior')",
    )
    field: InterviewField = Field(
        default=InterviewField.SOFTWARE_ENGINEERING,
        description="The professional field this job belongs to",
    )
    custom_field_name: str = Field(
        default="",
        max_length=100,
        description="Name of custom field if field is CUSTOM",
    )
    required_skills: list[str] = Field(
        default_factory=list,
        description="List of specific required skills (max 100 chars each)",
    )
    experience_level: ExperienceLevel = Field(
        default=ExperienceLevel.JUNIOR,
        description="Experience level expected for the candidate",
    )
    difficulty: DifficultyLevel = Field(
        default=DifficultyLevel.MEDIUM,
        description="Interview difficulty level",
    )
    competencies: list[Competency] = Field(
        min_length=1,
        max_length=15,
        description="Competencies to assess. Must have at least 1, max 15.",
    )
    additional_context: str = Field(
        default="",
        max_length=2000,
        description="Any additional context for the interviewer (team culture, "
                    "specific technologies, recent projects, etc.)",
    )

    @model_validator(mode='after')
    def check_custom_field_name(self) -> 'JobDescription':
        if self.field == InterviewField.CUSTOM and not self.custom_field_name.strip():
            raise ValueError('custom_field_name is required when field is CUSTOM')
        return self

"""
Evaluator Agent Adapter.

Wraps either the Groq SDK (for Groq provider) or an AutoGen AssistantAgent
(for OpenAI provider) to analyze the completed interview transcript and score
the candidate against the provided rubric.
"""

from app.agents.base import (
    is_groq,
    get_json_schema_instruction,
    groq_generate,
    create_openai_client,
    parse_json_safely,
)
from app.prompts.evaluator import get_evaluator_system_prompt, get_evaluator_task_prompt
from app.schemas.job import JobDescription
from app.schemas.rubric import EvaluationRubric
from app.schemas.agent_outputs import EvaluationReport
from app.schemas.interview import TranscriptEntry
from app.observability.logging import get_logger

logger = get_logger(__name__)


class EvaluatorAgentAdapter:
    """
    Adapter for the Evaluator Agent.

    Routes to the Groq SDK directly (no openai/jiter) or AutoGen+OpenAI
    depending on the configured LLM provider.
    """

    def __init__(self, job: JobDescription, rubric: EvaluationRubric):
        self.job = job
        self.rubric = rubric
        self._system_prompt = get_evaluator_system_prompt(job, rubric)
        self._use_groq = is_groq()

        if self._use_groq:
            # Embed JSON schema in system prompt; Groq SDK handles the rest
            self._system_prompt += get_json_schema_instruction(EvaluationReport)
            self._agent = None  # not used
        else:
            # AutoGen + OpenAI native structured outputs; temperature=0 for determinism
            model_client = create_openai_client(
                response_format=EvaluationReport,
                temperature=0.0
            )
            from autogen_agentchat.agents import AssistantAgent
            self._agent = AssistantAgent(
                name="evaluator",
                model_client=model_client,
                system_message=self._system_prompt
            )

    async def generate_evaluation(self, transcript: list[TranscriptEntry]) -> EvaluationReport:
        """
        Analyzes the complete transcript and generates a structured EvaluationReport.
        """
        logger.info("Starting transcript evaluation")

        transcript_text = "\n".join([
            f"[{entry.timestamp.strftime('%H:%M:%S')}] {entry.speaker.upper()}: {entry.content}"
            for entry in transcript
        ])
        task_prompt = get_evaluator_task_prompt(transcript_text)

        try:
            if self._use_groq:
                report = await groq_generate(
                    system_prompt=self._system_prompt,
                    user_message=task_prompt,
                    output_model=EvaluationReport,
                    temperature=0.0,
                    max_tokens=3072,
                )
            else:
                result = await self._agent.run(task=task_prompt)
                raw_response = result.messages[-1].content
                report = parse_json_safely(raw_response, EvaluationReport)

            logger.info(
                "Evaluation completed successfully",
                extra={"competencies_evaluated": len(report.competency_evaluations)}
            )
            return report

        except Exception as e:
            logger.error(f"Failed to generate evaluation: {str(e)}", exc_info=True)
            raise

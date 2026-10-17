"""
Interviewer Agent Adapter.

Wraps either the Groq SDK (for Groq provider) or an AutoGen AssistantAgent
(for OpenAI provider) to provide a strict, typed interface for generating
interview questions.
"""

from app.agents.base import (
    is_groq,
    get_json_schema_instruction,
    groq_generate,
    create_openai_client,
    parse_json_safely,
)
from app.prompts.interviewer import get_interviewer_system_prompt, get_interviewer_task_prompt
from app.schemas.job import JobDescription
from app.schemas.agent_outputs import NextQuestion
from app.schemas.interview import TranscriptEntry
from app.observability.logging import get_logger

logger = get_logger(__name__)


class InterviewerAgentAdapter:
    """
    Adapter for the Interviewer Agent.

    Routes to the Groq SDK directly (no openai/jiter) or AutoGen+OpenAI
    depending on the configured LLM provider.
    """

    def __init__(self, job: JobDescription):
        self.job = job
        self._system_prompt = get_interviewer_system_prompt(job)
        self._use_groq = is_groq()

        if self._use_groq:
            # Embed JSON schema in system prompt; Groq SDK handles the rest
            self._system_prompt += get_json_schema_instruction(NextQuestion)
            self._agent = None  # not used
        else:
            # AutoGen + OpenAI native structured outputs
            model_client = create_openai_client(
                response_format=NextQuestion,
                temperature=0.7
            )
            from autogen_agentchat.agents import AssistantAgent
            self._agent = AssistantAgent(
                name="interviewer",
                model_client=model_client,
                system_message=self._system_prompt
            )

    async def generate_next_question(
        self,
        transcript: list[TranscriptEntry],
        questions_remaining: int,
        followups_remaining: int = 0,
        asked_questions: list[str] = None
    ) -> NextQuestion:
        """
        Analyzes the transcript and generates the next question.
        """
        logger.info("Generating next question", extra={"questions_remaining": questions_remaining})

        if asked_questions is None:
            asked_questions = []

        transcript_text = "\n".join([
            f"[{entry.timestamp.strftime('%H:%M:%S')}] {entry.speaker.upper()}: {entry.content}"
            for entry in transcript
        ])
        task_prompt = get_interviewer_task_prompt(
            transcript_text, 
            questions_remaining, 
            followups_remaining, 
            asked_questions
        )

        try:
            if self._use_groq:
                next_question = await groq_generate(
                    system_prompt=self._system_prompt,
                    user_message=task_prompt,
                    output_model=NextQuestion,
                    temperature=0.7,
                )
            else:
                result = await self._agent.run(task=task_prompt)
                raw_response = result.messages[-1].content
                next_question = parse_json_safely(raw_response, NextQuestion)

            logger.info(
                "Question generated successfully",
                extra={
                    "competency_targeted": next_question.competency_targeted,
                    "is_followup": next_question.is_followup,
                }
            )
            return next_question

        except Exception as e:
            logger.error(f"Failed to generate next question: {str(e)}", exc_info=True)
            raise

"""
Candidate Simulator Agent Adapter.

Acts as a mock candidate to test the interview orchestration
without requiring a human to type answers.
"""

from pydantic import BaseModel, Field

from app.agents.base import (
    is_groq,
    get_json_schema_instruction,
    groq_generate,
    create_openai_client,
    parse_json_safely,
)
from app.prompts.candidate import get_simulator_system_prompt, get_simulator_task_prompt
from app.schemas.job import JobDescription
from app.schemas.interview import TranscriptEntry
from app.observability.logging import get_logger

logger = get_logger(__name__)


# Simple structured output for the candidate to ensure we just get the answer text
class CandidateAnswer(BaseModel):
    answer_text: str = Field(description="The exact text of the candidate's response.")


class CandidateSimulatorAdapter:
    """
    Adapter for the Candidate Simulator Agent.
    
    Generates synthetic answers based on an assigned persona.
    """
    
    def __init__(self, job: JobDescription, persona: str = "A mid-level engineer who is slightly nervous and sometimes needs clarification."):
        self.job = job
        self.persona = persona
        self._system_prompt = get_simulator_system_prompt(job, persona)
        self._use_groq = is_groq()

        if self._use_groq:
            self._system_prompt += get_json_schema_instruction(CandidateAnswer)
            self._agent = None
        else:
            # Higher temperature for more natural/varied human-like responses
            model_client = create_openai_client(
                response_format=CandidateAnswer,
                temperature=0.8
            )
            from autogen_agentchat.agents import AssistantAgent
            self._agent = AssistantAgent(
                name="candidate_simulator",
                model_client=model_client,
                system_message=self._system_prompt
            )

    async def generate_answer(self, transcript: list[TranscriptEntry], current_question: str) -> str:
        """
        Generates an answer to the current question.
        
        Returns:
            str: Just the text of the answer.
        """
        logger.info("Simulator generating answer", extra={"persona": self.persona[:50] + "..."})
        
        transcript_text = "\n".join([
            f"[{entry.timestamp.strftime('%H:%M:%S')}] {entry.speaker.upper()}: {entry.content}"
            for entry in transcript
        ])
        
        task_prompt = get_simulator_task_prompt(transcript_text, current_question)
        
        try:
            if self._use_groq:
                answer = await groq_generate(
                    system_prompt=self._system_prompt,
                    user_message=task_prompt,
                    output_model=CandidateAnswer,
                    temperature=0.8,
                )
            else:
                result = await self._agent.run(task=task_prompt)
                raw_response = result.messages[-1].content
                answer = parse_json_safely(raw_response, CandidateAnswer)
            
            logger.info("Simulator answer generated")
            return answer.answer_text
            
        except Exception as e:
            logger.error(f"Simulator failed to generate answer: {str(e)}", exc_info=True)
            raise

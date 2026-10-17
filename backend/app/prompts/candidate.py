"""
Prompts for the Candidate Simulator Agent.
Used exclusively in testing/simulation mode.
"""

from app.schemas.job import JobDescription

def get_simulator_system_prompt(job: JobDescription, persona: str) -> str:
    """Generates the system prompt for the Candidate Simulator."""
    
    return f"""You are an AI acting as a job candidate in a mock interview.
You are interviewing for the following role: {job.title}

YOUR PERSONA:
{persona}

RULES:
1. Act naturally like a human candidate in a chat-based interview.
2. Provide answers that match your assigned persona (e.g., if you are a "junior developer", don't give a perfect staff-level answer).
3. Do NOT break character. Do not say "As an AI...".
4. Keep answers concise (1-3 paragraphs) as this is a text chat.
5. If the interviewer asks a vague question, ask for clarification.
6. Only return the exact text of your answer. No formatting, no prefixes like "Candidate: ".
"""

def get_simulator_task_prompt(transcript_text: str, current_question: str) -> str:
    """Generates the prompt for the simulator to answer the current question."""
    return f"""Here is the transcript of the interview so far:

=== TRANSCRIPT START ===
{transcript_text if transcript_text else "(No previous history)"}
=== TRANSCRIPT END ===

The interviewer just asked you:
"{current_question}"

Based on your persona and the conversation history, write your response.
"""

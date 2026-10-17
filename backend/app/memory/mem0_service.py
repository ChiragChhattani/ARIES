"""
Mem0 Integration Service.

Uses Mem0 to store long-term, cross-session memory for a candidate.
This allows the system to remember candidate preferences, strengths,
or career goals if they interview again in the future.
"""

import os
from typing import List, Dict, Any

try:
    from mem0 import Memory
except ImportError:
    # Fallback if mem0 is not installed properly
    Memory = None

from app.core.config import get_settings
from app.observability.logging import get_logger
from app.schemas.interview import TranscriptEntry

logger = get_logger(__name__)


class CandidateMemoryService:
    """
    Wrapper around Mem0 to manage long-term candidate insights.
    """
    
    def __init__(self):
        settings = get_settings()
        self.enabled = Memory is not None and bool(settings.openai_api_key)
        
        if self.enabled:
            # Mem0 configuration requires a dict
            config = {
                "llm": {
                    "provider": "openai",
                    "config": {
                        "model": settings.openai_model,
                        "temperature": 0.0,
                        "api_key": settings.openai_api_key,
                    }
                }
            }
            try:
                self.memory = Memory.from_config(config)
                logger.info("Mem0 service initialized successfully.")
            except Exception as e:
                logger.error(f"Failed to initialize Mem0: {e}")
                self.enabled = False
        else:
            logger.warning("Mem0 not enabled (missing package or API key).")

    def extract_and_store_insights(self, candidate_id: str, transcript: List[TranscriptEntry]) -> None:
        """
        Analyzes a completed transcript and extracts facts about the candidate
        to store in long-term memory.
        """
        if not self.enabled or candidate_id == "Anonymous" or not candidate_id:
            return
            
        logger.info(f"Extracting Mem0 insights for candidate: {candidate_id}")
        
        # Combine transcript into a readable format for Mem0
        full_text = "\n".join([f"{entry.speaker}: {entry.content}" for entry in transcript])
        
        # Instruct Mem0 to extract specific types of facts
        prompt = (
            "Extract factual preferences, hard skills mentioned, career goals, "
            "and demographic context about the candidate from this interview transcript. "
            "Do NOT extract evaluation scores or interviewer opinions."
        )
        
        try:
            # Mem0's 'add' method automatically extracts entities and memories from the text
            self.memory.add(
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": full_text}
                ],
                user_id=candidate_id
            )
            logger.info(f"Successfully stored Mem0 insights for {candidate_id}")
        except Exception as e:
            logger.error(f"Mem0 extraction failed for {candidate_id}: {e}")

    def get_candidate_context(self, candidate_id: str, job_title: str) -> str:
        """
        Retrieves relevant historical memories for a candidate to inject
        into the Interviewer Agent's prompt for personalization.
        """
        if not self.enabled or candidate_id == "Anonymous" or not candidate_id:
            return ""
            
        try:
            # Search Mem0 for relevance to this specific job
            results = self.memory.search(query=job_title, user_id=candidate_id)
            
            if not results:
                return ""
                
            memories = [res["memory"] for res in results]
            logger.info(f"Retrieved {len(memories)} Mem0 records for {candidate_id}")
            
            # Combine into a context string
            context = "PREVIOUS KNOWLEDGE ABOUT CANDIDATE:\n"
            for mem in memories:
                context += f"- {mem}\n"
                
            return context
        except Exception as e:
            logger.error(f"Mem0 search failed for {candidate_id}: {e}")
            return ""

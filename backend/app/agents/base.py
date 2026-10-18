"""
Base Adapter for AutoGen agents.

This module provides factory functions and a Groq-native client that create
LLM connections based on application configuration.

Architecture
------------
* **OpenAI path** : uses AutoGen's `OpenAIChatCompletionClient` + native
  `response_format=<PydanticModel>` structured outputs (beta.parse).
* **Groq path**   : uses the `groq` SDK (`AsyncGroq`) directly, bypassing
  the `openai` package entirely.  This is necessary because the `openai`
  package's C extension `jiter.pyd` is blocked by Windows Application Control
  policies on some machines.  The `groq` SDK is pure-Python and has no such
  restriction.

Both paths return structured Pydantic objects; callers use `parse_json_safely`
to convert the raw JSON string Groq returns.
"""

import asyncio
from typing import TypeVar, Type
from pydantic import BaseModel, ValidationError
import json

from app.core.config import get_settings
from app.observability.logging import get_logger

logger = get_logger(__name__)

T = TypeVar('T', bound=BaseModel)


def is_groq() -> bool:
    """Returns True if the current LLM provider is Groq."""
    return get_settings().llm_provider == "groq"


def get_json_schema_instruction(model: Type[T]) -> str:
    """
    Returns a system prompt suffix instructing the LLM to respond with JSON
    matching the given Pydantic model's schema.

    Used by Groq agents (where response_format=PydanticModel is not supported)
    to embed the schema directly in the system message.
    """
    schema = model.model_json_schema()
    schema_str = json.dumps(schema, indent=2)
    return (
        "\n\nYou MUST respond with a single valid JSON object that conforms EXACTLY "
        "to this schema. Do NOT include any text before or after the JSON. "
        "Do NOT wrap it in markdown code blocks.\n\n"
        f"Required JSON schema:\n{schema_str}"
    )


def create_openai_client(response_format: Type[T] | None = None,
                          temperature: float | None = None):
    """
    Creates an AutoGen `OpenAIChatCompletionClient` for the OpenAI path.
    Not called when provider is Groq.
    """
    from autogen_ext.models.openai import OpenAIChatCompletionClient
    settings = get_settings()

    client_kwargs = {
        "model": settings.openai_model or "gpt-4o",
        "api_key": settings.openai_api_key or "sk-dummy-key",
        "max_tokens": settings.openai_max_tokens,
        "temperature": temperature if temperature is not None else settings.openai_temperature,
    }
    if response_format is not None:
        client_kwargs["response_format"] = response_format

    return OpenAIChatCompletionClient(**client_kwargs)


def create_groq_client():
    """
    Creates an `AsyncGroq` client using the groq SDK.
    The groq SDK is pure Python and does NOT require jiter or openai.
    """
    import groq
    settings = get_settings()
    api_key = settings.groq_api_key.strip() if settings.groq_api_key else ""
    if not api_key:
        raise groq.AuthenticationError(
            message="GROQ_API_KEY is not configured on the server. Please set GROQ_API_KEY in environment variables.",
            response=None,
            body=None,
        )
    return groq.AsyncGroq(api_key=api_key)


async def groq_generate(
    system_prompt: str,
    user_message: str,
    output_model: Type[T],
    temperature: float = 0.7,
    max_tokens: int | None = None,
    max_retries: int = 3,
) -> T:
    """
    Call Groq directly and return a parsed Pydantic object.
    Includes retry logic with backoff for rate limits and connection issues,
    and fallback model selection for missing models.

    Args:
        system_prompt: The agent's system message (should already contain JSON schema instruction).
        user_message: The user/task message.
        output_model: Pydantic model to parse the response into.
        temperature: Sampling temperature.
        max_tokens: Maximum tokens for response (defaults to 1024 to respect TPM budgets).
        max_retries: Number of retries on 429 rate limit or connection error.

    Returns:
        A validated instance of `output_model`.
    """
    import groq
    settings = get_settings()
    client = create_groq_client()
    target_model = settings.groq_model or "openai/gpt-oss-120b"
    token_limit = max_tokens if max_tokens is not None else min(settings.openai_max_tokens, 2048)

    retries = 0
    backoff = 2.0
    model_fallback_attempted = False

    while True:
        try:
            response = await client.chat.completions.create(
                model=target_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                response_format={"type": "json_object"},
                temperature=temperature,
                max_tokens=token_limit,
            )
            raw = response.choices[0].message.content
            logger.debug(f"Groq raw response (first 300 chars): {raw[:300]}")
            return parse_json_safely(raw, output_model)
        except groq.NotFoundError as err:
            if model_fallback_attempted:
                logger.error(f"Fallback Groq model '{target_model}' also not found: {err}")
                raise
            model_fallback_attempted = True
            logger.warning(f"Groq model '{target_model}' not found. Falling back to alternative model: {err}")
            fallback_models = ["openai/gpt-oss-120b", "openai/gpt-oss-20b"]
            target_model = next((m for m in fallback_models if m != target_model), "openai/gpt-oss-20b")
        except groq.BadRequestError as err:
            err_str = str(err)
            if "json_validate_failed" in err_str and retries < max_retries:
                retries += 1
                token_limit = min(token_limit + 1024, settings.openai_max_tokens)
                logger.warning(
                    f"Groq JSON validation failed (likely token truncation). Increased max_tokens to {token_limit} and retrying ({retries}/{max_retries}): {err}"
                )
                await asyncio.sleep(1.0)
                continue
            logger.error(f"Groq BadRequestError: {err}")
            raise
        except (ValidationError, json.JSONDecodeError) as err:
            retries += 1
            if retries > max_retries:
                logger.error(f"Malformed LLM output exceeded max retries ({max_retries}): {err}")
                raise
            logger.warning(
                f"Malformed LLM output received (attempt {retries}/{max_retries}). Retrying generation: {err}"
            )
            await asyncio.sleep(1.0)
        except (groq.RateLimitError, groq.APIConnectionError) as err:
            retries += 1
            if retries > max_retries:
                logger.error(f"Groq call exceeded max retries ({max_retries}): {err}")
                raise
            sleep_time = backoff
            if hasattr(err, "response") and err.response is not None:
                retry_after = getattr(err.response, "headers", {}).get("retry-after")
                if retry_after:
                    try:
                        sleep_time = max(float(retry_after), sleep_time)
                    except (ValueError, TypeError):
                        pass
            # Bound single wait time to 15 seconds to ensure total wait time is strictly bounded
            sleep_time = min(sleep_time, 15.0)
            logger.warning(
                f"Groq {type(err).__name__} (attempt {retries}/{max_retries}). Retrying in {sleep_time:.1f}s: {err}"
            )
            await asyncio.sleep(sleep_time)
            backoff *= 1.5


def parse_json_safely(raw_text: str, model: Type[T]) -> T:
    """
    Safely parse JSON from the LLM, stripping markdown code fences if present.
    Even with structured outputs, models sometimes wrap JSON in ```json blocks.
    """
    cleaned = raw_text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return model.model_validate_json(cleaned.strip())

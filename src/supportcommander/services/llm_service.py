import time

import openai
from openai import AsyncOpenAI

from supportcommander.core.config import get_settings
from supportcommander.services import cost_tracker
from supportcommander.services.llm_models import LLMResult

settings = get_settings()

client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=30.0)


class LLMServiceError(Exception):
    """Base error for model service failures"""

class LLMAuthenticationError(LLMServiceError):
    """OpenAI Authentication Failed"""

class LLMRateLimitError(LLMServiceError):
    """OpenAI Rate Limit Reached"""

class LLMConnectionError(LLMServiceError):
    """OpenAI Connection Failed"""


async def generate_text(
    *,
    instructions: str,
    input_text: str,
    _agent_name: str = "llm",
) -> LLMResult:
    try:
        t0 = time.perf_counter()
        response = await client.responses.create(
            model=settings.openai_model,
            instructions=instructions,
            input=input_text,
        )
        latency_ms = (time.perf_counter() - t0) * 1000

        # Extract token usage from the response object.
        usage = getattr(response, "usage", None)
        input_tokens  = int(getattr(usage, "input_tokens",  0) or 0)
        output_tokens = int(getattr(usage, "output_tokens", 0) or 0)

        result = LLMResult(
            text          = response.output_text,
            model         = settings.openai_model,
            request_id    = response._request_id,
            input_tokens  = input_tokens,
            output_tokens = output_tokens,
            latency_ms    = latency_ms,
        )

        # Register with any active cost tracker for this async context.
        cost_tracker.register(_agent_name, result)

        return result

    except openai.AuthenticationError as exc:
        raise LLMAuthenticationError("OpenAI authentication failed.") from exc

    except openai.RateLimitError as exc:
        raise LLMRateLimitError("OpenAI rate limit reached") from exc

    except openai.APIConnectionError as exc:
        raise LLMConnectionError("Could not connect to OpenAI") from exc

    except openai.APIError as exc:
        raise LLMServiceError("OpenAI API request failed") from exc

from __future__ import annotations

import openai
from openai import AsyncOpenAI

from supportcommander.core.config import get_settings
from supportcommander.services.embedding_models import EmbeddingResult

settings = get_settings()
client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=30.0)


class EmbeddingServiceError(Exception):
    """Embedding generation failed"""


async def generate_embedding(text: str) -> EmbeddingResult:
    clean_text = text.strip()
    if not clean_text:
        raise ValueError("Cannot generate embedding for empty text")

    try:
        response = await client.embeddings.create(
            model= settings.openai_embedding_model,
            input= clean_text,
        )
        embedding = response.data[0].embedding

        return EmbeddingResult(
            embedding= embedding,
            model= settings.openai_embedding_model,
        )
    except openai.AuthenticationError as exc:
        raise EmbeddingServiceError("OpenAI authentication failed while generating embedding.") from exc

    except openai.RateLimitError as exc:
        raise EmbeddingServiceError("OpenAI embedding rate limit was reached.") from exc

    except openai.APIConnectionError as exc:
        raise EmbeddingServiceError("Could not connect to OpenAI embedding service.") from exc

    except openai.APIError as exc:
        raise EmbeddingServiceError("OpenAI embedding request failed.") from exc
    
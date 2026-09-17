from fastapi import APIRouter

from supportcommander.core.config import get_settings

router = APIRouter(prefix="/api/v1/llm", tags=["LLM"])

@router.get("/config")
def llm_config() -> dict:
    settings = get_settings()
    return {
        "provider": "OpenAI",
        "model" : settings.openai_model,
        "configured": bool(settings.openai_api_key[:4])
    }
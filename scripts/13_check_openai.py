import asyncio
from supportcommander.core.config import get_settings
from supportcommander.services.llm_service import generate_text

async def main() -> None:
    settings = get_settings()

    print("="*70)
    print("SupportCommander OpenAI Check")
    print("="*70)
    print(f"API Key: {settings.openai_api_key[:4]}...")
    print(f"Model: {settings.openai_model}")
    print("="*70)

    print("Generating text...")
    result = await generate_text(
        instructions = "You are a helpful assistant that can answer questions and help with tasks.",
        input_text = "What is the capital of India?"
    )
    print()
    print("Model response:")
    print(result.text)

    print()
    print("Model:", result.model)
    print("Request ID:", result.request_id)

    print()
    print("=" * 70)
    print(
        "OpenAI client test successful!"
    )
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
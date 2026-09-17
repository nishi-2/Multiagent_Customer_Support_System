import asyncio

from supportcommander.services.embedding_service import generate_embedding


async def main() -> None:
    print("=" * 70)
    print("SupportCommander Embedding Check")
    print("=" * 70)

    result = await generate_embedding("Customer requests a refund.")

    print(f"Embedding model: {result.model}")
    print(f"Vector dimensions: {len(result.embedding)}")
    print(f"First five values: {result.embedding[:5]}")

    print()
    print("=" * 70)
    print("Embedding service successful!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())

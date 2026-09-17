import asyncio
from datetime import datetime, timezone

from supportcommander.db.mongo import get_database
from supportcommander.rag.policy_chunker import chunk_policies
from supportcommander.rag.policy_loader import load_all_policies
from supportcommander.services.embedding_service import generate_embedding


async def main() -> None:
    print("=" * 70)
    print("SupportCommander Policy Index Builder")
    print("=" * 70)

    policies = load_all_policies()
    chunks = chunk_policies(policies)

    print(f"Policies: {len(policies)}")
    print(f"Chunks: {len(chunks)}")

    db = get_database()

    collection = db.policy_chunks
    records = []

    for index, chunk in enumerate(chunks, start=1):
        print(f"Embedding \n{index}/{len(chunks)}\n{chunk.chunk_id}")
        embedding_result = await generate_embedding(chunk.content)
        record = chunk.model_dump()
        record["embedding"] = embedding_result.embedding
        record["embedding_model"] = embedding_result.model
        record["indexed_at"] = datetime.now(timezone.utc)
        records.append(record)

    # Development rebuild: replace index each run.
    collection.delete_many({})

    if records:
        collection.insert_many(records)

    collection.create_index("chunk_id", unique=True)
    collection.create_index("policy_id")
    collection.create_index("category")

    print()
    print(f"Stored chunks: {len(records)}")
    print()
    print("=" * 70)
    print("Policy index build successful!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())

 
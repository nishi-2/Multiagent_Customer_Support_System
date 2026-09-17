from supportcommander.rag.policy_chunker import chunk_policies
from supportcommander.rag.policy_loader import load_all_policies



def main() -> None:
    print("=" * 70)
    print("SupportCommander Policy Chunk Check")
    print("=" * 70)

    policies = load_all_policies()

    chunks = chunk_policies(policies)

    print(f"Policies: {len(policies)}")
    print(f"Chunks: {len(chunks)}")

    if not chunks:
        raise RuntimeError("No policy chunks generated.")

    chunk_ids = [chunk.chunk_id for chunk in chunks]

    if len(chunk_ids) != len(set(chunk_ids)):
        raise RuntimeError("Duplicate chunk IDs detected.")

    print("Unique chunk IDs: OK"  )

    print()
    print("Example chunk:")

    print("-" * 70)

    print(chunks[0].content)

    print()
    print("=" * 70)
    print("Policy chunking successful!")
    print("=" * 70)


if __name__ == "__main__":
    main()
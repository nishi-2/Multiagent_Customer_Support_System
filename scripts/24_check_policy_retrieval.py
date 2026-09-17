import asyncio

from supportcommander.rag.retriever import retrieve_policies
from supportcommander.rag.retriever import retrieve_for_intent


async def main() -> None:

    print("=" * 70)
    print("SupportCommander Policy Retrieval Check")
    print("=" * 70)

    query = """I want my money back of 450 USD."""

    print(f"Query: {query}")

    results = await retrieve_for_intent(query, intent="refund_request", top_k=5)

    print()

    for index, result in enumerate(results, start=1,):

        print(f"Result #{index}")

        print(f"Policy: {result.policy_title}")

        print(f"Section: {result.section}")

        print(f"Score: {round(result.similarity_score, 4)}")

        print(result.content)

        print("-" * 70)

    print()
    print("=" * 70)
    print("Policy retrieval successful!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
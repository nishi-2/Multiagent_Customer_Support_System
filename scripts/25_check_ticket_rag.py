import asyncio

from supportcommander.agents.triage_agent import run_triage_agent
from supportcommander.graph.state_factory import create_initial_state
from supportcommander.rag.retriever import retrieve_for_graph
from supportcommander.services.ticket_service import get_ticket


async def main() -> None:

    print("=" * 70)
    print("SupportCommander Ticket RAG Check")
    print("=" * 70)

    ticket = get_ticket(1)

    if ticket is None:
        raise RuntimeError("Ticket 1 was not found.")

    state = create_initial_state(ticket_id=1, ticket=ticket)
    state = await run_triage_agent(state)

    triage = state.get("triage")

    if triage is None:
        raise RuntimeError("Triage result was not created.")

    print(f"Ticket ID: {ticket['ticket_id']}")
    print(f"Dataset type: {ticket['ticket_type']}")
    print(f"Triage intent: {triage.intent}")

    print()

    policies = await retrieve_for_graph(ticket["ticket_text"], intent=triage.intent, top_k=3)

    state["retrieved_policies"] = policies

    print("Retrieved policies:")

    print()

    for policy in policies:
        print(policy.policy_id)

        print(f"Policy: {policy.title}")

        print(f"Relevance: {round(policy.relevance_score or 0, 4)}")

        print("-" * 70)

    print()
    print("=" * 70)
    print("Ticket RAG successful!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
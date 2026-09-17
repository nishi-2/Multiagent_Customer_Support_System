import asyncio

from supportcommander.agents.triage_agent import run_triage_agent
from supportcommander.graph.state_factory import create_initial_state
from supportcommander.services.ticket_service import get_ticket
from supportcommander.agents.triage_evaluation import expected_intent


async def test_ticket(ticket_id: int) -> None:
    ticket = get_ticket(ticket_id)

    if ticket is None:
        return

    state = create_initial_state(ticket_id=ticket_id, ticket=ticket,)
    state = await run_triage_agent(state)
    triage = state.get("triage")

    print()
    print("-" * 70)
    print("Ticket:", ticket_id)
    print("Dataset type:", ticket["ticket_type"])
    expected = expected_intent(ticket["ticket_type"])

    if triage:
        print("AI intent:", triage.intent)

        matches = (triage.intent == expected)
        print("Expected intent:", expected,)
        print("Intent match:", matches,)
        
        print("Urgency:", triage.urgency)
        print("Confidence:", triage.confidence)
        print("Summary:", triage.summary)

    print("Escalated:", state["escalated"])


async def main() -> None:
    print("=" * 70)
    print("SupportCommander Triage Samples")
    print("=" * 70)

    ticket_ids = [1,2]

    for ticket_id in ticket_ids:
        await test_ticket(ticket_id)

    print()
    print("=" * 70)
    print("Triage sample test complete!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
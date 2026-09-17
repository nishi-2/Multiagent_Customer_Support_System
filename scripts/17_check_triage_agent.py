import asyncio

from supportcommander.agents.triage_agent import run_triage_agent
from supportcommander.graph.state_factory import create_initial_state
from supportcommander.graph.state_utils import serialize_state
from supportcommander.services.ticket_service import get_ticket

from supportcommander.services.workflow_service import save_workflow_state


async def main() -> None:
    print("=" * 70)
    print("SupportCommander Triage Agent Check")
    print("=" * 70)

    ticket = get_ticket(1)

    if ticket is None:
        raise RuntimeError("Ticket 1 was not found.")

    print(f"Ticket ID: {ticket['ticket_id']}")
    print(f"Dataset type: {ticket['ticket_type']}")
    print(f"Dataset priority: {ticket['ticket_priority']}")

    state = create_initial_state(ticket_id=1, ticket=ticket)

    print()
    print("Running Triage Agent...")

    state = await run_triage_agent(state)

    save_workflow_state(state)
    print("Workflow persisted: OK")

    serialized = serialize_state(state)
    triage = serialized["triage"]

    print()
    print("Agent result")
    print("-" * 40)

    print("Intent:", triage["intent"])
    print("Urgency:", triage["urgency"])
    print("Confidence:", triage["confidence"])
    print("Summary:", triage["summary"])
    print("Needs customer context:", triage["needs_customer_context"])
    print("Needs policy lookup:", triage["needs_policy_lookup"])
    print("Needs risk review:", triage["needs_risk_review"])
    print()
    print("Next stage:", serialized["next_stage"])
    print("Audit events:", len(serialized["audit_events"]))

    print()
    print("=" * 70)
    print("Triage Agent successful!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
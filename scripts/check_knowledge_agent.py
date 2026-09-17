import asyncio

from supportcommander.agents.knowledge_agent import (
    run_knowledge_agent,
)
from supportcommander.agents.triage_agent import (
    run_triage_agent,
)
from supportcommander.graph.state_factory import (
    create_initial_state,
)
from supportcommander.services.ticket_service import (
    get_ticket,
)


async def main() -> None:

    ticket = get_ticket(
        1
    )

    if ticket is None:
        raise RuntimeError(
            "Ticket 1 was not found."
        )

    state = create_initial_state(
        ticket_id=1,
        ticket=ticket,
    )

    state = await run_triage_agent(
        state
    )

    if state.get(
        "escalated"
    ):
        raise RuntimeError(
            "Ticket escalated during triage."
        )

    state = (
        await run_knowledge_agent(
            state
        )
    )

    policies = state.get(
        "retrieved_policies"
    )

    if not policies:
        raise RuntimeError(
            "No policies were retrieved."
        )

    print(
        "Triage intent:",
        state["triage"].intent,
    )

    print()

    for policy in policies:

        print(
            policy.policy_id,
            "|",
            policy.title,
            "|",
            round(
                policy.relevance_score
                or 0,
                4,
            ),
        )

    print()
    print(
        "Knowledge Agent successful!"
    )


if __name__ == "__main__":
    asyncio.run(main())

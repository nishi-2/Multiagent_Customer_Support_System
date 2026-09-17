import asyncio

from supportcommander.graph.coordinator import (
    coordinator_graph,
)
from supportcommander.graph.state_factory import (
    create_initial_state,
)
from supportcommander.services.ticket_service import (
    get_ticket,
)


async def main() -> None:

    print("=" * 70)
    print(
        "SupportCommander Coordinator Graph Check"
    )
    print("=" * 70)

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

    result = await (
        coordinator_graph.ainvoke(
            state
        )
    )

    print(
        "Triage:",
        bool(result.get("triage")),
    )

    print(
        "Context:",
        bool(
            result.get(
                "customer_context"
            )
        ),
    )

    print(
        "Risk:",
        bool(
            result.get(
                "risk_assessment"
            )
        ),
    )

    print(
        "Policies:",
        len(
            result.get(
                "retrieved_policies",
                [],
            )
        ),
    )

    print(
        "Resolution plan:",
        bool(
            result.get(
                "resolution_plan"
            )
        ),
    )

    print()

    print(
        "Stage:",
        result.get(
            "current_stage"
        ),
    )

    print(
        "Next:",
        result.get(
            "next_stage"
        ),
    )

    print(
        "Escalated:",
        result.get("escalated"),
    )

    print()
    print("=" * 70)
    print(
        "Coordinator graph successful!"
    )
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())

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
        "SupportCommander Policy Gate Check"
    )
    print("=" * 70)

    ticket = get_ticket(
        1
    )

    if ticket is None:
        raise RuntimeError(
            "Ticket 1 not found."
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

    if result.get(
        "escalated"
    ):
        print(
            "Workflow escalated "
            "during triage."
        )

        return

    gate = result.get(
        "policy_gate_result"
    )

    if gate is None:
        raise RuntimeError(
            "Policy Gate did not run."
        )

    print(
        "Overall decision:",
        gate.decision,
    )

    print(
        "Human approval:",
        gate.requires_human_approval,
    )

    print()

    print(
        "Action decisions:"
    )

    for decision in (
        gate.action_decisions
    ):

        print(
            "-",
            decision.action_type,
            "→",
            decision.decision,
        )

        print(
            "  Reason:",
            decision.reason,
        )

        print(
            "  Rules:",
            decision.rule_ids,
        )

    print()

    print(
        "Current stage:",
        result.get(
            "current_stage"
        ),
    )

    print(
        "Next stage:",
        result.get(
            "next_stage"
        ),
    )

    print()
    print("=" * 70)
    print(
        "Policy Gate successful!"
    )
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())

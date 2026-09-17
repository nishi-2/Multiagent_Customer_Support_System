import asyncio

from supportcommander.agents.resolution_planner import (
    run_resolution_planner,
)
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
        "SupportCommander Resolution "
        "Planner Check"
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

    state = await (
        coordinator_graph.ainvoke(
            state
        )
    )

    if state.get(
        "escalated"
    ):
        raise RuntimeError(
            "Ticket was escalated "
            "before planning."
        )

    plan = state.get(
        "resolution_plan"
    )

    if plan is None:
        raise RuntimeError(
            "No ResolutionPlan created."
        )

    print(
        "Summary:",
        plan.summary,
    )

    print(
        "Confidence:",
        plan.confidence,
    )

    print(
        "Policy basis:",
        plan.policy_basis,
    )

    print()

    print(
        "Proposed actions:"
    )

    for action in plan.actions:

        print(
            "-",
            action.action_type,
        )

        print(
            "  Order:",
            action.order_id,
        )

        print(
            "  Amount:",
            action.amount,
        )

        print(
            "  Reason:",
            action.reason,
        )

    print()

    print(
        "Next stage:",
        state.get(
            "next_stage"
        ),
    )

    print()
    print("=" * 70)
    print(
        "Resolution Planner successful!"
    )
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())

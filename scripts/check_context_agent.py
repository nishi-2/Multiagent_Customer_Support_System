import asyncio

from supportcommander.agents.context_agent import (
    run_context_agent,
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
        "SupportCommander Context Agent Check"
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

    state = await run_context_agent(
        state
    )

    context = state.get(
        "customer_context"
    )

    if context is None:
        raise RuntimeError(
            "Context Agent returned no context."
        )

    print(
        "Customer:",
        bool(context.customer),
    )

    print(
        "Order:",
        bool(context.order),
    )

    print(
        "Payment:",
        bool(context.payment),
    )

    print(
        "Shipment:",
        bool(context.shipment),
    )

    print(
        "Refund records:",
        len(
            context.refund_history
        ),
    )

    print(
        "Replacement records:",
        len(
            context.replacement_history
        ),
    )

    print(
        "Missing data:",
        context.missing_data,
    )

    print()
    print("=" * 70)
    print(
        "Context Agent successful!"
    )
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())

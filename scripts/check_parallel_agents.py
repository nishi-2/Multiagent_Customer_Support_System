import asyncio
from copy import deepcopy

from supportcommander.agents.context_agent import (
    run_context_agent,
)
from supportcommander.agents.risk_agent import (
    run_risk_agent,
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

    initial_state = (
        create_initial_state(
            ticket_id=1,
            ticket=ticket,
        )
    )

    context_state = deepcopy(
        initial_state
    )

    risk_state = deepcopy(
        initial_state
    )

    context_result, risk_result = (
        await asyncio.gather(
            run_context_agent(
                context_state
            ),
            run_risk_agent(
                risk_state
            ),
        )
    )

    assert (
        context_result.get(
            "customer_context"
        )
        is not None
    )

    assert (
        risk_result.get(
            "risk_assessment"
        )
        is not None
    )

    print(
        "Context Agent: OK"
    )

    print(
        "Risk Agent: OK"
    )

    print(
        "Independent parallel execution: OK"
    )


if __name__ == "__main__":
    asyncio.run(main())

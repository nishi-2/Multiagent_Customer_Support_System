import asyncio

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

    print("=" * 70)
    print(
        "SupportCommander Risk Agent Check"
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

    state = await run_risk_agent(
        state
    )

    risk = state.get(
        "risk_assessment"
    )

    if risk is None:
        raise RuntimeError(
            "Risk Agent returned no result."
        )

    print(
        "Risk level:",
        risk.risk_level,
    )

    print(
        "Risk score:",
        risk.risk_score,
    )

    print(
        "Signals:",
        risk.risk_signals,
    )

    print(
        "Human review:",
        risk.requires_human_review,
    )

    print(
        "Rationale:",
        risk.rationale,
    )

    print()
    print("=" * 70)
    print(
        "Risk Agent successful!"
    )
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())

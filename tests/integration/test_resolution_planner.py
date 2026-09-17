import pytest

from supportcommander.graph.coordinator import (
    coordinator_graph,
)
from supportcommander.graph.state_factory import (
    create_initial_state,
)
from supportcommander.services.ticket_service import (
    get_ticket,
)


@pytest.mark.asyncio
async def test_resolution_planner():

    ticket = get_ticket(
        1
    )

    assert ticket is not None

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
        pytest.skip(
            "Triage escalated this ticket."
        )

    plan = result.get(
        "resolution_plan"
    )

    assert plan is not None

    assert (
        0.0
        <= plan.confidence
        <= 1.0
    )

    assert (
        result[
            "current_stage"
        ].value
        in {
            "approval",
            "action_execution",
            "verification",
            "response_drafting",
        }
    )

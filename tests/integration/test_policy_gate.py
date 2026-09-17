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
async def test_policy_gate_runs():

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
            "Triage escalated ticket."
        )

    gate = result.get(
        "policy_gate_result"
    )

    assert gate is not None

    assert gate.decision in {
        "allow",
        "require_approval",
        "reject",
        "escalate",
    }

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

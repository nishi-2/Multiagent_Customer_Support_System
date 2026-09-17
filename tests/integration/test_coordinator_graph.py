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
async def test_coordinator_graph_runs():

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

    assert (
        result.get("triage")
        is not None
    )

    if result.get("escalated"):
        assert (
            result[
                "current_stage"
            ].value
            == "escalated"
        )
        return

    assert (
        result.get(
            "customer_context"
        )
        is not None
    )

    assert (
        result.get(
            "risk_assessment"
        )
        is not None
    )

    assert result.get(
        "retrieved_policies"
    )

    assert result.get(
        "resolution_plan"
    ) is not None

    assert result.get(
        "policy_gate_result"
    ) is not None

    decision = (
        result[
            "policy_gate_result"
        ].decision
    )

    assert decision in {
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

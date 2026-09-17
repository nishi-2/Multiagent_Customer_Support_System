import pytest

from supportcommander.graph.coordinator import coordinator_graph
from supportcommander.graph.state_factory import create_initial_state
from supportcommander.services.ticket_service import get_ticket
from supportcommander.services.workflow_service import (
    get_workflow_state,
    save_workflow_state,
)


@pytest.mark.asyncio
async def test_full_workflow_produces_valid_state():

    ticket = get_ticket(1)
    assert ticket is not None

    state = create_initial_state(
        ticket_id=1,
        ticket=ticket,
    )

    result = await coordinator_graph.ainvoke(state)

    assert result.get("current_stage") is not None
    assert result.get("workflow_id") is not None
    assert len(result.get("audit_events") or []) > 0


@pytest.mark.asyncio
async def test_full_workflow_saves_to_mongodb():

    ticket = get_ticket(1)
    assert ticket is not None

    state = create_initial_state(
        ticket_id=1,
        ticket=ticket,
    )

    result = await coordinator_graph.ainvoke(state)
    save_workflow_state(result)

    wf_id = result.get("workflow_id")
    assert wf_id is not None

    doc = get_workflow_state(wf_id)
    assert doc is not None
    assert doc["workflow_id"] == wf_id


@pytest.mark.asyncio
async def test_non_escalated_workflow_reaches_terminal_stage():

    ticket = get_ticket(1)
    assert ticket is not None

    state = create_initial_state(
        ticket_id=1,
        ticket=ticket,
    )

    result = await coordinator_graph.ainvoke(state)

    if result.get("escalated"):
        pytest.skip("Ticket was escalated.")

    terminal_stages = {
        "approval",
        "response_drafting",
        "completed",
        "failed",
    }

    assert (
        str(result.get("current_stage"))
        in terminal_stages
    ), f"Unexpected stage: {result.get('current_stage')}"


@pytest.mark.asyncio
async def test_allow_decision_produces_final_response():

    ticket = get_ticket(1)
    assert ticket is not None

    state = create_initial_state(
        ticket_id=1,
        ticket=ticket,
    )

    result = await coordinator_graph.ainvoke(state)

    if result.get("escalated"):
        pytest.skip("Ticket escalated.")

    gate = result.get("policy_gate_result")

    if gate is None or gate.decision != "allow":
        pytest.skip(
            f"Gate decision is not 'allow' ({gate.decision if gate else 'none'})."
        )

    final = result.get("final_response")
    assert final is not None, "final_response expected for 'allow' decision"
    assert final.resolution_status in {
        "resolved",
        "pending_customer",
        "escalated",
        "failed",
    }
    assert len(final.message.strip()) >= 20

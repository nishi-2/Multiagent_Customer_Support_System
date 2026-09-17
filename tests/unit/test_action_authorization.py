import pytest

from supportcommander.graph.models import (
    ApprovalState,
    CustomerContext,
    PolicyGateResult,
    ProposedAction,
    ResolutionPlan,
    RiskAssessment,
)
from supportcommander.services.action_execution_service import (
    execute_resolution_plan,
)


def build_state(
    *,
    gate_decision: str,
    approval_status: str | None = None,
) -> dict:

    plan = ResolutionPlan(
        summary="Refund proposed.",
        actions=[
            ProposedAction(
                action_type="refund",
                reason="Test refund.",
                order_id="ORD-000001",
                amount=50.0,
            )
        ],
        policy_basis=["POL-REFUND-001"],
        customer_response_strategy="Explain.",
        confidence=0.9,
    )

    gate = PolicyGateResult(
        decision=gate_decision,
        reasons=["test"],
        requires_human_approval=(
            gate_decision != "allow"
        ),
    )

    context = CustomerContext(
        customer={"customer_id": "CUST-000001"},
        order={"order_id": "ORD-000001"},
    )

    risk = RiskAssessment(
        risk_level="low",
        risk_score=0.1,
    )

    state: dict = {
        "resolution_plan": plan,
        "policy_gate_result": gate,
        "customer_context": context,
        "risk_assessment": risk,
    }

    if approval_status is not None:
        state["approval"] = ApprovalState(
            required=True,
            status=approval_status,
        )

    return state


@pytest.mark.asyncio
async def test_pending_approval_cannot_execute():

    state = build_state(
        gate_decision="require_approval",
        approval_status="pending",
    )

    with pytest.raises(
        RuntimeError,
        match="not authorized",
    ):
        await execute_resolution_plan(
            state
        )


@pytest.mark.asyncio
async def test_rejected_approval_cannot_execute():

    state = build_state(
        gate_decision="require_approval",
        approval_status="rejected",
    )

    with pytest.raises(
        RuntimeError,
        match="not authorized",
    ):
        await execute_resolution_plan(
            state
        )


@pytest.mark.asyncio
async def test_no_approval_state_cannot_execute():

    state = build_state(
        gate_decision="require_approval",
    )

    with pytest.raises(
        RuntimeError,
        match="not authorized",
    ):
        await execute_resolution_plan(
            state
        )

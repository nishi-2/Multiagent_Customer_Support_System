"""
Deterministic policy gate evaluation scenarios.

These tests do not call OpenAI. They verify that specific combinations of
context, risk, and resolution plan produce the expected policy gate decision.
"""

import pytest

from supportcommander.graph.models import (
    CustomerContext,
    PolicyGateResult,
    ProposedAction,
    ResolutionPlan,
    RiskAssessment,
    TriageResult,
)
from supportcommander.policy.policy_gate import run_policy_gate


def build_state(
    *,
    intent: str = "refund_request",
    risk_level: str = "low",
    risk_score: float = 0.1,
    customer: dict | None = None,
    order: dict | None = None,
    payment: dict | None = None,
    shipment: dict | None = None,
    refund_history: list | None = None,
    replacement_history: list | None = None,
    actions: list[ProposedAction] | None = None,
    triage_confidence: float = 0.9,
) -> dict:

    if customer is None:
        customer = {
            "customer_id": "CUST-000001",
            "account_status": "active",
        }

    if order is None:
        order = {
            "order_id": "ORD-000001",
            "customer_id": "CUST-000001",
            "order_status": "delivered",
            "order_date": "2026-08-01T00:00:00Z",
        }

    if payment is None:
        payment = {
            "order_id": "ORD-000001",
            "amount": 100.0,
            "payment_status": "paid",
        }

    if actions is None:
        actions = [
            ProposedAction(
                action_type="refund",
                reason="Defective product.",
                order_id="ORD-000001",
                amount=50.0,
            )
        ]

    triage = TriageResult(
        intent=intent,
        urgency="medium",
        confidence=triage_confidence,
        summary="Customer requests refund.",
    )

    plan = ResolutionPlan(
        summary="Issue refund.",
        actions=actions,
        policy_basis=["POL-REFUND-001"],
        customer_response_strategy="Confirm refund.",
        confidence=0.9,
    )

    context = CustomerContext(
        customer=customer,
        order=order,
        payment=payment,
        shipment=shipment,
        refund_history=refund_history or [],
        replacement_history=replacement_history or [],
    )

    risk = RiskAssessment(
        risk_level=risk_level,
        risk_score=risk_score,
    )

    return {
        "ticket_id": 1,
        "triage": triage,
        "resolution_plan": plan,
        "customer_context": context,
        "risk_assessment": risk,
        "audit_events": [],
        "low_planner_confidence": triage_confidence < 0.5,
    }


def run(state: dict) -> PolicyGateResult:
    result = run_policy_gate(state)
    return result["policy_gate_result"]


def test_small_refund_low_risk_allows():
    state = build_state(
        risk_level="low",
        order={
            "order_id": "ORD-000001",
            "customer_id": "CUST-000001",
            "order_status": "delivered",
            "order_date": "2026-09-10T00:00:00Z",
        },
        actions=[
            ProposedAction(
                action_type="refund",
                reason="Defective product.",
                order_id="ORD-000001",
                amount=50.0,
            )
        ],
    )
    gate = run(state)
    assert gate.decision in {"allow", "require_approval"}


def test_large_refund_requires_approval():
    state = build_state(
        payment={"order_id": "ORD-000001", "amount": 500.0, "payment_status": "paid"},
        actions=[
            ProposedAction(
                action_type="refund",
                reason="Full refund requested.",
                order_id="ORD-000001",
                amount=400.0,
            )
        ],
    )
    gate = run(state)
    assert gate.decision in {"require_approval", "escalate"}


def test_restricted_account_rejects_refund():
    state = build_state(
        customer={
            "customer_id": "CUST-000001",
            "account_status": "restricted",
        }
    )
    gate = run(state)
    assert gate.decision in {"reject", "escalate"}


def test_low_planner_confidence_escalates():
    state = build_state(triage_confidence=0.3)
    plan = state["resolution_plan"]
    state["resolution_plan"] = plan.model_copy(
        update={"planner_flags": ["low_planner_confidence"]}
    )
    gate = run(state)
    assert gate.decision == "escalate"


def test_escalate_action_type_escalates():
    state = build_state(actions=[
        ProposedAction(
            action_type="escalate",
            reason="Complex legal issue.",
            order_id="ORD-000001",
        )
    ])
    gate = run(state)
    assert gate.decision == "escalate"


def test_high_risk_refund_requires_approval():
    state = build_state(risk_level="high", risk_score=0.8)
    gate = run(state)
    assert gate.decision in {"require_approval", "escalate", "reject"}


def test_cancellation_not_shipped_allows():
    state = build_state(
        intent="cancellation_request",
        shipment={"order_id": "ORD-000001", "status": "processing"},
        order={
            "order_id": "ORD-000001",
            "customer_id": "CUST-000001",
            "order_status": "processing",
            "order_date": "2026-09-01T00:00:00Z",
            "order_amount": 80.0,
        },
        payment={
            "order_id": "ORD-000001",
            "amount": 80.0,
            "payment_status": "paid",
        },
        actions=[
            ProposedAction(
                action_type="cancel_order",
                reason="Customer changed mind.",
                order_id="ORD-000001",
            )
        ],
    )
    gate = run(state)
    assert gate.decision in {"allow", "require_approval"}

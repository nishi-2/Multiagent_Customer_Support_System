from datetime import (
    datetime,
    timezone,
)

from supportcommander.graph.models import (
    ProposedAction,
)
from supportcommander.policy.gate_rules import (
    evaluate_refund_action,
)


def test_small_low_risk_refund_allowed():

    now = datetime.now(
        timezone.utc
    ).isoformat()

    result = evaluate_refund_action(
        action_index=0,

        action=ProposedAction(
            action_type="refund",
            reason="Eligible refund.",
            order_id="ORD-1",
            amount=100,
        ),

        customer={
            "account_status": "active"
        },

        order={
            "order_id": "ORD-1",
            "created_at": now,
        },

        payment={
            "status": "paid",
            "amount": 200,
        },

        refund_history=[],

        risk_level="low",
    )

    assert result.decision == "allow"


def test_large_refund_requires_approval():

    now = datetime.now(
        timezone.utc
    ).isoformat()

    result = evaluate_refund_action(
        action_index=0,

        action=ProposedAction(
            action_type="refund",
            reason="Refund.",
            order_id="ORD-1",
            amount=450,
        ),

        customer={
            "account_status": "active"
        },

        order={
            "order_id": "ORD-1",
            "created_at": now,
        },

        payment={
            "status": "paid",
            "amount": 500,
        },

        refund_history=[],

        risk_level="low",
    )

    assert (
        result.decision
        == "require_approval"
    )


def test_refund_above_payment_rejected():

    now = datetime.now(
        timezone.utc
    ).isoformat()

    result = evaluate_refund_action(
        action_index=0,

        action=ProposedAction(
            action_type="refund",
            reason="Refund.",
            order_id="ORD-1",
            amount=600,
        ),

        customer={
            "account_status": "active"
        },

        order={
            "created_at": now,
        },

        payment={
            "status": "paid",
            "amount": 500,
        },

        refund_history=[],

        risk_level="low",
    )

    assert (
        result.decision
        == "reject"
    )


def test_high_risk_refund_escalates():

    now = datetime.now(
        timezone.utc
    ).isoformat()

    result = evaluate_refund_action(
        action_index=0,

        action=ProposedAction(
            action_type="refund",
            reason="Refund.",
            order_id="ORD-1",
            amount=100,
        ),

        customer={
            "account_status": "active"
        },

        order={
            "created_at": now,
        },

        payment={
            "status": "paid",
            "amount": 200,
        },

        refund_history=[],

        risk_level="high",
    )

    assert (
        result.decision
        == "escalate"
    )

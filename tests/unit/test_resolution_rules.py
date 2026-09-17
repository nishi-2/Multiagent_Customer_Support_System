import pytest

from supportcommander.agents.resolution_rules import (
    ResolutionValidationError,
    validate_resolution_plan,
)
from supportcommander.graph.models import (
    CustomerContext,
    ProposedAction,
    ResolutionPlan,
    RetrievedPolicy,
)


def build_state():

    return {
        "ticket": {
            "order_id":
                "ORD-000001"
        },

        "customer_context":
            CustomerContext(
                customer={},
                order={
                    "order_id":
                        "ORD-000001",

                    "order_amount":
                        200,
                },
                payment={
                    "amount":
                        200,
                },
            ),

        "retrieved_policies": [
            RetrievedPolicy(
                policy_id=(
                    "POL-REFUND-001"
                ),
                title=(
                    "Refund Policy"
                ),
                content="...",
                source="policy_rag",
                relevance_score=0.9,
            )
        ],
    }


def test_valid_refund_plan():

    state = build_state()

    plan = ResolutionPlan(
        summary="Refund proposed.",

        actions=[
            ProposedAction(
                action_type="refund",
                reason="Eligible refund.",
                order_id="ORD-000001",
                amount=100,
            )
        ],

        policy_basis=[
            "POL-REFUND-001"
        ],

        customer_response_strategy=(
            "Explain next steps."
        ),

        confidence=0.9,
    )

    result = (
        validate_resolution_plan(
            state,
            plan,
        )
    )

    assert result is plan


def test_unknown_policy_rejected():

    state = build_state()

    plan = ResolutionPlan(
        summary="Refund proposed.",

        actions=[
            ProposedAction(
                action_type="refund",
                reason="Refund.",
                order_id="ORD-000001",
                amount=100,
            )
        ],

        policy_basis=[
            "FAKE-POLICY"
        ],

        customer_response_strategy=(
            "Explain next steps."
        ),

        confidence=0.9,
    )

    with pytest.raises(
        ResolutionValidationError
    ):
        validate_resolution_plan(
            state,
            plan,
        )


def test_refund_above_payment_rejected():

    state = build_state()

    plan = ResolutionPlan(
        summary="Refund proposed.",

        actions=[
            ProposedAction(
                action_type="refund",
                reason="Refund.",
                order_id="ORD-000001",
                amount=500,
            )
        ],

        policy_basis=[
            "POL-REFUND-001"
        ],

        customer_response_strategy=(
            "Explain next steps."
        ),

        confidence=0.9,
    )

    with pytest.raises(
        ResolutionValidationError
    ):
        validate_resolution_plan(
            state,
            plan,
        )

from __future__ import annotations

from supportcommander.graph.models import (
    ResolutionPlan,
)


class ResolutionValidationError(
    Exception
):
    """Planner proposed an invalid action."""


def validate_resolution_plan(
    state: dict,
    plan: ResolutionPlan,
) -> ResolutionPlan:

    ticket = state["ticket"]

    context = state[
        "customer_context"
    ]

    order = (
        context.order
        or {}
    )

    known_order_id = (
        order.get("order_id")
        or ticket.get("order_id")
    )

    known_policy_ids = {
        policy.policy_id
        for policy
        in state.get(
            "retrieved_policies",
            [],
        )
    }

    for policy_id in (
        plan.policy_basis
    ):
        if (
            policy_id
            not in known_policy_ids
        ):
            raise ResolutionValidationError(
                "Planner referenced unknown "
                f"policy ID: {policy_id}"
            )

    for action in plan.actions:

        if (
            action.order_id
            and known_order_id
            and action.order_id
            != known_order_id
        ):
            raise ResolutionValidationError(
                "Planner proposed an action "
                "for an unknown order."
            )

        if (
            action.action_type
            != "refund"
            and action.amount
            is not None
        ):
            raise ResolutionValidationError(
                "Only refund actions may "
                "contain an amount."
            )

    payment = (
        context.payment
        or {}
    )

    payment_amount = (
        payment.get(
            "amount",
            payment.get(
                "payment_amount"
            ),
        )
    )

    if payment_amount is not None:

        try:
            payment_amount = float(
                payment_amount
            )

        except (
            TypeError,
            ValueError,
        ):
            payment_amount = None

    for action in plan.actions:

        if (
            action.action_type
            == "refund"
            and action.amount
            is not None
            and payment_amount
            is not None
            and action.amount
            > payment_amount
        ):
            raise ResolutionValidationError(
                "Proposed refund exceeds "
                "recorded payment amount."
            )

    return plan

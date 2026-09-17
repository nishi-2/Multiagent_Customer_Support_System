from __future__ import annotations

from datetime import (
    datetime,
    timezone,
)

from supportcommander.graph.models import (
    ActionPolicyDecision,
    ProposedAction,
)
from supportcommander.policy.constants import (
    CANCELLATION_AUTO_APPROVAL_LIMIT,
    REFUND_AUTO_APPROVAL_LIMIT,
    REFUND_WINDOW_DAYS,
    REPLACEMENT_AUTO_APPROVAL_LIMIT,
    REPLACEMENT_WINDOW_DAYS,
)

DECISION_PRIORITY = {
    "allow": 1,
    "require_approval": 2,
    "reject": 3,
    "escalate": 4,
}


def most_restrictive_decision(
    decisions: list[str],
) -> str:

    if not decisions:
        return "allow"

    return max(
        decisions,
        key=lambda decision: (
            DECISION_PRIORITY[
                decision
            ]
        ),
    )


def parse_datetime(
    value,
) -> datetime | None:

    if value is None:
        return None

    if isinstance(
        value,
        datetime,
    ):
        dt = value

    elif isinstance(
        value,
        str,
    ):
        try:
            dt = datetime.fromisoformat(
                value.replace(
                    "Z",
                    "+00:00",
                )
            )
        except ValueError:
            return None

    else:
        return None

    if dt.tzinfo is None:
        dt = dt.replace(
            tzinfo=timezone.utc
        )

    return dt


def age_in_days(
    value,
) -> int | None:

    dt = parse_datetime(
        value
    )

    if dt is None:
        return None

    now = datetime.now(
        timezone.utc
    )

    delta = now - dt

    return delta.days


def get_account_status(
    customer: dict,
) -> str:

    return str(
        customer.get(
            "account_status",
            "",
        )
    ).lower()


def is_restricted_account(
    customer: dict,
) -> bool:

    return (
        get_account_status(
            customer
        )
        == "restricted"
    )


def get_payment_amount(
    payment: dict,
) -> float | None:

    value = payment.get(
        "amount",
        payment.get(
            "payment_amount"
        ),
    )

    if value is None:
        return None

    try:
        return float(value)

    except (
        TypeError,
        ValueError,
    ):
        return None


def get_order_amount(
    order: dict,
) -> float | None:

    value = order.get(
        "order_amount",
        order.get(
            "amount"
        ),
    )

    if value is None:
        return None

    try:
        return float(value)

    except (
        TypeError,
        ValueError,
    ):
        return None


def evaluate_refund_action(
    *,
    action_index: int,
    action: ProposedAction,
    customer: dict,
    order: dict,
    payment: dict,
    refund_history: list[dict],
    risk_level: str,
) -> ActionPolicyDecision:

    if is_restricted_account(
        customer
    ):
        return ActionPolicyDecision(
            action_index=action_index,
            action_type="refund",
            decision="escalate",
            reason=(
                "Restricted accounts cannot "
                "receive autonomous refunds."
            ),
            rule_ids=[
                "REFUND_RESTRICTED_ACCOUNT"
            ],
        )

    payment_status = str(
        payment.get(
            "payment_status",
            payment.get(
                "status",
                "",
            ),
        )
    ).lower()

    if payment_status not in {
        "paid",
        "partially_refunded",
    }:
        return ActionPolicyDecision(
            action_index=action_index,
            action_type="refund",
            decision="reject",
            reason=(
                "Refund requires a valid "
                "paid transaction."
            ),
            rule_ids=[
                "REFUND_PAYMENT_NOT_ELIGIBLE"
            ],
        )

    payment_amount = (
        get_payment_amount(
            payment
        )
    )

    if action.amount is None:
        return ActionPolicyDecision(
            action_index=action_index,
            action_type="refund",
            decision="escalate",
            reason=(
                "Refund amount is missing."
            ),
            rule_ids=[
                "REFUND_AMOUNT_MISSING"
            ],
        )

    if (
        payment_amount is not None
        and action.amount
        > payment_amount
    ):
        return ActionPolicyDecision(
            action_index=action_index,
            action_type="refund",
            decision="reject",
            reason=(
                "Refund amount exceeds "
                "the recorded payment."
            ),
            rule_ids=[
                "REFUND_EXCEEDS_PAYMENT"
            ],
        )

    completed_refunds = [
        refund
        for refund
        in refund_history
        if (
            str(
                refund.get(
                    "status",
                    "",
                )
            ).lower()
            in {
                "completed",
                "refunded",
            }
            and (
                not action.order_id
                or refund.get(
                    "order_id"
                )
                == action.order_id
            )
        )
    ]

    if completed_refunds:
        return ActionPolicyDecision(
            action_index=action_index,
            action_type="refund",
            decision="reject",
            reason=(
                "A completed refund already "
                "exists for this customer/order."
            ),
            rule_ids=[
                "REFUND_ALREADY_COMPLETED"
            ],
        )

    reference_date = (
        order.get(
            "delivered_at"
        )
        or order.get(
            "delivery_date"
        )
        or order.get(
            "order_date"
        )
        or order.get(
            "created_at"
        )
    )

    days_old = age_in_days(
        reference_date
    )

    if (
        days_old is not None
        and days_old
        > REFUND_WINDOW_DAYS
    ):
        return ActionPolicyDecision(
            action_index=action_index,
            action_type="refund",
            decision="require_approval",
            reason=(
                "Refund request is outside "
                f"the {REFUND_WINDOW_DAYS}-day "
                "standard window."
            ),
            rule_ids=[
                "REFUND_OUTSIDE_WINDOW"
            ],
        )

    if days_old is None:
        return ActionPolicyDecision(
            action_index=action_index,
            action_type="refund",
            decision="escalate",
            reason=(
                "Refund eligibility window "
                "cannot be verified."
            ),
            rule_ids=[
                "REFUND_DATE_UNVERIFIED"
            ],
        )

    if risk_level == "high":
        return ActionPolicyDecision(
            action_index=action_index,
            action_type="refund",
            decision="escalate",
            reason=(
                "High-risk refunds cannot "
                "be executed autonomously."
            ),
            rule_ids=[
                "REFUND_HIGH_RISK"
            ],
        )

    if risk_level == "medium":
        return ActionPolicyDecision(
            action_index=action_index,
            action_type="refund",
            decision="require_approval",
            reason=(
                "Medium-risk refund requires "
                "human approval."
            ),
            rule_ids=[
                "REFUND_MEDIUM_RISK"
            ],
        )

    if (
        action.amount
        > REFUND_AUTO_APPROVAL_LIMIT
    ):
        return ActionPolicyDecision(
            action_index=action_index,
            action_type="refund",
            decision="require_approval",
            reason=(
                "Refund amount exceeds "
                "the autonomous refund limit "
                f"of {REFUND_AUTO_APPROVAL_LIMIT:.2f}."
            ),
            rule_ids=[
                "REFUND_ABOVE_AUTO_LIMIT"
            ],
        )

    return ActionPolicyDecision(
        action_index=action_index,
        action_type="refund",
        decision="allow",
        reason=(
            "Refund satisfies autonomous "
            "refund requirements."
        ),
        rule_ids=[
            "REFUND_AUTONOMOUS_ALLOWED"
        ],
    )


def evaluate_replacement_action(
    *,
    action_index: int,
    action: ProposedAction,
    customer: dict,
    order: dict,
    replacement_history: list[dict],
    risk_level: str,
) -> ActionPolicyDecision:

    if is_restricted_account(
        customer
    ):
        return ActionPolicyDecision(
            action_index=action_index,
            action_type="replacement",
            decision="escalate",
            reason=(
                "Restricted account requires "
                "manual replacement review."
            ),
            rule_ids=[
                "REPLACEMENT_RESTRICTED_ACCOUNT"
            ],
        )

    completed = [
        item
        for item
        in replacement_history
        if (
            str(
                item.get(
                    "status",
                    "",
                )
            ).lower()
            in {
                "completed",
                "shipped",
                "delivered",
            }
            and (
                not action.order_id
                or item.get(
                    "order_id"
                )
                == action.order_id
            )
        )
    ]

    if completed:
        return ActionPolicyDecision(
            action_index=action_index,
            action_type="replacement",
            decision="require_approval",
            reason=(
                "A prior replacement exists "
                "for this order."
            ),
            rule_ids=[
                "REPLACEMENT_PRIOR_RECORD"
            ],
        )

    reference_date = (
        order.get(
            "delivered_at"
        )
        or order.get(
            "delivery_date"
        )
        or order.get(
            "order_date"
        )
        or order.get(
            "created_at"
        )
    )

    days_old = age_in_days(
        reference_date
    )

    if days_old is None:
        return ActionPolicyDecision(
            action_index=action_index,
            action_type="replacement",
            decision="escalate",
            reason=(
                "Replacement eligibility "
                "window cannot be verified."
            ),
            rule_ids=[
                "REPLACEMENT_DATE_UNVERIFIED"
            ],
        )

    if (
        days_old
        > REPLACEMENT_WINDOW_DAYS
    ):
        return ActionPolicyDecision(
            action_index=action_index,
            action_type="replacement",
            decision="require_approval",
            reason=(
                "Replacement request is "
                "outside the standard "
                f"{REPLACEMENT_WINDOW_DAYS}-day "
                "window."
            ),
            rule_ids=[
                "REPLACEMENT_OUTSIDE_WINDOW"
            ],
        )

    if risk_level == "high":
        return ActionPolicyDecision(
            action_index=action_index,
            action_type="replacement",
            decision="escalate",
            reason=(
                "High-risk replacement requires "
                "manual review."
            ),
            rule_ids=[
                "REPLACEMENT_HIGH_RISK"
            ],
        )

    if risk_level == "medium":
        return ActionPolicyDecision(
            action_index=action_index,
            action_type="replacement",
            decision="require_approval",
            reason=(
                "Medium-risk replacement "
                "requires human approval."
            ),
            rule_ids=[
                "REPLACEMENT_MEDIUM_RISK"
            ],
        )

    order_amount = (
        get_order_amount(
            order
        )
    )

    if order_amount is None:
        return ActionPolicyDecision(
            action_index=action_index,
            action_type="replacement",
            decision="escalate",
            reason=(
                "Order value cannot be verified."
            ),
            rule_ids=[
                "REPLACEMENT_VALUE_UNVERIFIED"
            ],
        )

    if (
        order_amount
        > REPLACEMENT_AUTO_APPROVAL_LIMIT
    ):
        return ActionPolicyDecision(
            action_index=action_index,
            action_type="replacement",
            decision="require_approval",
            reason=(
                "Product value exceeds the "
                "autonomous replacement limit "
                f"of "
                f"{REPLACEMENT_AUTO_APPROVAL_LIMIT:.2f}."
            ),
            rule_ids=[
                "REPLACEMENT_ABOVE_AUTO_LIMIT"
            ],
        )

    return ActionPolicyDecision(
        action_index=action_index,
        action_type="replacement",
        decision="allow",
        reason=(
            "Replacement satisfies autonomous "
            "replacement requirements."
        ),
        rule_ids=[
            "REPLACEMENT_AUTONOMOUS_ALLOWED"
        ],
    )


def evaluate_cancellation_action(
    *,
    action_index: int,
    action: ProposedAction,
    customer: dict,
    order: dict,
    shipment: dict,
    risk_level: str,
) -> ActionPolicyDecision:

    if is_restricted_account(
        customer
    ):
        return ActionPolicyDecision(
            action_index=action_index,
            action_type="cancel_order",
            decision="escalate",
            reason=(
                "Restricted account requires "
                "manual cancellation review."
            ),
            rule_ids=[
                "CANCEL_RESTRICTED_ACCOUNT"
            ],
        )

    shipment_status = str(
        shipment.get(
            "shipment_status",
            shipment.get(
                "status",
                "",
            ),
        )
    ).lower()

    if shipment_status in {
        "shipped",
        "in_transit",
        "delivered",
    }:
        return ActionPolicyDecision(
            action_index=action_index,
            action_type="cancel_order",
            decision="reject",
            reason=(
                "Order can no longer be "
                "cancelled after shipment."
            ),
            rule_ids=[
                "CANCEL_ALREADY_SHIPPED"
            ],
        )

    order_status = str(
        order.get(
            "order_status",
            order.get(
                "status",
                "",
            ),
        )
    ).lower()

    if order_status == "cancelled":
        return ActionPolicyDecision(
            action_index=action_index,
            action_type="cancel_order",
            decision="reject",
            reason=(
                "Order is already cancelled."
            ),
            rule_ids=[
                "CANCEL_ALREADY_CANCELLED"
            ],
        )

    if risk_level == "high":
        return ActionPolicyDecision(
            action_index=action_index,
            action_type="cancel_order",
            decision="escalate",
            reason=(
                "High-risk cancellation "
                "requires manual review."
            ),
            rule_ids=[
                "CANCEL_HIGH_RISK"
            ],
        )

    if risk_level == "medium":
        return ActionPolicyDecision(
            action_index=action_index,
            action_type="cancel_order",
            decision="require_approval",
            reason=(
                "Medium-risk cancellation "
                "requires approval."
            ),
            rule_ids=[
                "CANCEL_MEDIUM_RISK"
            ],
        )

    order_amount = (
        get_order_amount(
            order
        )
    )

    if order_amount is None:
        return ActionPolicyDecision(
            action_index=action_index,
            action_type="cancel_order",
            decision="escalate",
            reason=(
                "Order value cannot be verified."
            ),
            rule_ids=[
                "CANCEL_VALUE_UNVERIFIED"
            ],
        )

    if (
        order_amount
        > CANCELLATION_AUTO_APPROVAL_LIMIT
    ):
        return ActionPolicyDecision(
            action_index=action_index,
            action_type="cancel_order",
            decision="require_approval",
            reason=(
                "Order value exceeds autonomous "
                "cancellation limit of "
                f"{CANCELLATION_AUTO_APPROVAL_LIMIT:.2f}."
            ),
            rule_ids=[
                "CANCEL_ABOVE_AUTO_LIMIT"
            ],
        )

    return ActionPolicyDecision(
        action_index=action_index,
        action_type="cancel_order",
        decision="allow",
        reason=(
            "Cancellation satisfies autonomous "
            "cancellation requirements."
        ),
        rule_ids=[
            "CANCEL_AUTONOMOUS_ALLOWED"
        ],
    )


def evaluate_non_transactional_action(
    *,
    action_index: int,
    action: ProposedAction,
) -> ActionPolicyDecision:

    if action.action_type == "escalate":
        return ActionPolicyDecision(
            action_index=action_index,
            action_type=action.action_type,
            decision="escalate",
            reason=action.reason,
            rule_ids=[
                "PLANNER_ESCALATION"
            ],
        )

    return ActionPolicyDecision(
        action_index=action_index,
        action_type=action.action_type,
        decision="allow",
        reason=(
            "Action is non-transactional "
            "and does not modify backend state."
        ),
        rule_ids=[
            "NON_TRANSACTIONAL_ALLOWED"
        ],
    )


def evaluate_action(
    *,
    action_index: int,
    action: ProposedAction,
    customer: dict,
    order: dict,
    payment: dict,
    shipment: dict,
    refund_history: list[dict],
    replacement_history: list[dict],
    risk_level: str,
) -> ActionPolicyDecision:

    if action.action_type == "refund":
        return evaluate_refund_action(
            action_index=action_index,
            action=action,
            customer=customer,
            order=order,
            payment=payment,
            refund_history=refund_history,
            risk_level=risk_level,
        )

    if action.action_type == "replacement":
        return evaluate_replacement_action(
            action_index=action_index,
            action=action,
            customer=customer,
            order=order,
            replacement_history=(
                replacement_history
            ),
            risk_level=risk_level,
        )

    if action.action_type == "cancel_order":
        return evaluate_cancellation_action(
            action_index=action_index,
            action=action,
            customer=customer,
            order=order,
            shipment=shipment,
            risk_level=risk_level,
        )

    return evaluate_non_transactional_action(
        action_index=action_index,
        action=action,
    )

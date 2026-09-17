from __future__ import annotations


def assess_context_risk(
    *,
    customer: dict | None,
    order: dict | None,
    payment: dict | None,
    refund_history: list[dict],
    replacement_history: list[dict],
) -> tuple[
    float,
    list[str],
]:

    score = 0.0
    signals: list[str] = []

    customer = customer or {}
    order = order or {}
    payment = payment or {}

    # Missing critical backend data
    missing_critical = []

    if not customer:
        missing_critical.append(
            "customer"
        )

    if not order:
        missing_critical.append(
            "order"
        )

    if not payment:
        missing_critical.append(
            "payment"
        )

    if missing_critical:
        score += 0.35

        signals.append(
            "critical_context_missing"
        )

    # Account restriction
    account_status = str(
        customer.get(
            "account_status",
            "",
        )
    ).lower()

    if account_status == "restricted":
        score += 0.50

        signals.append(
            "restricted_account"
        )

    # Existing generated risk marker
    source_risk = str(
        customer.get(
            "risk_level",
            "",
        )
    ).lower()

    if source_risk == "medium":
        score += 0.25

        signals.append(
            "customer_medium_risk"
        )

    elif source_risk == "high":
        score += 0.50

        signals.append(
            "customer_high_risk"
        )

    # Payment status
    payment_status = str(
        payment.get(
            "payment_status",
            payment.get(
                "status",
                "",
            ),
        )
    ).lower()

    if payment_status in {
        "failed",
        "disputed",
    }:
        score += 0.40

        signals.append(
            "payment_issue"
        )

    # High-value order
    order_amount = (
        order.get(
            "order_amount",
            order.get(
                "amount",
                0,
            ),
        )
        or 0
    )

    try:
        order_amount = float(
            order_amount
        )
    except (
        TypeError,
        ValueError,
    ):
        order_amount = 0.0

    if order_amount > 500:
        score += 0.15

        signals.append(
            "high_value_order"
        )

    # Refund frequency
    if len(
        refund_history
    ) >= 2:

        score += 0.20

        signals.append(
            "multiple_refund_history"
        )

    # Replacement frequency
    if len(
        replacement_history
    ) >= 2:

        score += 0.15

        signals.append(
            "multiple_replacement_history"
        )

    score = min(
        score,
        1.0,
    )

    return (
        score,
        signals,
    )


def risk_level_from_score(
    score: float,
) -> str:

    if score >= 0.70:
        return "high"

    if score >= 0.35:
        return "medium"

    return "low"

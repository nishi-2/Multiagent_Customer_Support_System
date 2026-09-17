from supportcommander.agents.risk_rules import (
    assess_context_risk,
    risk_level_from_score,
)


def test_low_risk_context():

    score, signals = (
        assess_context_risk(
            customer={
                "account_status": "active",
                "risk_level": "low",
            },
            order={
                "order_amount": 100,
            },
            payment={
                "status": "paid",
            },
            refund_history=[],
            replacement_history=[],
        )
    )

    assert score == 0.0
    assert signals == []

    assert (
        risk_level_from_score(
            score
        )
        == "low"
    )


def test_restricted_account_is_high_risk():

    score, signals = (
        assess_context_risk(
            customer={
                "account_status":
                    "restricted",

                "risk_level":
                    "high",
            },
            order={
                "order_amount": 100,
            },
            payment={
                "status": "paid",
            },
            refund_history=[],
            replacement_history=[],
        )
    )

    assert score >= 0.70

    assert (
        "restricted_account"
        in signals
    )

    assert (
        risk_level_from_score(
            score
        )
        == "high"
    )


def test_missing_context_is_medium_risk():

    score, signals = (
        assess_context_risk(
            customer=None,
            order=None,
            payment=None,
            refund_history=[],
            replacement_history=[],
        )
    )

    assert score >= 0.35

    assert (
        "critical_context_missing"
        in signals
    )

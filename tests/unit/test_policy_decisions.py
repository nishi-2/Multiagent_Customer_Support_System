from supportcommander.policy.gate_rules import (
    most_restrictive_decision,
)


def test_allow_only():

    assert (
        most_restrictive_decision(
            ["allow"]
        )
        == "allow"
    )


def test_approval_beats_allow():

    assert (
        most_restrictive_decision(
            [
                "allow",
                "require_approval",
            ]
        )
        == "require_approval"
    )


def test_escalate_beats_approval():

    assert (
        most_restrictive_decision(
            [
                "require_approval",
                "escalate",
            ]
        )
        == "escalate"
    )


def test_reject_is_most_restrictive():

    assert (
        most_restrictive_decision(
            [
                "allow",
                "escalate",
                "reject",
            ]
        )
        == "reject"
    )

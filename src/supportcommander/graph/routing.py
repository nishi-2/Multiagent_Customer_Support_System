from __future__ import annotations

from typing import Literal

from supportcommander.graph.state import (
    SupportGraphState,
)


def route_after_startup(
    state: SupportGraphState,
) -> str:
    """Route after the parallel startup phase (triage + context + risk)."""
    if state.get("escalated"):
        return "escalated"
    return "continue"



def route_after_policy_gate(
    state: SupportGraphState,
) -> Literal[
    "approval",
    "action_execution",
    "response_drafting",
]:

    result = state.get(
        "policy_gate_result"
    )

    if result is None:
        raise RuntimeError(
            "Policy gate result is missing."
        )

    if result.decision == "allow":
        return "action_execution"

    if result.decision in {
        "require_approval",
        "escalate",
    }:
        return "approval"

    return "response_drafting"

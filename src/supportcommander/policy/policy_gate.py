from __future__ import annotations

from supportcommander.graph.audit import (
    append_audit_event,
)
from supportcommander.graph.models import (
    PolicyGateResult,
    WorkflowStage,
)
from supportcommander.graph.state import (
    SupportGraphState,
)
from supportcommander.policy.gate_rules import (
    evaluate_action,
    most_restrictive_decision,
)


def run_policy_gate(
    state: SupportGraphState,
) -> SupportGraphState:

    append_audit_event(
        state,
        event_type="policy_gate_started",
        actor="policy_gate",
        message="Policy Gate evaluation started.",
        metadata={
            "ticket_id":
                state.get("ticket_id")
        },
    )

    plan = state.get(
        "resolution_plan"
    )

    context = state.get(
        "customer_context"
    )

    risk = state.get(
        "risk_assessment"
    )

    if plan is None:
        raise RuntimeError(
            "Resolution plan is missing."
        )

    if context is None:
        raise RuntimeError(
            "Customer context is missing."
        )

    if risk is None:
        raise RuntimeError(
            "Risk assessment is missing."
        )

    if (
        "low_planner_confidence"
        in plan.planner_flags
    ):
        result = PolicyGateResult(
            decision="escalate",
            reasons=[
                (
                    "Resolution Planner confidence "
                    "is below the configured "
                    "minimum."
                )
            ],
            requires_human_approval=True,
        )

        state[
            "policy_gate_result"
        ] = result

        state[
            "current_stage"
        ] = WorkflowStage.POLICY_GATE

        state[
            "next_stage"
        ] = WorkflowStage.APPROVAL

        append_audit_event(
            state,
            event_type="policy_gate_completed",
            actor="policy_gate",
            message="Policy Gate completed: escalated due to low planner confidence.",
            metadata={
                "decision":
                    result.decision
            },
        )

        return state

    if context.missing_data:

        critical = {
            "customer",
            "order",
            "payment",
        }

        if critical.intersection(
            context.missing_data
        ):
            result = PolicyGateResult(
                decision="escalate",
                reasons=[
                    (
                        "Critical backend context "
                        "is missing."
                    )
                ],
                requires_human_approval=True,
            )

            state[
                "policy_gate_result"
            ] = result

            state[
                "current_stage"
            ] = WorkflowStage.POLICY_GATE

            state[
                "next_stage"
            ] = WorkflowStage.APPROVAL

            append_audit_event(
                state,
                event_type="policy_gate_completed",
                actor="policy_gate",
                message="Policy Gate completed: escalated due to missing critical context.",
                metadata={
                    "decision":
                        result.decision,
                    "missing_data":
                        context.missing_data,
                },
            )

            return state

    # Check human-in-the-loop trigger signals detected at triage time.
    # Only escalate for genuinely sensitive triggers — "frustration" is normal
    # for support tickets and should be handled autonomously where policies allow.
    SERIOUS_TRIGGERS = {"security_concern", "personal_data_change"}
    triage = state.get("triage")
    human_triggers: list[str] = []
    if triage and hasattr(triage, "human_triggers"):
        human_triggers = triage.human_triggers or []

    serious = [t for t in human_triggers if t in SERIOUS_TRIGGERS]
    if serious:
        trigger_str = ", ".join(serious)
        result = PolicyGateResult(
            decision="require_approval",
            reasons=[f"Human review required: {trigger_str}"],
            requires_human_approval=True,
        )

        state["policy_gate_result"] = result
        state["current_stage"] = WorkflowStage.POLICY_GATE
        state["next_stage"] = WorkflowStage.APPROVAL

        append_audit_event(
            state,
            event_type="policy_gate_completed",
            actor="policy_gate",
            message=f"Policy Gate: serious human triggers detected — {trigger_str}.",
            metadata={
                "decision": result.decision,
                "human_triggers": serious,
            },
        )

        return state

    customer = (
        context.customer
        or {}
    )

    order = (
        context.order
        or {}
    )

    payment = (
        context.payment
        or {}
    )

    shipment = (
        context.shipment
        or {}
    )

    decisions = []

    for index, action in enumerate(
        plan.actions
    ):
        decision = evaluate_action(
            action_index=index,
            action=action,
            customer=customer,
            order=order,
            payment=payment,
            shipment=shipment,
            refund_history=(
                context.refund_history
            ),
            replacement_history=(
                context.replacement_history
            ),
            risk_level=(
                risk.risk_level
            ),
        )

        decisions.append(
            decision
        )

    overall_decision = (
        most_restrictive_decision(
            [
                decision.decision
                for decision
                in decisions
            ]
        )
    )

    reasons = [
        decision.reason
        for decision
        in decisions
    ]

    result = PolicyGateResult(
        decision=overall_decision,
        action_decisions=decisions,
        reasons=reasons,
        requires_human_approval=(
            overall_decision
            in {
                "require_approval",
                "escalate",
            }
        ),
    )

    state[
        "policy_gate_result"
    ] = result

    state[
        "current_stage"
    ] = WorkflowStage.POLICY_GATE

    if overall_decision == "allow":

        state[
            "next_stage"
        ] = (
            WorkflowStage.ACTION_EXECUTION
        )

    elif overall_decision in {
        "require_approval",
        "escalate",
    }:

        state[
            "next_stage"
        ] = (
            WorkflowStage.APPROVAL
        )

    elif overall_decision == "reject":

        state[
            "next_stage"
        ] = (
            WorkflowStage.RESPONSE_DRAFTING
        )

    append_audit_event(
        state,
        event_type="policy_gate_completed",
        actor="policy_gate",
        message=f"Policy Gate completed: {overall_decision}.",
        metadata={
            "decision":
                overall_decision,

            "requires_human_approval":
                result.requires_human_approval,

            "action_decisions": [
                {
                    "action_type":
                        item.action_type,

                    "decision":
                        item.decision,

                    "rule_ids":
                        item.rule_ids,
                }
                for item
                in decisions
            ],
        },
    )

    return state

from __future__ import annotations

from supportcommander.graph.models import (
    ApprovalState,
    AuditEvent,
    CustomerContext,
    PolicyGateResult,
    ResolutionPlan,
    RetrievedPolicy,
    RiskAssessment,
    ToolExecutionResult,
    TriageResult,
    WorkflowStage,
)


def hydrate_workflow_state(
    document: dict,
) -> dict:

    state = dict(
        document
    )

    state.pop(
        "_id",
        None,
    )

    if state.get("triage"):
        state["triage"] = (
            TriageResult.model_validate(
                state["triage"]
            )
        )

    if state.get(
        "customer_context"
    ):
        state[
            "customer_context"
        ] = (
            CustomerContext.model_validate(
                state[
                    "customer_context"
                ]
            )
        )

    if state.get(
        "risk_assessment"
    ):
        state[
            "risk_assessment"
        ] = (
            RiskAssessment.model_validate(
                state[
                    "risk_assessment"
                ]
            )
        )

    state[
        "retrieved_policies"
    ] = [
        RetrievedPolicy.model_validate(
            item
        )
        for item
        in state.get(
            "retrieved_policies",
            [],
        )
    ]

    if state.get(
        "resolution_plan"
    ):
        state[
            "resolution_plan"
        ] = (
            ResolutionPlan.model_validate(
                state[
                    "resolution_plan"
                ]
            )
        )

    if state.get(
        "policy_gate_result"
    ):
        state[
            "policy_gate_result"
        ] = (
            PolicyGateResult.model_validate(
                state[
                    "policy_gate_result"
                ]
            )
        )

    if state.get(
        "approval"
    ):
        state[
            "approval"
        ] = (
            ApprovalState.model_validate(
                state[
                    "approval"
                ]
            )
        )

    state["audit_events"] = [
        AuditEvent.model_validate(item)
        if isinstance(item, dict)
        else item
        for item in state.get("audit_events", [])
    ]

    if state.get(
        "tool_results"
    ):
        state[
            "tool_results"
        ] = [
            ToolExecutionResult.model_validate(
                item
            )
            for item
            in state["tool_results"]
        ]

    if state.get(
        "current_stage"
    ):
        state[
            "current_stage"
        ] = WorkflowStage(
            state[
                "current_stage"
            ]
        )

    if state.get(
        "next_stage"
    ):
        state[
            "next_stage"
        ] = WorkflowStage(
            state[
                "next_stage"
            ]
        )

    return state

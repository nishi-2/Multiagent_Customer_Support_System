from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from supportcommander.graph.models import (
    AuditEvent,
    ApprovalState,
    CustomerContext,
    FinalResponse,
    PolicyGateResult,
    ResolutionPlan,
    RetrievedPolicy,
    RiskAssessment,
    ToolExecutionResult,
    TriageResult,
    WorkflowStage,
)


class SupportGraphState(TypedDict, total=False):
    # Workflow identity
    workflow_id: str

    # Original support case
    ticket_id: int
    ticket: dict[str, Any]

    # Agent outputs
    triage: TriageResult
    customer_context: CustomerContext
    risk_assessment: RiskAssessment

    # RAG
    retrieved_policies: list[RetrievedPolicy]

    # Planning
    resolution_plan: ResolutionPlan

    # Policy Gate
    policy_gate_result: PolicyGateResult

    # Human-in-the-loop
    approval: ApprovalState

    # MCP / transactional actions
    tool_results: list[ToolExecutionResult]

    # Observability — accumulated across all nodes via operator.add
    audit_events: Annotated[list[AuditEvent], operator.add]

    # Final output
    final_response: FinalResponse

    # Routing / workflow metadata
    current_stage: WorkflowStage
    next_stage: WorkflowStage | None

    escalated: bool
    escalation_reason: str | None

    error: str | None


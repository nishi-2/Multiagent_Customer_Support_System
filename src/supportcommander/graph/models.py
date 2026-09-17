from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from enum import StrEnum


class TriageResult(BaseModel):
    intent: Literal[
        "refund_request",
        "technical_issue",
        "cancellation_request",
        "product_inquiry",
        "billing_inquiry",
        "unknown",
    ]
    urgency: Literal["low", "medium", "high", "critical"]
    confidence: float = Field(ge=0.0, le=1.0)
    summary: str
    needs_customer_context: bool = True
    needs_policy_lookup: bool = True
    needs_risk_review: bool = True
    # Human-in-the-loop trigger signals detected at triage time.
    # Possible values: "frustration", "security_concern", "personal_data_change", "high_value_transaction"
    human_triggers: list[str] = Field(default_factory=list)


class CustomerContext(BaseModel):
    customer: dict[str, Any] | None = None
    order: dict[str, Any] | None = None
    payment: dict[str, Any] | None = None
    shipment: dict[str, Any] | None = None

    refund_history: list[
        dict[str, Any]
    ] = Field(
        default_factory=list
    )

    replacement_history: list[
        dict[str, Any]
    ] = Field(
        default_factory=list
    )

    missing_data: list[str] = Field(
        default_factory=list
    )


class RiskAssessment(BaseModel):
    risk_level: str
    risk_score: float

    risk_signals: list[str] = Field(
        default_factory=list
    )

    requires_human_review: bool = False

    rationale: str = ""


class RetrievedPolicy(BaseModel):
    policy_id: str
    title: str
    content: str
    source: str
    relevance_score: float | None = Field(default=None, ge=0.0, le=1.0)
    source_type: Literal["policy_db", "company_doc"] = "policy_db"
    citation: str | None = None


ActionType = Literal[
    "refund",
    "replacement",
    "cancel_order",
    "troubleshoot",
    "provide_information",
    "escalate",
    "no_action",
]


class ProposedAction(BaseModel):
    action_type: ActionType

    reason: str

    order_id: str | None = None

    amount: float | None = Field(
        default=None,
        ge=0,
    )

    parameters: dict[str, Any] = Field(
        default_factory=dict
    )


class ResolutionPlan(BaseModel):
    summary: str

    actions: list[
        ProposedAction
    ] = Field(
        default_factory=list
    )

    policy_basis: list[str] = Field(
        default_factory=list
    )

    customer_response_strategy: str

    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )

    planner_flags: list[str] = Field(
        default_factory=list
    )


PolicyDecision = Literal[
    "allow",
    "require_approval",
    "reject",
    "escalate",
]


class ActionPolicyDecision(BaseModel):
    action_index: int

    action_type: str

    decision: PolicyDecision

    reason: str

    rule_ids: list[str] = Field(
        default_factory=list
    )


class PolicyGateResult(BaseModel):
    decision: PolicyDecision

    action_decisions: list[
        ActionPolicyDecision
    ] = Field(
        default_factory=list
    )

    reasons: list[str] = Field(
        default_factory=list
    )

    requires_human_approval: bool = False


ApprovalDecision = Literal[
    "pending",
    "approved",
    "rejected",
]


class ApprovalState(BaseModel):
    required: bool = False

    status: ApprovalDecision = "pending"

    requested_reason: str | None = None

    # Rich handoff message from agent to human reviewer
    agent_recommendation: str | None = None

    decided_by: str | None = None

    decision_reason: str | None = None

    # Phase 5: structured 3-way decision
    decision_type: Literal["approved", "modified", "rejected"] | None = None
    commitments: list[str] = Field(default_factory=list)
    next_step: str | None = None  # what specialist will do (for rejected)
    modified_actions: list[dict] = Field(default_factory=list)  # for modified


class ToolExecutionResult(BaseModel):
    tool_name: str

    success: bool

    action_type: str

    data: dict[str, Any] | None = None

    error: str | None = None

    verification_passed: bool = False

    audit_metadata: dict[str, Any] = Field(
        default_factory=dict
    )


class AuditEvent(BaseModel):
    timestamp: datetime
    event_type: str
    actor: str
    message: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class FinalResponse(BaseModel):
    message: str
    resolution_status: str
    action_summary: str | None = None
    requires_follow_up: bool = False
    internal_notes: str | None = None
    # Always-present handoff note from agent to human representative
    agent_handoff: str | None = None


class WorkflowStage(StrEnum):
    INITIALIZED = "initialized"
    TRIAGE = "triage"
    PARALLEL_ANALYSIS = "parallel_analysis"
    RESOLUTION_PLANNING = "resolution_planning"
    POLICY_GATE = "policy_gate"
    APPROVAL = "approval"
    ACTION_EXECUTION = "action_execution"
    VERIFICATION = "verification"
    RESPONSE_DRAFTING = "response_drafting"
    COMPLETED = "completed"
    ESCALATED = "escalated"
    FAILED = "failed"
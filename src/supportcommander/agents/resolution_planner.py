from __future__ import annotations

import json

from pydantic import ValidationError

from supportcommander.agents.resolution_rules import (
    ResolutionValidationError,
    validate_resolution_plan,
)
from supportcommander.graph.audit import append_audit_event
from supportcommander.graph.models import (
    ProposedAction,
    ResolutionPlan,
    WorkflowStage,
)
from supportcommander.graph.state import (
    SupportGraphState,
)
from supportcommander.policy.constants import (
    RESOLUTION_MIN_CONFIDENCE,
)
from supportcommander.services.llm_service import (
    LLMServiceError,
    generate_text,
)


class ResolutionPlannerError(Exception):
    """Resolution planning failed."""


RESOLUTION_PLANNER_INSTRUCTIONS = """
You are the Resolution Planner for SupportCommander.

Your job is to propose a customer-support resolution using ONLY the
information provided to you.

You receive:

- ticket information
- triage result
- verified customer/order/payment/shipment context
- deterministic risk assessment
- retrieved company policy excerpts

You may propose one or more actions.

Allowed action_type values:

- refund
- replacement
- cancel_order
- troubleshoot
- provide_information
- escalate
- no_action

Important rules:

1. Do not execute any action.
2. Do not claim that a refund, replacement, or cancellation has happened.
3. Do not invent customer, order, payment, shipment, or policy facts.
4. Use only policy IDs supplied in the input.
5. If important information is missing or contradictory, propose escalation ONLY
   if a transactional action (refund, replacement, cancel_order) is truly required
   and cannot be completed without the missing data. For informational queries,
   complaints, tracking questions, or general guidance, use provide_information
   or troubleshoot instead — the absence of backend account data does not prevent
   answering informational tickets.
6. If no customer/order/payment context is available but retrieved_policies
   contain relevant KB documents, propose provide_information using those policies.
   Do NOT escalate just because backend account data is absent.
7. Risk information must be considered.
8. Never treat your proposal as final authorization.
9. The downstream deterministic Policy Gate decides whether an action may
   proceed automatically, requires human approval, or must be rejected.
10. If proposing a refund amount, it must come from the available transaction
    information or explicit customer request. Do not invent an amount.
11. Return valid JSON only.

Return exactly this JSON structure:

{
  "summary": "short resolution summary",
  "actions": [
    {
      "action_type": "refund | replacement | cancel_order | troubleshoot | provide_information | escalate | no_action",
      "reason": "why this action is proposed",
      "order_id": "order id or null",
      "amount": 0.0,
      "parameters": {}
    }
  ],
  "policy_basis": [
    "policy IDs used"
  ],
  "customer_response_strategy": "how SupportCommander should explain the next step",
  "confidence": 0.0,
  "planner_flags": []
}

For non-monetary actions, amount should be null.
""".strip()


def build_resolution_input(
    state: SupportGraphState,
) -> str:

    ticket = state.get(
        "ticket"
    )

    triage = state.get(
        "triage"
    )

    context = state.get(
        "customer_context"
    )

    risk = state.get(
        "risk_assessment"
    )

    policies = state.get(
        "retrieved_policies",
        [],
    )

    if ticket is None:
        raise ResolutionPlannerError(
            "Ticket is missing."
        )

    if triage is None:
        raise ResolutionPlannerError(
            "Triage result is missing."
        )

    if context is None:
        raise ResolutionPlannerError(
            "Customer context is missing."
        )

    if risk is None:
        raise ResolutionPlannerError(
            "Risk assessment is missing."
        )

    if not policies:
        raise ResolutionPlannerError(
            "Retrieved policies are missing."
        )

    payload = {
        "ticket": ticket,

        "triage":
            triage.model_dump(),

        "customer_context":
            context.model_dump(),

        "risk_assessment":
            risk.model_dump(),

        "retrieved_policies": [
            policy.model_dump()
            for policy in policies
        ],
    }

    return json.dumps(
        payload,
        default=str,
        indent=2,
    )


async def run_resolution_planner(
    state: SupportGraphState,
) -> SupportGraphState:

    state[
        "current_stage"
    ] = (
        WorkflowStage.RESOLUTION_PLANNING
    )

    append_audit_event(
        state,
        event_type=(
            "resolution_planning_started"
        ),
        actor="resolution_planner",
        message="Resolution Planner started.",
        metadata={
            "ticket_id":
                state["ticket_id"]
        },
    )

    try:
        planner_input = (
            build_resolution_input(
                state
            )
        )

        result = await generate_text(
            instructions=(
                RESOLUTION_PLANNER_INSTRUCTIONS
            ),
            input_text=planner_input,
            _agent_name="resolution_planner",
        )

        raw_text = (
            result.text.strip()
        )

        payload = json.loads(
            raw_text
        )

        plan = (
            ResolutionPlan
            .model_validate(
                payload
            )
        )

        plan = (
            validate_resolution_plan(
                state,
                plan,
            )
        )

        if (
            plan.confidence
            < RESOLUTION_MIN_CONFIDENCE
        ):
            plan.planner_flags.append(
                "low_planner_confidence"
            )

            if not any(
                action.action_type
                == "escalate"
                for action
                in plan.actions
            ):
                plan.actions.append(
                    ProposedAction(
                        action_type="escalate",
                        reason=(
                            "Resolution Planner "
                            "confidence is below "
                            "the configured threshold."
                        ),
                    )
                )

        state[
            "resolution_plan"
        ] = plan

        state[
            "current_stage"
        ] = (
            WorkflowStage.RESOLUTION_PLANNING
        )

        state[
            "next_stage"
        ] = (
            WorkflowStage.POLICY_GATE
        )

        append_audit_event(
            state,
            event_type=(
                "resolution_planning_completed"
            ),
            actor="resolution_planner",
            message="Resolution Planner completed.",
            metadata={
                "actions": [
                    action.action_type
                    for action
                    in plan.actions
                ],

                "confidence":
                    plan.confidence,

                "policy_basis":
                    plan.policy_basis,

                "request_id":
                    result.request_id,
            },
        )

        return state

    except (
        json.JSONDecodeError,
        ValidationError,
        ResolutionValidationError,
    ) as exc:

        state[
            "current_stage"
        ] = WorkflowStage.FAILED

        state[
            "next_stage"
        ] = None

        state[
            "error"
        ] = (
            "Resolution planning "
            f"validation failed: {exc}"
        )

        append_audit_event(
            state,
            event_type=(
                "resolution_planning_failed"
            ),
            actor="resolution_planner",
            message="Resolution planning validation failed.",
            metadata={
                "error": str(exc)
            },
        )

        raise ResolutionPlannerError(
            "Resolution Planner returned "
            "an invalid plan."
        ) from exc

    except LLMServiceError as exc:

        state[
            "current_stage"
        ] = WorkflowStage.FAILED

        state[
            "next_stage"
        ] = None

        state[
            "error"
        ] = (
            "Resolution Planner LLM "
            "request failed."
        )

        append_audit_event(
            state,
            event_type=(
                "resolution_planning_failed"
            ),
            actor="resolution_planner",
            message="Resolution Planner LLM request failed.",
            metadata={
                "error": str(exc)
            },
        )

        raise ResolutionPlannerError(
            "Resolution Planner LLM "
            "request failed."
        ) from exc

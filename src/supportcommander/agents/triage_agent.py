from __future__ import annotations

import json
from pydantic import ValidationError

from supportcommander.graph.audit import append_audit_event
from supportcommander.graph.models import TriageResult, WorkflowStage
from supportcommander.graph.state import SupportGraphState
from supportcommander.services.llm_service import LLMServiceError, generate_text
from supportcommander.agents.triage_rules import apply_triage_rules
from supportcommander.policy.constants import TRIAGE_MIN_CONFIDENCE


TRIAGE_INSTRUCTIONS = """
You are the Triage Agent for SupportCommander.

Your only responsibility is to analyze an incoming customer-support ticket and classify it.

You must determine:

1. intent
2. urgency
3. confidence
4. concise issue summary
5. which downstream analyses are required
6. human-in-the-loop trigger signals (see below)

Allowed intent values:

- refund_request
- technical_issue
- cancellation_request
- product_inquiry
- billing_inquiry
- unknown

Allowed urgency values:

- low
- medium
- high
- critical

Urgency guidance:

low: Routine informational question with no immediate impact.

medium: Normal customer-support problem requiring assistance.

high: Meaningful customer impact such as inability to use a purchased product, financial concern, repeated failure, or time-sensitive cancellation/refund issue.

critical: Severe customer impact, major financial/security concern, safety-related issue, account compromise, or another situation requiring immediate escalation.

Confidence must be between 0 and 1.

Human-in-the-loop trigger detection:

Populate "human_triggers" with any of the following strings that apply. Leave the list empty if none match.

- "frustration": Customer uses emotional or distressed language (e.g. angry, disappointed, threatening to leave, "worst experience", "unacceptable", "disgusted", or indicates they have contacted support multiple times for the same issue).
- "security_concern": Customer mentions unauthorized access, account compromise, fraud, someone else using their account, or suspicious activity.
- "personal_data_change": Customer requests changes to account email, password, payment method, billing address, or other identity-linked data.
- "high_value_transaction": The ticket involves a financial amount that appears large (e.g. refund or charge over $200, bulk order, enterprise purchase).

Do not attempt to resolve the ticket.

Do not invent customer history, policies, orders,
payments, refunds, or account information.

Return ONLY valid JSON.

Required JSON structure:

{
  "intent": "...",
  "urgency": "...",
  "confidence": 0.0,
  "summary": "...",
  "needs_customer_context": true,
  "needs_policy_lookup": true,
  "needs_risk_review": true,
  "human_triggers": []
}
""".strip()


class TriageAgentError(Exception):
    """Triage Agent could not produce a valid result."""


def build_triage_input(state: SupportGraphState,) -> str:

    ticket = state["ticket"]
    ticket_text = ticket.get("ticket_text")

    if not ticket_text:
        ticket_text = f"Subject: {ticket.get('ticket_subject', '')}\n\nDescription: {ticket.get('ticket_description', '')}"

    return (
        f"Ticket ID: {state['ticket_id']}\n"
        f"Source Priority: "
        f"{ticket.get('ticket_priority', 'Unknown')}\n"
        f"Channel: "
        f"{ticket.get('ticket_channel', 'Unknown')}\n\n"
        f"{ticket_text}"
    )


async def run_triage_agent(state: SupportGraphState,) -> SupportGraphState:

    state["current_stage"] = WorkflowStage.TRIAGE

    append_audit_event(
        state,
        event_type="triage_started",
        actor="triage_agent",
        message=("Triage Agent started ticket analysis."),
    )

    try:
        result = await generate_text(instructions=TRIAGE_INSTRUCTIONS, input_text=build_triage_input(state), _agent_name="triage_agent")
        raw_text = result.text.strip()
        parsed = json.loads(raw_text)
        triage = TriageResult.model_validate(parsed)
        triage = apply_triage_rules(triage)
        
        state["triage"] = triage

        # Low-confidence escalation
        if triage.confidence < TRIAGE_MIN_CONFIDENCE:
            state["escalated"] = True
            state["escalation_reason"] = "Triage confidence below minimum threshold."
            state["current_stage"] = WorkflowStage.ESCALATED
            state["next_stage"] = None

            append_audit_event(
                state,
                event_type="triage_low_confidence",
                actor="triage_agent",
                message=f"Triage confidence was below {TRIAGE_MIN_CONFIDENCE}.",
                metadata={"confidence": triage.confidence,},
            )

            return state

        state["current_stage"] = WorkflowStage.TRIAGE
        state["next_stage"] = WorkflowStage.PARALLEL_ANALYSIS

        append_audit_event(
            state,
            event_type="triage_completed",
            actor="triage_agent",
            message="Ticket triage completed.",
            metadata={
                "intent": triage.intent,
                "urgency": triage.urgency,
                "confidence": triage.confidence,
                "openai_request_id": result.request_id,
            },
        )

        return state

    except (json.JSONDecodeError, ValidationError,) as exc:
        state["error"] = "Triage Agent produced an invalid structured result."
        state["current_stage"] = WorkflowStage.FAILED
        state["next_stage"] = None

        append_audit_event(
            state,
            event_type="triage_failed",
            actor="triage_agent",
            message=state["error"],
        )

        raise TriageAgentError(state["error"]) from exc

    except LLMServiceError as exc:
        state["error"] = ("Triage Agent model request failed.")
        state["current_stage"] = WorkflowStage.FAILED
        state["next_stage"] = None

        append_audit_event(
            state,
            event_type="triage_failed",
            actor="triage_agent",
            message=state["error"],
        )

        raise TriageAgentError(state["error"]) from exc
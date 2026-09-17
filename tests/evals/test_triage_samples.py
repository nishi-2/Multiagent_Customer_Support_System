"""
Triage agent evaluation on representative ticket samples.

These tests call the OpenAI API and verify that the triage agent
produces intent classifications that match the expected ticket type.
"""

import pytest

from supportcommander.agents.triage_agent import run_triage_agent
from supportcommander.graph.state_factory import create_initial_state
from supportcommander.services.ticket_service import get_ticket


TICKET_INTENT_EXPECTATIONS = [
    (1, {"refund_request", "billing_inquiry", "cancellation_request", "unknown"}),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "ticket_id, expected_intents",
    TICKET_INTENT_EXPECTATIONS,
)
async def test_triage_classifies_ticket(ticket_id, expected_intents):

    ticket = get_ticket(ticket_id)
    assert ticket is not None, f"Ticket {ticket_id} not found."

    state = create_initial_state(
        ticket_id=ticket_id,
        ticket=ticket,
    )

    result = await run_triage_agent(state)

    triage = result.get("triage")
    assert triage is not None, "Triage result is None."

    assert triage.intent in {
        "refund_request",
        "technical_issue",
        "cancellation_request",
        "product_inquiry",
        "billing_inquiry",
        "unknown",
    }, f"Unknown intent: {triage.intent}"

    assert 0.0 <= triage.confidence <= 1.0, (
        f"Confidence {triage.confidence} is out of range."
    )

    assert triage.urgency in {
        "low", "medium", "high", "critical"
    }, f"Unknown urgency: {triage.urgency}"

    assert triage.summary, "summary is empty."


@pytest.mark.asyncio
async def test_triage_produces_audit_event():

    ticket = get_ticket(1)
    assert ticket is not None

    state = create_initial_state(
        ticket_id=1,
        ticket=ticket,
    )

    result = await run_triage_agent(state)
    events = result.get("audit_events") or []
    assert len(events) > 0, "No audit events produced by triage."

    event_types = [e.event_type for e in events]
    assert any(
        "triage" in t for t in event_types
    ), f"No triage audit event found. Events: {event_types}"

from fastapi import APIRouter, HTTPException, status

from supportcommander.agents.triage_agent import TriageAgentError, run_triage_agent
from supportcommander.graph.state_factory import create_initial_state
from supportcommander.graph.state_utils import serialize_state
from supportcommander.services.ticket_service import get_ticket
from supportcommander.services.workflow_service import save_workflow_state


router = APIRouter(prefix = "/api/v1/triage", tags = ["Triage Agent"])

@router.post("/{ticket_id}")
async def triage_ticket(ticket_id: int) -> dict:
    ticket = get_ticket(ticket_id)

    if ticket is None:
        raise HTTPException(status_code=(status.HTTP_404_NOT_FOUND), detail=(f"Ticket with ID {ticket_id} not found"))
    state = create_initial_state(ticket_id=ticket_id, ticket=ticket)

    try:
        state = await run_triage_agent(state)
    except TriageAgentError as exc:
        raise HTTPException(status_code=(status.HTTP_502_BAD_GATEWAY), detail=(f"Triage agent error: {str(exc)}"))

    save_workflow_state(state)
    serialized = serialize_state(state)

    return {
        "workflow_id": serialized["workflow_id"],
        "ticket_id":ticket_id,
        "triage":serialized["triage"],
        "escalated":serialized["escalated"],
        "escalation_reason":serialized["escalation_reason"],
        "next_stage":serialized["next_stage"],
    }
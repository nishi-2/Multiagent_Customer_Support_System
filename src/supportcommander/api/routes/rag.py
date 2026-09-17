from fastapi import APIRouter, HTTPException, Query, status
from supportcommander.agents.triage_agent import run_triage_agent
from supportcommander.graph.state_factory import create_initial_state
from supportcommander.rag.retriever import INTENT_POLICY_CATEGORIES, retrieve_for_intent
from supportcommander.services.ticket_service import get_ticket

from supportcommander.db.mongo import get_database


router = APIRouter(prefix="/api/v1/rag", tags=["RAG"])


@router.get("/index")
def rag_index_info() -> dict:

    db = get_database()

    count = db.policy_chunks.count_documents({})
    policies = db.policy_chunks.distinct("policy_id")
    categories = db.policy_chunks.distinct("category")

    return {
        "collection": "policy_chunks",
        "chunks": count,
        "policies": len(policies),
        "policy_ids": sorted(policies),
        "categories": sorted(categories),
    }


@router.get("/tickets/{ticket_id}/policies")
async def retrieve_ticket_policies(ticket_id: int, top_k: int = Query(default=3, ge=1, le=10)) -> dict:

    ticket = get_ticket(ticket_id)

    if ticket is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket {ticket_id} was not found.",
        )

    state = create_initial_state(ticket_id=ticket_id, ticket=ticket)
    state = await run_triage_agent(state)

    triage = state.get("triage")

    if triage is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Triage result was not available.",
        )

    results = await retrieve_for_intent(ticket["ticket_text"], intent=triage.intent, top_k=top_k)

    return {
        "ticket_id": ticket_id,
        "triage_intent": triage.intent,
        "searched_categories": INTENT_POLICY_CATEGORIES.get(triage.intent, [],),
        "items": [result.model_dump() for result in results],
        "total": len(results),
    }
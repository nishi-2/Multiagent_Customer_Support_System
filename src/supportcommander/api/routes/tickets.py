from fastapi import APIRouter, HTTPException, status, Query

from supportcommander.services.ticket_service import get_ticket, count_tickets, get_ticket_context, list_tickets


router = APIRouter(prefix="/api/v1/tickets", tags=["Tickets"])

@router.get("")
def read_tickets(
    limit: int = Query(default=20, ge=1, le=100,),
    skip: int = Query(default=0, ge=0,),
    ticket_status: str | None = None,
    ticket_type: str | None = None,
    ticket_priority: str | None = None,) -> dict:

    tickets = list_tickets(
        limit=limit,
        skip=skip,
        ticket_status=ticket_status,
        ticket_type=ticket_type,
        ticket_priority=ticket_priority,
    )

    total = count_tickets(
        ticket_status=ticket_status,
        ticket_type=ticket_type,
        ticket_priority=ticket_priority,
    )

    return {
        "items": tickets,
        "pagination": {
            "total": total,
            "limit": limit,
            "skip": skip,
            "returned": len(tickets),
        },
    }



@router.get("/{ticket_id}")
def read_ticket(ticket_id: int,) -> dict:

    ticket = get_ticket(ticket_id)

    if ticket is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket {ticket_id} - not found.",
        )

    return ticket


@router.get("/{ticket_id}/context")
def read_ticket_context(ticket_id: int,) -> dict:

    context = get_ticket_context(ticket_id)

    if context is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket {ticket_id} - context not found.",
        )

    return context
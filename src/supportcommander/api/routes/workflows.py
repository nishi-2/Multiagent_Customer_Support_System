from fastapi import (
    APIRouter,
    HTTPException,
    status,
)

from supportcommander.db.mongo import get_database
from supportcommander.graph.coordinator import (
    coordinator_graph,
)
from supportcommander.graph.state_factory import (
    create_initial_state,
)
from supportcommander.graph.state_utils import (
    serialize_state,
)
from supportcommander.services.ticket_service import (
    get_ticket,
)
from supportcommander.services.dataset_service import (
    get_dataset,
    get_user_ticket,
)
from supportcommander.services.workflow_service import (
    get_workflow_state,
    save_workflow_state,
)
from supportcommander.services import cost_tracker, cost_logger


router = APIRouter(
    prefix="/api/v1/workflows",
    tags=["Workflows"],
)


@router.post(
    "/tickets/{ticket_id}"
)
async def run_ticket_workflow(
    ticket_id: int,
) -> dict:

    ticket = get_ticket(ticket_id)

    if ticket is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket {ticket_id} was not found.",
        )

    initial_state = create_initial_state(
        ticket_id=ticket_id,
        ticket=ticket,
    )

    _acc = cost_tracker.start(
        workflow_id=initial_state["workflow_id"],
        ticket_id=ticket_id,
        user=ticket.get("customer_id") or f"ticket_{ticket_id}",
    )

    try:
        result = await coordinator_graph.ainvoke(initial_state)
    except Exception as exc:
        initial_state["error"] = str(exc)
        save_workflow_state(initial_state)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Workflow failed: {exc}",
        ) from exc
    finally:
        cost_logger.save(cost_tracker.finish(_acc))

    save_workflow_state(result)

    return serialize_state(result)


@router.get(
    "/{workflow_id}"
)
async def get_workflow(
    workflow_id: str,
) -> dict:

    document = get_workflow_state(workflow_id)

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow {workflow_id} was not found.",
        )

    return document


@router.get(
    "/tickets/{ticket_id}/history"
)
async def get_ticket_workflow_history(
    ticket_id: int,
) -> list:

    db = get_database()

    documents = list(
        db.workflows.find(
            {"ticket_id": ticket_id},
            {"_id": 0},
        ).sort("updated_at", -1)
    )

    return documents


@router.post(
    "/datasets/{dataset_id}/tickets/{row_id}",
    summary="Run the support workflow on a user-uploaded ticket",
)
async def run_dataset_ticket_workflow(
    dataset_id: str,
    row_id: int,
) -> dict:

    dataset = get_dataset(dataset_id)
    if dataset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset '{dataset_id}' not found.",
        )
    if dataset.get("status") != "ready":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Dataset '{dataset_id}' is not ready. "
                f"Current status: '{dataset.get('status')}'."
            ),
        )

    user_ticket = get_user_ticket(dataset_id, row_id)
    if user_ticket is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Row {row_id} not found in dataset '{dataset_id}'. "
                f"Valid rows are 0 to {dataset.get('ingested_count', 0) - 1}."
            ),
        )

    customer_identifier = user_ticket.get("customer_identifier") or ""
    # Derive a display name from the email local-part: "aarav.sharma@…" → "Aarav Sharma"
    _derived_name: str | None = None
    if customer_identifier and "@" in customer_identifier:
        local = customer_identifier.split("@")[0]
        _derived_name = " ".join(
            part.capitalize() for part in local.replace("_", ".").split(".") if part
        ) or None

    ticket = {
        "ticket_text":          user_ticket.get("ticket_text", ""),
        "ticket_subject":       user_ticket.get("ticket_subject") or "",
        "ticket_priority":      user_ticket.get("urgency") or "medium",
        "ticket_channel":       "uploaded",
        "customer_id":          None,
        "order_id":             None,
        "customer_identifier":  customer_identifier or None,
        "customer_email":       customer_identifier or None,
        "customer_name":        _derived_name,
        "intent_hint":          user_ticket.get("intent_hint"),
        "ticket_date":          user_ticket.get("ticket_date"),
        "original_ticket_id":   user_ticket.get("original_ticket_id"),
        "dataset_id":           dataset_id,
        "row_id":               row_id,
    }

    initial_state = create_initial_state(
        ticket_id=row_id,
        ticket=ticket,
    )

    _acc = cost_tracker.start(
        workflow_id=initial_state["workflow_id"],
        ticket_id=row_id,
        user=ticket.get("customer_identifier") or dataset_id,
    )

    try:
        result = await coordinator_graph.ainvoke(initial_state)
    except Exception as exc:
        initial_state["error"] = str(exc)
        save_workflow_state(initial_state)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Workflow failed: {exc}",
        ) from exc
    finally:
        cost_logger.save(cost_tracker.finish(_acc))

    save_workflow_state(result)

    return serialize_state(result)

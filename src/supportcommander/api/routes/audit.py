from __future__ import annotations

from fastapi import (
    APIRouter,
    HTTPException,
    status,
)

from supportcommander.services.workflow_service import (
    get_workflow_state,
)


router = APIRouter(
    prefix="/api/v1/audit",
    tags=["Audit"],
)


@router.get(
    "/workflows/{workflow_id}"
)
async def get_workflow_audit(
    workflow_id: str,
) -> list:

    document = get_workflow_state(
        workflow_id
    )

    if document is None:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=(
                f"Workflow {workflow_id} "
                "was not found."
            ),
        )

    return document.get(
        "audit_events",
        [],
    )

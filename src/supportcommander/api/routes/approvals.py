from __future__ import annotations

import asyncio
from typing import Literal

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from pydantic import BaseModel

from supportcommander.api.dependencies import require_api_key

from supportcommander.graph.state_utils import (
    serialize_state,
)
from supportcommander.services.approval_service import (
    ApprovalError,
    record_approval_decision,
    record_structured_decision,
)
from supportcommander.services.resume_service import (
    resume_workflow,
)


router = APIRouter(
    prefix="/api/v1/approvals",
    tags=["Approvals"],
    dependencies=[Depends(require_api_key)],
)


class ApprovalRequest(BaseModel):
    """Legacy binary approve/reject — maps to structured decision."""
    approved: bool
    decided_by: str
    reason: str


class StructuredApprovalRequest(BaseModel):
    decision: Literal["approved", "modified", "rejected"]
    decided_by: str
    reason: str
    commitments: list[str] = []
    next_step: str | None = None
    modified_actions: list[dict] = []


@router.post(
    "/{workflow_id}"
)
async def decide_approval(
    workflow_id: str,
    payload: StructuredApprovalRequest,
) -> dict:

    try:
        return await asyncio.to_thread(
            record_structured_decision,
            workflow_id=workflow_id,
            decision=payload.decision,
            decided_by=payload.decided_by,
            reason=payload.reason,
            commitments=payload.commitments,
            next_step=payload.next_step,
            modified_actions=payload.modified_actions,
        )

    except ApprovalError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post(
    "/{workflow_id}/resume"
)
async def resume_after_approval(
    workflow_id: str,
) -> dict:

    try:
        state = await resume_workflow(
            workflow_id
        )

        return serialize_state(
            state
        )

    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Resume failed: {exc}",
        ) from exc

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, status

from supportcommander.services.cost_logger import COST_LOGS_DIR

router = APIRouter(prefix="/api/v1/cost-logs", tags=["Cost Logs"])


@router.get("")
def list_cost_logs() -> list:
    if not COST_LOGS_DIR.exists():
        return []
    files = sorted(COST_LOGS_DIR.glob("*.json"), reverse=True)
    result = []
    for f in files[:100]:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            result.append({
                "filename": f.name,
                "workflow_id": data.get("workflow_id"),
                "ticket_id": data.get("ticket_id"),
                "user": data.get("user"),
                "started_at": data.get("started_at"),
                "completed_at": data.get("completed_at"),
                "total_wall_ms": data.get("total_wall_ms"),
                "total_cost_usd": data.get("summary", {}).get("total_cost_usd"),
                "total_tokens": data.get("summary", {}).get("total_tokens"),
                "llm_calls_count": data.get("llm_calls_count"),
                "models_used": data.get("models_used", []),
            })
        except Exception:
            pass
    return result


@router.get("/by-workflow/{workflow_id}")
def get_cost_log_by_workflow(workflow_id: str) -> dict:
    if not COST_LOGS_DIR.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No cost logs found.")
    for f in sorted(COST_LOGS_DIR.glob("*.json"), reverse=True):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if data.get("workflow_id") == workflow_id:
                data["filename"] = f.name
                return data
        except Exception:
            pass
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No cost log for this workflow.")


@router.get("/{filename}")
def get_cost_log(filename: str) -> dict:
    if not filename.endswith(".json") or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid filename.")
    path = COST_LOGS_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

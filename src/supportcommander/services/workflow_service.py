from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from supportcommander.db.mongo import get_database
from supportcommander.graph.state_utils import serialize_state


def save_workflow_state(state: dict) -> None:
    db = get_database()
    serialized = serialize_state(state)
    serialized["updated_at"] = datetime.now(timezone.utc)

    db.workflows.update_one(
        {"workflow_id": serialized["workflow_id"]},
        {"$set": serialized},
        upsert=True,
    )


def get_workflow_state(workflow_id: str,) -> dict[str, Any] | None:
    db = get_database()

    return db.workflows.find_one(
        {
            "workflow_id": workflow_id
        },
        {
            "_id": 0,
        },
    )
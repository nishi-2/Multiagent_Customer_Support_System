from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from pymongo import UpdateOne

from supportcommander.db.mongo import get_database
from supportcommander.services.dataset_service import read_cleaned_rows


@dataclass
class IngestResult:
    inserted: int
    updated: int
    total: int


def ingest_dataset(dataset_id: str) -> IngestResult:
    """
    Read cleaned rows from GridFS, normalise each to a UserTicket document,
    and bulk-upsert into the user_tickets collection.

    Upsert key: (dataset_id, row_id) — safe to call multiple times.
    """
    rows = read_cleaned_rows(dataset_id)
    if not rows:
        return IngestResult(inserted=0, updated=0, total=0)

    db = get_database()
    now = datetime.now(timezone.utc)

    ops: list[UpdateOne] = []
    for idx, row in enumerate(rows):
        doc = {
            "dataset_id": dataset_id,
            "row_id": idx,
            "ticket_text": row.get("ticket_text", ""),
            "ticket_subject": row.get("ticket_subject") or None,
            "customer_identifier": row.get("customer_identifier") or None,
            "ticket_date": row.get("ticket_date") or None,
            "intent_hint": row.get("intent_hint") or None,
            "urgency": row.get("urgency") or None,
            "ticket_status": row.get("ticket_status") or None,
            "original_ticket_id": row.get("ticket_id") or None,
            "ingested_at": now,
        }
        ops.append(
            UpdateOne(
                {"dataset_id": dataset_id, "row_id": idx},
                {"$set": doc},
                upsert=True,
            )
        )

    result = db.user_tickets.bulk_write(ops, ordered=False)
    return IngestResult(
        inserted=result.upserted_count,
        updated=result.modified_count,
        total=len(rows),
    )

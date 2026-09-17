from __future__ import annotations

import hashlib
import io
import re
from datetime import datetime, timezone
from typing import Any

import gridfs

from supportcommander.db.mongo import get_database

MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB
_USER_ID_SAFE = re.compile(r"[^a-zA-Z0-9_\-]")


class DatasetError(Exception):
    """Dataset operation failed."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_user_id(user_id: str) -> str:
    """Strip unsafe characters, truncate to 32 chars."""
    return _USER_ID_SAFE.sub("", user_id)[:32]


def _make_dataset_id(user_id: str, file_hash: str) -> str:
    return f"{_safe_user_id(user_id)}_{file_hash[:12]}"


# ── Read helpers ──────────────────────────────────────────────────────────────

def get_user_ticket(dataset_id: str, row_id: int) -> dict[str, Any] | None:
    db = get_database()
    return db.user_tickets.find_one(
        {"dataset_id": dataset_id, "row_id": row_id},
        {"_id": 0},
    )


def find_by_hash(file_hash: str) -> dict[str, Any] | None:
    db = get_database()
    return db.datasets.find_one({"file_hash": file_hash}, {"_id": 0})


def get_dataset(dataset_id: str) -> dict[str, Any] | None:
    db = get_database()
    return db.datasets.find_one({"dataset_id": dataset_id}, {"_id": 0})


def list_datasets(user_id: str) -> list[dict[str, Any]]:
    db = get_database()
    return list(
        db.datasets.find(
            {"user_id": user_id},
            {"_id": 0},
        ).sort("created_at", -1)
    )


def update_dataset_status(dataset_id: str, status: str) -> None:
    db = get_database()
    db.datasets.update_one(
        {"dataset_id": dataset_id},
        {
            "$set": {
                "status": status,
                "updated_at": datetime.now(timezone.utc),
            }
        },
    )


# ── Write ─────────────────────────────────────────────────────────────────────

def store_dataset_file(
    *,
    user_id: str,
    file_name: str,
    file_bytes: bytes,
) -> dict[str, Any]:
    """
    Fingerprint the file, check for duplicates, store raw bytes in GridFS,
    and create a dataset document.

    Returns the dataset document with a `duplicate` flag.
    Raises DatasetError on validation failure.
    """
    if not file_bytes:
        raise DatasetError("Uploaded file is empty.")

    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise DatasetError(
            f"File exceeds the {MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB limit."
        )

    file_hash = _sha256(file_bytes)

    # Deduplication: same bytes already ingested — return existing record instantly
    existing = find_by_hash(file_hash)
    if existing is not None:
        return {**existing, "duplicate": True}

    db = get_database()
    fs = gridfs.GridFS(db)

    gridfs_file_id = fs.put(
        io.BytesIO(file_bytes),
        filename=file_name,
        content_type="text/csv",
        metadata={"user_id": user_id},
    )

    dataset_id = _make_dataset_id(user_id, file_hash)
    now = datetime.now(timezone.utc)

    document: dict[str, Any] = {
        "dataset_id": dataset_id,
        "user_id": user_id,
        "file_name": file_name,
        "file_hash": file_hash,
        "file_size_bytes": len(file_bytes),
        "gridfs_file_id": str(gridfs_file_id),
        "status": "uploaded",
        # These fields are populated by later pipeline phases
        "row_count_raw": None,
        "valid_rows": None,
        "dropped_rows": None,
        "column_mapping": None,
        "cleaning_flags": None,
        "rejection_reason": None,
        "created_at": now,
        "updated_at": now,
    }

    db.datasets.insert_one(document)
    document.pop("_id", None)

    return {**document, "duplicate": False}


def save_analysis_result(
    dataset_id: str,
    *,
    is_accepted: bool,
    rejection_reason: str | None,
    domain_confidence: str,
    column_mapping: dict[str, Any],
    unmapped_columns: list[str],
    cleaning_needed: bool,
    cleaning_flags: list[str],
) -> None:
    db = get_database()
    db.datasets.update_one(
        {"dataset_id": dataset_id},
        {
            "$set": {
                "status": "analysed" if is_accepted else "rejected",
                "rejection_reason": rejection_reason,
                "domain_confidence": domain_confidence,
                "column_mapping": column_mapping,
                "unmapped_columns": unmapped_columns,
                "cleaning_needed": cleaning_needed,
                "cleaning_flags": cleaning_flags,
                "updated_at": datetime.now(timezone.utc),
            }
        },
    )


def save_clean_result(
    dataset_id: str,
    *,
    cleaned_rows: list[dict],
    row_count_raw: int,
    valid_rows: int,
    dropped_rows: int,
    cleaning_applied: list[str],
) -> None:
    import json as _json

    db = get_database()
    fs = gridfs.GridFS(db)

    json_bytes = _json.dumps(cleaned_rows, ensure_ascii=False, default=str).encode("utf-8")

    gridfs_id = fs.put(
        io.BytesIO(json_bytes),
        filename=f"{dataset_id}_cleaned.json",
        content_type="application/json",
        metadata={"dataset_id": dataset_id, "type": "cleaned"},
    )

    db.datasets.update_one(
        {"dataset_id": dataset_id},
        {
            "$set": {
                "status": "cleaned",
                "cleaned_gridfs_file_id": str(gridfs_id),
                "row_count_raw": row_count_raw,
                "valid_rows": valid_rows,
                "dropped_rows": dropped_rows,
                "cleaning_applied": cleaning_applied,
                "updated_at": datetime.now(timezone.utc),
            }
        },
    )


def read_cleaned_rows(dataset_id: str) -> list[dict]:
    """Retrieve the cleaned rows JSON from GridFS."""
    import json as _json

    document = get_dataset(dataset_id)
    if document is None:
        raise DatasetError(f"Dataset '{dataset_id}' not found.")

    db = get_database()
    fs = gridfs.GridFS(db)

    gridfs_id_str = document.get("cleaned_gridfs_file_id")
    if not gridfs_id_str:
        raise DatasetError(
            "Dataset has no cleaned data. Run POST /clean on this dataset first."
        )

    from bson import ObjectId

    grid_out = fs.get(ObjectId(gridfs_id_str))
    return _json.loads(grid_out.read())


def read_dataset_raw_bytes(dataset_id: str) -> bytes:
    """Retrieve the original CSV bytes from GridFS."""
    document = get_dataset(dataset_id)
    if document is None:
        raise DatasetError(f"Dataset '{dataset_id}' not found.")

    db = get_database()
    fs = gridfs.GridFS(db)

    gridfs_file_id_str = document.get("gridfs_file_id")
    if not gridfs_file_id_str:
        raise DatasetError("Dataset has no associated file in storage.")

    from bson import ObjectId
    grid_out = fs.get(ObjectId(gridfs_file_id_str))
    return grid_out.read()


def list_user_tickets(
    dataset_id: str,
    *,
    limit: int = 20,
    skip: int = 0,
) -> list[dict[str, Any]]:
    db = get_database()
    return list(
        db.user_tickets.find(
            {"dataset_id": dataset_id},
            {"_id": 0},
        ).sort("row_id", 1).skip(skip).limit(limit)
    )


def count_user_tickets(dataset_id: str) -> int:
    db = get_database()
    return db.user_tickets.count_documents({"dataset_id": dataset_id})


def delete_dataset(dataset_id: str) -> dict[str, Any]:
    """
    Cascade-delete a dataset: GridFS raw CSV, GridFS cleaned JSON,
    all user_tickets rows, and the dataset document itself.
    Returns deletion counts.
    """
    document = get_dataset(dataset_id)
    if document is None:
        raise DatasetError(f"Dataset '{dataset_id}' not found.")

    from bson import ObjectId

    db = get_database()
    fs = gridfs.GridFS(db)

    for field in ("gridfs_file_id", "cleaned_gridfs_file_id"):
        file_id_str = document.get(field)
        if file_id_str:
            try:
                fs.delete(ObjectId(file_id_str))
            except Exception:
                pass  # Already gone — continue

    tickets_result = db.user_tickets.delete_many({"dataset_id": dataset_id})
    db.datasets.delete_one({"dataset_id": dataset_id})

    return {
        "dataset_id": dataset_id,
        "deleted_tickets": tickets_result.deleted_count,
    }


def save_ingest_result(
    dataset_id: str,
    *,
    inserted: int,
    updated: int,
    total: int,
) -> None:
    db = get_database()
    db.datasets.update_one(
        {"dataset_id": dataset_id},
        {
            "$set": {
                "status": "ready",
                "ingested_count": total,
                "updated_at": datetime.now(timezone.utc),
            }
        },
    )


# ── Index setup (called at app startup) ───────────────────────────────────────

def ensure_dataset_indexes() -> None:
    from pymongo import ASCENDING, IndexModel

    db = get_database()
    db.datasets.create_indexes([
        IndexModel(
            [("dataset_id", ASCENDING)],
            unique=True,
            name="dataset_id_unique",
        ),
        IndexModel(
            [("file_hash", ASCENDING)],
            unique=True,
            name="file_hash_unique",
        ),
        IndexModel(
            [("user_id", ASCENDING)],
            name="dataset_user_id",
        ),
        IndexModel(
            [("status", ASCENDING)],
            name="dataset_status",
        ),
    ])


def ensure_user_ticket_indexes() -> None:
    from pymongo import ASCENDING, IndexModel

    db = get_database()
    db.user_tickets.create_indexes([
        IndexModel(
            [("dataset_id", ASCENDING), ("row_id", ASCENDING)],
            unique=True,
            name="user_ticket_dataset_row_unique",
        ),
        IndexModel(
            [("dataset_id", ASCENDING)],
            name="user_ticket_dataset_id",
        ),
    ])

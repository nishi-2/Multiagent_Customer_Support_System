from __future__ import annotations

import re

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from supportcommander.api.dependencies import require_api_key
from fastapi import Query

from supportcommander.services.dataset_service import (
    DatasetError,
    count_user_tickets,
    delete_dataset,
    get_dataset,
    list_datasets,
    list_user_tickets,
    read_dataset_raw_bytes,
    save_analysis_result,
    save_clean_result,
    save_ingest_result,
    store_dataset_file,
    update_dataset_status,
)

_ALLOWED_EXTENSIONS = {".csv"}
_ALLOWED_CONTENT_TYPES = {"text/csv", "application/csv", "application/octet-stream", "text/plain"}
_USER_ID_RE = re.compile(r"^[a-zA-Z0-9_\-]{1,64}$")

router = APIRouter(
    prefix="/api/v1/datasets",
    tags=["Datasets"],
    dependencies=[Depends(require_api_key)],
)


def _validate_user_id(user_id: str) -> None:
    if not _USER_ID_RE.match(user_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "user_id must be 1–64 characters: "
                "letters, digits, hyphens, and underscores only."
            ),
        )


def _validate_csv_file(file: UploadFile) -> None:
    name = (file.filename or "").strip()
    if not name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="File must have a name.",
        )

    ext = f".{name.rsplit('.', 1)[-1].lower()}" if "." in name else ""
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Only CSV files are accepted. Received: '{name}'",
        )


@router.post(
    "/upload",
    status_code=status.HTTP_201_CREATED,
    summary="Upload a customer-support CSV dataset",
    description=(
        "Upload a CSV file containing customer support data "
        "(tickets, complaints, feedback, reviews). "
        "Duplicate files are detected by content hash and returned instantly "
        "without re-processing. Files unrelated to customer support will be "
        "rejected in Phase 2 (analysis)."
    ),
)
async def upload_dataset(
    file: UploadFile = File(..., description="CSV file to upload (max 50 MB)"),
    user_id: str = Form(..., description="Your user identifier (alphanumeric, max 64 chars)"),
) -> dict:

    _validate_user_id(user_id)
    _validate_csv_file(file)

    file_bytes = await file.read()

    try:
        result = store_dataset_file(
            user_id=user_id,
            file_name=file.filename or "upload.csv",
            file_bytes=file_bytes,
        )
    except DatasetError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    is_duplicate = result.pop("duplicate", False)

    return {
        **result,
        "duplicate": is_duplicate,
        "message": (
            "File already processed. Dataset is ready to use."
            if is_duplicate
            else "File uploaded successfully. Proceed to /analyse to validate and ingest."
        ),
        "next_step": (
            None
            if is_duplicate
            else f"/api/v1/datasets/{result['dataset_id']}/analyse"
        ),
    }


@router.get(
    "",
    summary="List datasets for a user",
)
def get_user_datasets(user_id: str) -> list[dict]:
    _validate_user_id(user_id)
    return list_datasets(user_id)


@router.get(
    "/{dataset_id}",
    summary="Get dataset info and status",
)
def get_dataset_info(dataset_id: str) -> dict:
    document = get_dataset(dataset_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset '{dataset_id}' not found.",
        )
    return document


_CLEANED_STATUSES = {"cleaned", "ready"}
_TERMINAL_STATUSES = {"analysed", "rejected", "ready"}
_ANALYSABLE_STATUSES = {"uploaded"}


@router.post(
    "/{dataset_id}/analyse",
    summary="Validate domain and map columns (one LLM call per new file)",
    description=(
        "Validates that the dataset contains customer-support data, maps CSV columns "
        "to internal fields, and identifies cleaning flags. Idempotent — calling again "
        "on an already-analysed or rejected dataset returns the stored result without "
        "making another LLM call."
    ),
)
async def analyse_dataset_endpoint(dataset_id: str) -> dict:
    from supportcommander.agents.dataset_analyst import analyse_dataset
    from supportcommander.services.llm_service import LLMServiceError

    document = get_dataset(dataset_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset '{dataset_id}' not found.",
        )

    current_status = document.get("status", "")

    # Idempotent: already analysed / rejected / ready — return stored result
    if current_status in _TERMINAL_STATUSES:
        return {
            "dataset_id": dataset_id,
            "status": current_status,
            "cached": True,
            "is_customer_service_data": current_status != "rejected",
            "rejection_reason": document.get("rejection_reason"),
            "domain_confidence": document.get("domain_confidence"),
            "column_mapping": document.get("column_mapping"),
            "unmapped_columns": document.get("unmapped_columns", []),
            "cleaning_needed": document.get("cleaning_needed", False),
            "cleaning_flags": document.get("cleaning_flags", []),
        }

    if current_status == "analysing":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Analysis is already in progress for this dataset.",
        )

    if current_status not in _ANALYSABLE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Dataset cannot be analysed in its current state: '{current_status}'.",
        )

    # Lock the dataset to prevent duplicate concurrent analysis calls
    update_dataset_status(dataset_id, "analysing")

    try:
        file_bytes = read_dataset_raw_bytes(dataset_id)
    except DatasetError as exc:
        update_dataset_status(dataset_id, "uploaded")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not retrieve file for analysis: {exc}",
        ) from exc

    try:
        analysis = await analyse_dataset(file_bytes)
    except ValueError as exc:
        # CSV parse failure — put back to uploaded so the user can fix and re-try
        update_dataset_status(dataset_id, "uploaded")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except LLMServiceError as exc:
        update_dataset_status(dataset_id, "uploaded")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Analysis model error: {exc}",
        ) from exc
    except Exception as exc:
        update_dataset_status(dataset_id, "uploaded")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error during analysis: {exc}",
        ) from exc

    save_analysis_result(
        dataset_id,
        is_accepted=analysis.is_customer_service_data,
        rejection_reason=analysis.rejection_reason,
        domain_confidence=analysis.domain_confidence,
        column_mapping=analysis.column_mapping,
        unmapped_columns=analysis.unmapped_columns,
        cleaning_needed=analysis.cleaning_needed,
        cleaning_flags=analysis.cleaning_flags,
    )

    final_status = "analysed" if analysis.is_customer_service_data else "rejected"

    return {
        "dataset_id": dataset_id,
        "status": final_status,
        "cached": False,
        "is_customer_service_data": analysis.is_customer_service_data,
        "rejection_reason": analysis.rejection_reason,
        "domain_confidence": analysis.domain_confidence,
        "column_mapping": analysis.column_mapping,
        "unmapped_columns": analysis.unmapped_columns,
        "cleaning_needed": analysis.cleaning_needed,
        "cleaning_flags": analysis.cleaning_flags,
        "next_step": (
            f"/api/v1/datasets/{dataset_id}/clean"
            if analysis.is_customer_service_data
            else None
        ),
    }


@router.post(
    "/{dataset_id}/clean",
    summary="Deterministically clean an analysed dataset (no LLM)",
    description=(
        "Parses all CSV rows, applies the column mapping from analysis, and runs "
        "deterministic cleaning steps (HTML stripping, deduplication, date "
        "normalisation, etc.) based on the flags detected in /analyse. "
        "Idempotent — returns cached stats if already cleaned."
    ),
)
async def clean_dataset_endpoint(dataset_id: str) -> dict:
    from supportcommander.pipeline.cleaner import clean_dataset

    document = get_dataset(dataset_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset '{dataset_id}' not found.",
        )

    current_status = document.get("status", "")

    # Idempotent — return stored stats for already-cleaned datasets
    if current_status in _CLEANED_STATUSES:
        return {
            "dataset_id": dataset_id,
            "status": current_status,
            "cached": True,
            "row_count_raw": document.get("row_count_raw"),
            "valid_rows": document.get("valid_rows"),
            "dropped_rows": document.get("dropped_rows"),
            "cleaning_applied": document.get("cleaning_applied", []),
            "next_step": f"/api/v1/datasets/{dataset_id}/ingest",
        }

    if current_status == "cleaning":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cleaning is already in progress for this dataset.",
        )

    if current_status != "analysed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Dataset must be in 'analysed' state before cleaning. "
                f"Current state: '{current_status}'."
            ),
        )

    column_mapping: dict = document.get("column_mapping") or {}
    cleaning_flags: list = document.get("cleaning_flags") or []

    # Lock to prevent concurrent clean calls
    update_dataset_status(dataset_id, "cleaning")

    try:
        file_bytes = read_dataset_raw_bytes(dataset_id)
    except DatasetError as exc:
        update_dataset_status(dataset_id, "analysed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not retrieve file for cleaning: {exc}",
        ) from exc

    try:
        result = clean_dataset(file_bytes, column_mapping, cleaning_flags)
    except ValueError as exc:
        update_dataset_status(dataset_id, "analysed")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        update_dataset_status(dataset_id, "analysed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Cleaning failed unexpectedly: {exc}",
        ) from exc

    save_clean_result(
        dataset_id,
        cleaned_rows=result.rows,
        row_count_raw=result.row_count_raw,
        valid_rows=result.valid_rows,
        dropped_rows=result.dropped_rows,
        cleaning_applied=result.cleaning_applied,
    )

    return {
        "dataset_id": dataset_id,
        "status": "cleaned",
        "cached": False,
        "row_count_raw": result.row_count_raw,
        "valid_rows": result.valid_rows,
        "dropped_rows": result.dropped_rows,
        "cleaning_applied": result.cleaning_applied,
        "next_step": f"/api/v1/datasets/{dataset_id}/ingest",
    }


@router.post(
    "/{dataset_id}/ingest",
    summary="Normalise cleaned rows into the user_tickets collection",
    description=(
        "Reads the cleaned rows produced by /clean and bulk-upserts them into "
        "the user_tickets collection with a stable (dataset_id, row_id) key. "
        "Safe to call multiple times — existing rows are updated in-place. "
        "Dataset status transitions to 'ready' on success."
    ),
)
async def ingest_dataset_endpoint(dataset_id: str) -> dict:
    from supportcommander.pipeline.ingestor import ingest_dataset

    document = get_dataset(dataset_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset '{dataset_id}' not found.",
        )

    current_status = document.get("status", "")

    # Idempotent — already ingested
    if current_status == "ready":
        return {
            "dataset_id": dataset_id,
            "status": "ready",
            "cached": True,
            "inserted": 0,
            "updated": 0,
            "total": document.get("ingested_count", 0),
        }

    if current_status == "ingesting":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ingestion is already in progress for this dataset.",
        )

    if current_status != "cleaned":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Dataset must be in 'cleaned' state before ingestion. "
                f"Current state: '{current_status}'. "
                f"Run POST /api/v1/datasets/{dataset_id}/clean first."
            ),
        )

    # Lock to prevent concurrent ingest calls
    update_dataset_status(dataset_id, "ingesting")

    try:
        result = ingest_dataset(dataset_id)
    except DatasetError as exc:
        update_dataset_status(dataset_id, "cleaned")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not read cleaned data: {exc}",
        ) from exc
    except Exception as exc:
        update_dataset_status(dataset_id, "cleaned")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ingestion failed unexpectedly: {exc}",
        ) from exc

    save_ingest_result(
        dataset_id,
        inserted=result.inserted,
        updated=result.updated,
        total=result.total,
    )

    return {
        "dataset_id": dataset_id,
        "status": "ready",
        "cached": False,
        "inserted": result.inserted,
        "updated": result.updated,
        "total": result.total,
    }


# ── In-progress statuses that must not be interrupted by a delete ─────────────
_BUSY_STATUSES = {"analysing", "cleaning", "ingesting"}


@router.delete(
    "/{dataset_id}",
    summary="Delete a dataset and all its data",
    description=(
        "Permanently removes the dataset document, both GridFS files "
        "(raw CSV and cleaned JSON), and all ingested user_tickets rows. "
        "Datasets currently being processed (analysing, cleaning, ingesting) "
        "cannot be deleted."
    ),
)
def delete_dataset_endpoint(dataset_id: str) -> dict:
    document = get_dataset(dataset_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset '{dataset_id}' not found.",
        )

    current_status = document.get("status", "")
    if current_status in _BUSY_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Dataset '{dataset_id}' is currently being processed "
                f"(status: '{current_status}'). Wait for processing to "
                "complete or fail before deleting."
            ),
        )

    try:
        result = delete_dataset(dataset_id)
    except DatasetError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    return {
        **result,
        "message": (
            f"Dataset '{dataset_id}' and all associated data deleted successfully."
        ),
    }


@router.get(
    "/{dataset_id}/tickets",
    summary="List ingested tickets for a dataset",
    description=(
        "Returns paginated rows from the user_tickets collection for this "
        "dataset. Only available once the dataset status is 'ready'."
    ),
)
def list_dataset_tickets(
    dataset_id: str,
    limit: int = Query(default=20, ge=1, le=100, description="Rows per page"),
    skip: int = Query(default=0, ge=0, description="Rows to skip"),
) -> dict:
    document = get_dataset(dataset_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset '{dataset_id}' not found.",
        )

    if document.get("status") != "ready":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Tickets are not available yet — dataset status is "
                f"'{document.get('status')}'. Run the full pipeline "
                "(analyse → clean → ingest) to reach 'ready' status."
            ),
        )

    tickets = list_user_tickets(dataset_id, limit=limit, skip=skip)
    total = count_user_tickets(dataset_id)

    return {
        "dataset_id": dataset_id,
        "total": total,
        "limit": limit,
        "skip": skip,
        "tickets": tickets,
    }

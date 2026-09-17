from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from supportcommander.services.pdf_service import (
    MAX_BATCH,
    MAX_FILE_BYTES,
    MAX_PAGES,
    delete_document,
    get_document,
    list_documents,
    process_pdf,
)

router = APIRouter(prefix="/api/v1/knowledge-base", tags=["Knowledge Base"])


@router.post("/upload", summary="Upload up to 5 PDF documents into the knowledge base")
async def upload_documents(
    files: list[UploadFile] = File(...),
    doc_type: str = "general",
) -> list[dict]:
    """
    Process each PDF: extract text, chunk, embed, store.
    Per-file caps: 25 MB, 150 pages, text-based only.
    Batch cap: 5 files per request.
    Returns a result entry per file with status 'ready' or 'rejected'.
    """
    if len(files) > MAX_BATCH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum {MAX_BATCH} files per upload. Received {len(files)}.",
        )

    results: list[dict] = []

    for upload in files:
        filename = upload.filename or "unnamed.pdf"

        if not filename.lower().endswith(".pdf"):
            results.append({
                "filename": filename,
                "status":   "rejected",
                "error":    "Only PDF files are accepted.",
            })
            continue

        file_bytes = await upload.read()

        if len(file_bytes) > MAX_FILE_BYTES:
            mb = len(file_bytes) / 1024 / 1024
            results.append({
                "filename": filename,
                "status":   "rejected",
                "error":    f"File is {mb:.1f} MB — exceeds the 25 MB limit.",
            })
            continue

        try:
            doc_meta = await process_pdf(file_bytes, filename, doc_type=doc_type)
            results.append({"status": "ready", **doc_meta})
        except ValueError as exc:
            results.append({
                "filename": filename,
                "status":   "rejected",
                "error":    str(exc),
            })
        except Exception as exc:
            results.append({
                "filename": filename,
                "status":   "error",
                "error":    f"Processing failed: {exc}",
            })

    return results


@router.get("/documents", summary="List all documents in the knowledge base")
def get_documents() -> list[dict]:
    return list_documents()


@router.get("/documents/{doc_id}", summary="Get metadata for a single document")
def get_document_by_id(doc_id: str) -> dict:
    doc = get_document(doc_id)
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{doc_id}' not found.",
        )
    return doc


@router.delete("/documents/{doc_id}", summary="Delete a document and all its chunks")
def remove_document(doc_id: str) -> dict:
    found = delete_document(doc_id)
    if not found:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{doc_id}' not found.",
        )
    return {"doc_id": doc_id, "status": "deleted"}


@router.get("/stats", summary="Knowledge base statistics")
def kb_stats() -> dict:
    from supportcommander.db.mongo import get_database
    db = get_database()
    doc_count   = db.kb_documents.count_documents({})
    chunk_count = db.kb_chunks.count_documents({})
    return {
        "documents":   doc_count,
        "chunks":      chunk_count,
        "caps": {
            "max_file_mb":    MAX_FILE_BYTES // (1024 * 1024),
            "max_pages":      MAX_PAGES,
            "max_batch":      MAX_BATCH,
        },
    }

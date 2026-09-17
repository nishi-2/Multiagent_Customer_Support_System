"""
PDF ingestion pipeline: validate → extract → chunk → embed → store.

Caps enforced:
  Max file size : 25 MB
  Max pages     : 150
  Max batch     : 5 files per upload

Chunking:
  Target size   : ~512 tokens  (≈ 2 048 chars, 1 token ≈ 4 chars)
  Overlap       : ~100 tokens  (≈ 400 chars)
  Strategy      : paragraph-aware split, hard-split only if paragraph
                  exceeds the target size
"""
from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any

import pymupdf

from supportcommander.db.mongo import get_database
from supportcommander.services.embedding_service import generate_embedding

logger = logging.getLogger(__name__)

# ── Hard caps ─────────────────────────────────────────────────────────────────
MAX_FILE_BYTES       = 25 * 1024 * 1024   # 25 MB
MAX_PAGES            = 150
MAX_BATCH            = 5
MIN_EXTRACTABLE_CHARS = 100               # below → image-only PDF

# ── Chunking constants (char-based token approximation) ───────────────────────
CHUNK_CHARS   = 512 * 4    # ≈ 2 048 chars  ≈ 512 tokens
OVERLAP_CHARS = 100 * 4    # ≈ 400  chars  ≈ 100 tokens

# ── Retrieval threshold ───────────────────────────────────────────────────────
SIMILARITY_THRESHOLD = 0.75


# ── Validation ────────────────────────────────────────────────────────────────

def validate_upload(file_bytes: bytes, filename: str) -> None:
    if not filename.lower().endswith(".pdf"):
        raise ValueError(f"'{filename}' is not a PDF file.")
    if len(file_bytes) > MAX_FILE_BYTES:
        mb = len(file_bytes) / 1024 / 1024
        raise ValueError(
            f"'{filename}' is {mb:.1f} MB — exceeds the 25 MB limit."
        )


# ── Extraction ────────────────────────────────────────────────────────────────

def extract_text(file_bytes: bytes, filename: str) -> tuple[str, int]:
    """
    Open PDF bytes with PyMuPDF and extract plain text.
    Returns (full_text, page_count).
    Raises ValueError for image-only PDFs or oversized docs.
    """
    try:
        doc = pymupdf.open(stream=file_bytes, filetype="pdf")
    except Exception as exc:
        raise ValueError(f"Could not open '{filename}' as a PDF: {exc}") from exc

    page_count = len(doc)

    if page_count > MAX_PAGES:
        raise ValueError(
            f"'{filename}' has {page_count} pages — exceeds the 150-page limit."
        )

    page_texts: list[str] = []
    for page in doc:
        page_texts.append(page.get_text())

    full_text = "\n\n".join(page_texts)
    full_text = re.sub(r"\n{3,}", "\n\n", full_text).strip()

    if len(full_text) < MIN_EXTRACTABLE_CHARS:
        raise ValueError(
            f"'{filename}' appears to be an image-based (scanned) PDF — "
            "no text could be extracted. Please upload a text-based PDF."
        )

    return full_text, page_count


# ── Chunking ──────────────────────────────────────────────────────────────────

def _hard_split(text: str, doc_id: str, start_index: int) -> list[dict[str, Any]]:
    """Hard-split a single oversized paragraph into CHUNK_CHARS pieces with overlap."""
    chunks = []
    pos = 0
    idx = start_index
    while pos < len(text):
        end = pos + CHUNK_CHARS
        content = text[pos:end].strip()
        if content:
            chunks.append({
                "chunk_id":    f"{doc_id}_c{idx:04d}",
                "doc_id":      doc_id,
                "chunk_index": idx,
                "content":     content,
            })
            idx += 1
        pos = end - OVERLAP_CHARS
    return chunks


def chunk_text(text: str, doc_id: str, filename: str) -> list[dict[str, Any]]:
    """
    Paragraph-aware chunking with overlap.
    Each chunk gets doc_id, filename, chunk_index, and content.
    """
    paragraphs = [p.strip() for p in re.split(r"\n\n+", text) if p.strip()]
    chunks: list[dict[str, Any]] = []
    current = ""
    idx = 0

    for para in paragraphs:
        # Single paragraph too big → hard-split it directly
        if len(para) > CHUNK_CHARS:
            if current.strip():
                chunks.append({
                    "chunk_id":    f"{doc_id}_c{idx:04d}",
                    "doc_id":      doc_id,
                    "chunk_index": idx,
                    "content":     current.strip(),
                })
                idx += 1
                current = ""
            sub = _hard_split(para, doc_id, idx)
            idx += len(sub)
            chunks.extend(sub)
            continue

        if current and len(current) + len(para) + 2 > CHUNK_CHARS:
            chunks.append({
                "chunk_id":    f"{doc_id}_c{idx:04d}",
                "doc_id":      doc_id,
                "chunk_index": idx,
                "content":     current.strip(),
            })
            idx += 1
            current = current[-OVERLAP_CHARS:].strip() + "\n\n" + para
        else:
            current = (current + "\n\n" + para).strip() if current else para

    if current.strip():
        chunks.append({
            "chunk_id":    f"{doc_id}_c{idx:04d}",
            "doc_id":      doc_id,
            "chunk_index": idx,
            "content":     current.strip(),
        })

    for chunk in chunks:
        chunk["filename"] = filename

    return chunks


# ── Embed + store ─────────────────────────────────────────────────────────────

async def _embed_and_store_chunks(
    doc_id: str,
    chunks: list[dict[str, Any]],
) -> int:
    """Embed each chunk and bulk-insert into kb_chunks. Returns stored count."""
    db = get_database()
    embedded: list[dict] = []

    for chunk in chunks:
        try:
            result = await generate_embedding(chunk["content"])
            embedded.append({
                **chunk,
                "embedding":       result.embedding,
                "embedding_model": result.model,
            })
        except Exception as exc:
            logger.warning("Embedding failed for chunk %s: %s", chunk["chunk_id"], exc)

    if embedded:
        db.kb_chunks.insert_many(embedded)

    return len(embedded)


# ── Main entry point ──────────────────────────────────────────────────────────

async def process_pdf(
    file_bytes: bytes,
    filename: str,
    doc_type: str = "general",
) -> dict:
    """
    Full pipeline: validate → extract → chunk → embed → store.
    Returns the document metadata dict (without _id).
    Raises ValueError for user-facing validation failures.
    """
    validate_upload(file_bytes, filename)

    full_text, page_count = extract_text(file_bytes, filename)

    doc_id = str(uuid.uuid4())
    chunks = chunk_text(full_text, doc_id, filename)

    stored_count = await _embed_and_store_chunks(doc_id, chunks)

    doc_meta: dict[str, Any] = {
        "doc_id":      doc_id,
        "filename":    filename,
        "doc_type":    doc_type,
        "page_count":  page_count,
        "chunk_count": stored_count,
        "char_count":  len(full_text),
        "times_cited": 0,
        "upload_date": datetime.now(timezone.utc).isoformat(),
        "status":      "ready",
    }

    db = get_database()
    db.kb_documents.insert_one({**doc_meta, "_id": doc_id})

    logger.info(
        "KB doc ingested | doc_id=%s file=%s pages=%d chunks=%d",
        doc_id, filename, page_count, stored_count,
    )

    return doc_meta


# ── Document management ───────────────────────────────────────────────────────

def list_documents() -> list[dict]:
    db = get_database()
    docs = list(db.kb_documents.find({}, {"_id": 0}))
    return sorted(docs, key=lambda d: d.get("upload_date", ""), reverse=True)


def get_document(doc_id: str) -> dict | None:
    db = get_database()
    return db.kb_documents.find_one({"doc_id": doc_id}, {"_id": 0})


def delete_document(doc_id: str) -> bool:
    """Delete document metadata and all its chunks. Returns False if not found."""
    db = get_database()
    doc = db.kb_documents.find_one({"doc_id": doc_id})
    if not doc:
        return False
    db.kb_chunks.delete_many({"doc_id": doc_id})
    db.kb_documents.delete_one({"_id": doc_id})
    logger.info("KB doc deleted | doc_id=%s file=%s", doc_id, doc.get("filename"))
    return True

from __future__ import annotations

import csv
import io
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime

_ENCODINGS_TO_TRY = ("utf-8-sig", "utf-8", "latin-1", "cp1252")
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_CTRL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# In decreasing specificity so that longer patterns match first
_DATE_FORMATS = [
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
    "%d/%m/%Y %H:%M:%S",
    "%m/%d/%Y %H:%M:%S",
    "%d/%m/%Y",
    "%m/%d/%Y",
    "%d-%m-%Y",
    "%m-%d-%Y",
    "%d %B %Y",
    "%d %b %Y",
    "%B %d, %Y",
    "%b %d, %Y",
]


@dataclass
class CleanResult:
    rows: list[dict[str, str]]
    row_count_raw: int
    valid_rows: int
    dropped_rows: int
    cleaning_applied: list[str]


# ── CSV decode & parse ────────────────────────────────────────────────────────

def _decode_csv(file_bytes: bytes) -> str:
    for enc in _ENCODINGS_TO_TRY:
        try:
            return file_bytes.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    raise ValueError(
        "Could not decode the CSV file. Please re-save as UTF-8 and re-upload."
    )


def _detect_dialect(text: str) -> csv.Dialect:
    try:
        return csv.Sniffer().sniff(text[:8192], delimiters=",;\t|")
    except csv.Error:
        return csv.excel


def _parse_all_rows(
    file_bytes: bytes,
    column_mapping: dict[str, str],
) -> tuple[list[dict[str, str]], int]:
    """
    Parse every row in the CSV and apply column_mapping to rename keys.
    Unknown CSV columns are silently dropped.
    Returns (mapped_rows, raw_row_count).
    """
    text = _decode_csv(file_bytes)
    dialect = _detect_dialect(text)
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)

    # Normalise mapping keys once (strip leading/trailing whitespace)
    norm_mapping: dict[str, str] = {k.strip(): v for k, v in column_mapping.items()}
    # Also build a lower-case fallback for case-insensitive lookup
    lower_mapping: dict[str, str] = {k.lower(): v for k, v in norm_mapping.items()}

    raw_count = 0
    mapped_rows: list[dict[str, str]] = []

    for row in reader:
        raw_count += 1
        mapped: dict[str, str] = {}
        for csv_col, raw_val in row.items():
            col_stripped = (csv_col or "").strip()
            # Exact match first, case-insensitive fallback
            internal = norm_mapping.get(col_stripped) or lower_mapping.get(
                col_stripped.lower()
            )
            if internal:
                mapped[internal] = (raw_val or "").strip()
        mapped_rows.append(mapped)

    return mapped_rows, raw_count


# ── Per-value transformations ─────────────────────────────────────────────────

def _strip_html(val: str) -> str:
    import html as _html

    val = _HTML_TAG_RE.sub(" ", val)
    val = _html.unescape(val)
    return " ".join(val.split())


def _strip_control_chars(val: str) -> str:
    return _CTRL_CHAR_RE.sub("", val)


def _normalize_unicode(val: str) -> str:
    return unicodedata.normalize("NFKC", val)


def _normalize_date(val: str) -> str:
    if not val:
        return val
    val = val.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(val, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return val  # keep original if no format matched


# ── Main entry point ──────────────────────────────────────────────────────────

def clean_dataset(
    file_bytes: bytes,
    column_mapping: dict[str, str],
    cleaning_flags: list[str],
) -> CleanResult:
    """
    Parse all rows from the CSV, apply column_mapping, and run each
    deterministic cleaning step indicated by cleaning_flags.

    Always drops rows where ticket_text is empty (safety baseline).
    """
    if not column_mapping:
        raise ValueError(
            "column_mapping is empty — run /analyse on this dataset first."
        )

    flags = set(cleaning_flags)
    rows, raw_count = _parse_all_rows(file_bytes, column_mapping)
    cleaning_applied: list[str] = []

    # trailing_whitespace is handled in _parse_all_rows (always strip)
    if "trailing_whitespace" in flags:
        cleaning_applied.append("trailing_whitespace")

    # ── Text-level transforms ─────────────────────────────────────────────────
    apply_html = "html_content" in flags
    apply_unicode = "mixed_encoding" in flags
    apply_ctrl = "control_characters" in flags

    if apply_html or apply_unicode or apply_ctrl:
        for row in rows:
            for key in list(row.keys()):
                val = row[key]
                if not val:
                    continue
                if apply_html:
                    val = _strip_html(val)
                if apply_unicode:
                    val = _normalize_unicode(val)
                if apply_ctrl:
                    val = _strip_control_chars(val)
                row[key] = val

        if apply_html:
            cleaning_applied.append("html_content")
        if apply_unicode:
            cleaning_applied.append("mixed_encoding")
        if apply_ctrl:
            cleaning_applied.append("control_characters")

    # ── Date normalisation ────────────────────────────────────────────────────
    has_date_field = "ticket_date" in column_mapping.values()
    if "inconsistent_dates" in flags and has_date_field:
        for row in rows:
            if "ticket_date" in row and row["ticket_date"]:
                row["ticket_date"] = _normalize_date(row["ticket_date"])
        cleaning_applied.append("inconsistent_dates")

    # ── Drop rows with empty ticket_text (always — rows are unusable without it)
    before_null = len(rows)
    rows = [r for r in rows if r.get("ticket_text", "").strip()]
    null_dropped = before_null - len(rows)
    if null_dropped > 0 or "null_text_rows" in flags:
        if "null_text_rows" in flags:
            cleaning_applied.append("null_text_rows")

    # ── Deduplicate on ticket_text ────────────────────────────────────────────
    if "has_duplicates" in flags:
        seen: set[str] = set()
        unique: list[dict[str, str]] = []
        for row in rows:
            key = row.get("ticket_text", "").strip().lower()
            if key not in seen:
                seen.add(key)
                unique.append(row)
        if len(unique) < len(rows):
            cleaning_applied.append("has_duplicates")
        rows = unique

    valid = len(rows)
    dropped = raw_count - valid

    return CleanResult(
        rows=rows,
        row_count_raw=raw_count,
        valid_rows=valid,
        dropped_rows=dropped,
        cleaning_applied=cleaning_applied,
    )

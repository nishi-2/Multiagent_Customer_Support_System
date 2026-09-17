from __future__ import annotations

import csv
import io
import json
from typing import Any, Literal

from pydantic import BaseModel, field_validator

from supportcommander.services.llm_service import LLMServiceError, generate_text


# ── Constants ─────────────────────────────────────────────────────────────────

VALID_INTERNAL_FIELDS = {
    "ticket_text",          # REQUIRED — main complaint / message body
    "ticket_subject",       # subject or title line
    "customer_identifier",  # email, user_id, customer name
    "ticket_date",          # creation timestamp
    "intent_hint",          # category, type, department, topic
    "urgency",              # priority / severity
    "ticket_status",        # open / closed / resolved
    "ticket_id",            # unique case / ticket ID
}

VALID_CLEANING_FLAGS = {
    "has_duplicates",
    "null_text_rows",
    "trailing_whitespace",
    "inconsistent_dates",
    "html_content",
    "mixed_encoding",
    "control_characters",
}

_ENCODINGS_TO_TRY = ("utf-8-sig", "utf-8", "latin-1", "cp1252")

_ANALYST_INSTRUCTIONS = """
You are a data analyst for a customer support AI platform.

You receive a JSON object with two keys:
- "columns": list of column names from a CSV file
- "sample_rows": up to 5 sample data rows (list of objects)

Your job:
1. Decide if this is customer support / feedback / complaint data.
2. Map CSV columns to our internal schema fields.
3. Identify data quality issues.

━━━ WHAT COUNTS AS CUSTOMER SUPPORT DATA ━━━
Accept:
• Help desk / support tickets
• Customer complaints or grievances
• Product or service feedback and reviews
• Customer service chat logs or transcripts
• Survey responses about a product or service experience
• E-commerce order complaints

Reject (with a clear reason):
• Financial transactions, stock data, sensor readings
• Medical / clinical records
• HR, payroll, or employee data
• Product catalogs or inventory lists
• Anything where there is no customer-facing message or complaint text

━━━ INTERNAL SCHEMA FIELDS ━━━
Map each relevant CSV column to exactly one of these values:

  ticket_text          REQUIRED — the main complaint, message, or review body
  ticket_subject       subject line or title (optional)
  customer_identifier  customer email, ID, or username (optional)
  ticket_date          creation date or timestamp (optional)
  intent_hint          category, type, department, or topic tag (optional)
  urgency              priority or severity level (optional)
  ticket_status        open / closed / resolved status (optional)
  ticket_id            unique ticket or case identifier (optional)

Rules:
• Only use the exact field names listed above.
• A CSV column may map to at most one internal field.
• If ticket_text cannot be clearly identified, set is_customer_service_data to false.
• Leave unmapped columns in "unmapped_columns".

━━━ CLEANING FLAGS ━━━
Include any of the following that apply based on the sample:
  has_duplicates        — rows appear identical or near-identical
  null_text_rows        — main text column has empty/null values
  trailing_whitespace   — leading or trailing whitespace visible
  inconsistent_dates    — dates appear in mixed formats
  html_content          — HTML tags visible in text fields
  mixed_encoding        — non-UTF-8 characters visible
  control_characters    — special / control characters in text

━━━ RESPONSE FORMAT ━━━
Respond ONLY with valid JSON — no markdown fences, no commentary:

{
  "is_customer_service_data": true,
  "rejection_reason": null,
  "domain_confidence": "high",
  "column_mapping": {
    "<csv_column_name>": "<internal_field_name>"
  },
  "unmapped_columns": ["col1", "col2"],
  "cleaning_needed": true,
  "cleaning_flags": ["flag1", "flag2"]
}

domain_confidence must be one of: "high", "medium", "low"
"""


# ── Pydantic model for structured LLM output ──────────────────────────────────

class DatasetAnalysis(BaseModel):
    is_customer_service_data: bool
    rejection_reason: str | None = None
    domain_confidence: Literal["high", "medium", "low"] = "medium"
    column_mapping: dict[str, str] = {}
    unmapped_columns: list[str] = []
    cleaning_needed: bool = False
    cleaning_flags: list[str] = []

    @field_validator("column_mapping")
    @classmethod
    def _check_mapping_values(cls, v: dict[str, str]) -> dict[str, str]:
        invalid = {val for val in v.values() if val not in VALID_INTERNAL_FIELDS}
        if invalid:
            # Strip unknown targets rather than hard-failing — keeps partial results
            return {k: val for k, val in v.items() if val in VALID_INTERNAL_FIELDS}
        return v

    @field_validator("cleaning_flags")
    @classmethod
    def _check_cleaning_flags(cls, v: list[str]) -> list[str]:
        return [f for f in v if f in VALID_CLEANING_FLAGS]


# ── CSV parsing (deterministic, no model) ────────────────────────────────────

def parse_csv_preview(
    file_bytes: bytes,
    max_rows: int = 5,
) -> tuple[list[str], list[dict[str, Any]]]:
    """
    Decode the CSV bytes and return (column_names, sample_rows).
    Tries multiple encodings; uses csv.Sniffer for delimiter detection.
    """
    text: str | None = None
    for enc in _ENCODINGS_TO_TRY:
        try:
            text = file_bytes.decode(enc)
            break
        except (UnicodeDecodeError, LookupError):
            continue

    if text is None:
        raise ValueError(
            "Could not decode the CSV file. "
            "Please save it as UTF-8 and re-upload."
        )

    # Detect delimiter from the first 8 KB
    sample = text[:8192]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel  # safe fallback: comma-delimited

    reader = csv.DictReader(io.StringIO(text), dialect=dialect)

    columns: list[str] = [c.strip() for c in (reader.fieldnames or [])]
    if not columns:
        raise ValueError("CSV file has no header row or could not be parsed.")

    rows: list[dict[str, Any]] = []
    for row in reader:
        # Skip completely blank rows
        stripped = {k.strip(): (v.strip() if isinstance(v, str) else v) for k, v in row.items()}
        if not any(stripped.values()):
            continue
        rows.append(stripped)
        if len(rows) >= max_rows:
            break

    return columns, rows


def _build_analyst_input(columns: list[str], sample_rows: list[dict]) -> str:
    return json.dumps(
        {"columns": columns, "sample_rows": sample_rows},
        ensure_ascii=False,
        default=str,
    )


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
        text = "\n".join(lines[1:end])
    return text.strip()


# ── Main entry point ──────────────────────────────────────────────────────────

async def analyse_dataset(file_bytes: bytes) -> DatasetAnalysis:
    """
    Parse the CSV preview and call the LLM once to:
    - validate domain
    - produce column mapping
    - identify cleaning flags

    Raises LLMServiceError on model failure.
    Raises ValueError on CSV parse failure.
    """
    columns, sample_rows = parse_csv_preview(file_bytes)

    analyst_input = _build_analyst_input(columns, sample_rows)

    llm_result = await generate_text(
        instructions=_ANALYST_INSTRUCTIONS,
        input_text=analyst_input,
        _agent_name="dataset_analyst",
    )

    raw = _strip_fences(llm_result.text)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LLMServiceError(
            f"Dataset analyst returned invalid JSON: {exc}"
        ) from exc

    try:
        analysis = DatasetAnalysis(**data)
    except Exception as exc:
        raise LLMServiceError(
            f"Dataset analyst output failed schema validation: {exc}"
        ) from exc

    # Hard rule: ticket_text MUST be mapped — without it, workflows cannot run
    if analysis.is_customer_service_data:
        if "ticket_text" not in analysis.column_mapping.values():
            analysis.is_customer_service_data = False
            analysis.rejection_reason = (
                "No customer complaint or message text column could be identified. "
                "A column containing the main message body is required."
            )
            analysis.column_mapping = {}
            analysis.domain_confidence = "low"

    return analysis

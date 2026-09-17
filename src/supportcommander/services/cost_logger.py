"""
Writes cost log dicts produced by cost_tracker.finish() to
  <project_root>/cost_logs/<user>_<YYYYMMDD_HHMMSS_ffffff>.json

The directory is created on first use.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# cost_logs/ sits at the project root, two levels above this file's package.
# src/supportcommander/services/cost_logger.py  →  ../../..  →  project root
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
COST_LOGS_DIR = _PROJECT_ROOT / "cost_logs"


def save(log: dict) -> str:
    """
    Persist *log* as a JSON file.

    Returns the absolute path of the written file.
    """
    COST_LOGS_DIR.mkdir(parents=True, exist_ok=True)

    user = str(log.get("user", "unknown")).replace("/", "_").replace("\\", "_")[:32]
    ts   = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    filename = f"{user}_{ts}.json"
    path = COST_LOGS_DIR / filename

    with path.open("w", encoding="utf-8") as fh:
        json.dump(log, fh, indent=2, ensure_ascii=False)

    logger.info(
        "cost_log saved | workflow=%s tokens=%s cost=$%.6f file=%s",
        log.get("workflow_id", "?"),
        log.get("summary", {}).get("total_tokens", "?"),
        log.get("summary", {}).get("total_cost_usd", 0),
        filename,
    )
    return str(path)

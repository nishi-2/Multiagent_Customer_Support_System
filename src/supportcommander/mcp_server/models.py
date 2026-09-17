from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class SupportToolResult(BaseModel):
    success: bool
    data: dict[str, Any] | list[dict[str, Any]] | None = None
    error: str | None = None


class TransactionToolResult(BaseModel):
    success: bool

    transaction_id: str | None = None

    data: dict[str, Any] | None = None

    error: str | None = None
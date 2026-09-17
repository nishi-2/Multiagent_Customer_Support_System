from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


def serialize_value(value: Any,) -> Any:
    if isinstance(value, BaseModel,):
        return value.model_dump(mode="json")

    if isinstance(value, datetime):
        return value.isoformat()

    if isinstance(value, list):
        return [serialize_value(item) for item in value]

    if isinstance(value, dict):
        return {key: serialize_value(item) for key, item in value.items()}

    return value


def serialize_state(state: dict,) -> dict:
    return {key: serialize_value(value) for key, value in state.items()}
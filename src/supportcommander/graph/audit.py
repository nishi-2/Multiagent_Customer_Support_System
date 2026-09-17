from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from supportcommander.graph.models import AuditEvent
from supportcommander.graph.state import SupportGraphState


def append_audit_event(state: SupportGraphState, *, event_type: str, actor: str, message: str, metadata: dict[str, Any] | None = None) -> None:
    event = AuditEvent(
        timestamp=datetime.now(timezone.utc),
        event_type=event_type,
        actor=actor,
        message=message,
        metadata=metadata or {},
    )

    state.setdefault("audit_events", [],).append(event)
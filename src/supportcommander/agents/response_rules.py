from __future__ import annotations

from supportcommander.graph.models import FinalResponse


class ResponseValidationError(Exception):
    pass


VALID_STATUSES = {
    "resolved",
    "pending_customer",
    "pending_approval",
    "escalated",
    "failed",
}


def validate_final_response(
    response: FinalResponse,
) -> None:

    if not response.message or not response.message.strip():
        raise ResponseValidationError(
            "Response message is empty."
        )

    if len(response.message.strip()) < 20:
        raise ResponseValidationError(
            "Response message is too short."
        )

    if not response.resolution_status:
        raise ResponseValidationError(
            "Resolution status is missing."
        )

    if response.resolution_status not in VALID_STATUSES:
        raise ResponseValidationError(
            f"Unknown resolution status: "
            f"{response.resolution_status}"
        )

import pytest

from supportcommander.agents.response_rules import (
    ResponseValidationError,
    validate_final_response,
)
from supportcommander.graph.models import FinalResponse


def make_response(**kwargs) -> FinalResponse:
    defaults = {
        "message": "Thank you for contacting us. Your refund of $50.00 has been processed.",
        "resolution_status": "resolved",
    }
    defaults.update(kwargs)
    return FinalResponse(**defaults)


def test_valid_response_passes():
    response = make_response()
    validate_final_response(response)


def test_empty_message_fails():
    response = make_response(message="")
    with pytest.raises(ResponseValidationError, match="empty"):
        validate_final_response(response)


def test_whitespace_only_message_fails():
    response = make_response(message="   ")
    with pytest.raises(ResponseValidationError, match="empty"):
        validate_final_response(response)


def test_too_short_message_fails():
    response = make_response(message="Hi there.")
    with pytest.raises(ResponseValidationError, match="too short"):
        validate_final_response(response)


def test_invalid_status_fails():
    response = make_response(resolution_status="unknown_status")
    with pytest.raises(ResponseValidationError, match="Unknown resolution status"):
        validate_final_response(response)


def test_all_valid_statuses_pass():
    valid = [
        "resolved",
        "pending_customer",
        "pending_approval",
        "escalated",
        "failed",
    ]
    for status in valid:
        response = make_response(resolution_status=status)
        validate_final_response(response)


def test_optional_fields_accepted():
    response = make_response(
        action_summary="Issued refund of $50.",
        requires_follow_up=True,
        internal_notes="Customer was very polite.",
    )
    validate_final_response(response)


def test_missing_resolution_status_fails():
    with pytest.raises(Exception):
        FinalResponse(message="A valid long enough message for the test.")

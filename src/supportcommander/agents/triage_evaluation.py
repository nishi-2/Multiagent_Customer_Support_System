SOURCE_TYPE_TO_INTENT = {
    "Refund request":"refund_request",
    "Technical issue":"technical_issue",
    "Cancellation request":"cancellation_request",
    "Product inquiry":"product_inquiry",
    "Billing inquiry":"billing_inquiry",
}


def expected_intent(ticket_type: str,) -> str | None:
    return SOURCE_TYPE_TO_INTENT.get(ticket_type)
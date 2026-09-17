import asyncio

from supportcommander.services.llm_service import generate_text
from supportcommander.services.ticket_service import get_ticket


async def main() -> None:
    ticket = get_ticket(1)

    if ticket is None:
        raise RuntimeError("Ticket 1 not found")
    
    print("=" * 70)
    print("SupportCommander Ticket LLM Test")
    print("=" * 70)
    print(f"Ticket ID: {ticket['ticket_id']}")
    print(f"Source type: {ticket['ticket_type']}")
    print(f"Priority: {ticket['ticket_priority']}")

    print()
    print("Sending ticket to model...")

    result = await generate_text(
        instructions=(
            "You are testing a customer support analysis system. "
            "Read the ticket and respond with one short sentence describing the customer's main problem."
        ),
        input_text=ticket["ticket_text"],
    )

    print()
    print("Model analysis:")
    print(result.text)

    print()
    print("Request ID:", result.request_id)

    print()
    print("=" * 70)
    print("Ticket LLM test successful!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
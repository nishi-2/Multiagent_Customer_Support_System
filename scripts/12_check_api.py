import httpx


BASE_URL = "http://localhost:8000"


def main() -> None:
    print("=" * 70)
    print(
        "SupportCommander API Check"
    )
    print("=" * 70)

    health = httpx.get(
        f"{BASE_URL}/health",
        timeout=5,
    )

    health.raise_for_status()

    print("API health: OK")

    db_health = httpx.get(
        f"{BASE_URL}/health/db",
        timeout=5,
    )

    db_health.raise_for_status()

    print("MongoDB health: OK")

    ticket = httpx.get(
        f"{BASE_URL}/api/v1/tickets/1",
        timeout=5,
    )

    ticket.raise_for_status()

    ticket_data = ticket.json()

    assert (
        ticket_data["ticket_id"]
        == 1
    )

    print("Ticket lookup: OK")

    context = httpx.get(
        f"{BASE_URL}/api/v1/tickets/1/context",
        timeout=5,
    )

    context.raise_for_status()

    context_data = (
        context.json()
    )

    assert (
        context_data["ticket"][
            "ticket_id"
        ]
        == 1
    )

    assert (
        context_data["customer"]
        is not None
    )

    assert (
        context_data["order"]
        is not None
    )

    assert (
        context_data["payment"]
        is not None
    )

    print(
        "Support context: OK"
    )

    print()
    print("=" * 70)
    print(
        "FastAPI backend successful!"
    )
    print("=" * 70)


if __name__ == "__main__":
    main()
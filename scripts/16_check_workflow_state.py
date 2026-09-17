from supportcommander.graph.state_factory import create_initial_state
from supportcommander.services.ticket_service import get_ticket
from supportcommander.services.workflow_service import get_workflow_state, save_workflow_state


def main() -> None:
    print("=" * 70)
    print("SupportCommander Workflow State Check")
    print("=" * 70)

    ticket = get_ticket(1)

    if ticket is None:
        raise RuntimeError("Ticket 1 was not found.")

    state = create_initial_state(ticket_id=1, ticket=ticket)
    save_workflow_state(state)

    print("Workflow save: OK")

    workflow_id = state["workflow_id"]
    saved = get_workflow_state(workflow_id)

    if saved is None:
        raise RuntimeError("Workflow could not be read.")

    print("Workflow read: OK")

    if saved["ticket_id"]!= 1:
        raise RuntimeError("Saved ticket ID mismatch.")

    print("Workflow ticket link: OK")

    print()
    print("Workflow ID:", workflow_id)

    print()
    print("=" * 70)
    print("Workflow state persistence successful!")
    print("=" * 70)


if __name__ == "__main__":
    main()
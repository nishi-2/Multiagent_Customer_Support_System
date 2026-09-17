from pprint import pprint

from supportcommander.graph.models import (
    ProposedAction,
    ResolutionPlan,
    RiskAssessment,
    TriageResult,
)
from supportcommander.graph.state_factory import create_initial_state
from supportcommander.graph.state_utils import serialize_state
from supportcommander.services.ticket_service import get_ticket


def main() -> None:
    print("=" * 70)
    print("SupportCommander State Model Check")
    print("=" * 70)

    ticket = get_ticket(1)

    if ticket is None:
        raise RuntimeError("Ticket 1 not found.")

    state = create_initial_state(ticket_id=1, ticket=ticket)

    print("Initial state: OK")

    state["triage"] = (
        TriageResult(
            intent="technical_issue",
            urgency="critical",
            confidence=0.95,
            summary="Customer reports a product setup issue.",
            ),
        )

    print("Triage model: OK")

    state["risk_assessment"] = RiskAssessment(risk_level="low", confidence=0.90, suspicious_request=False, reasons=[])

    print("Risk model: OK")

    state["resolution_plan"] = ResolutionPlan(
        summary=("Provide troubleshooting guidance."),
        actions=[ProposedAction(action_type="provide_guidance", reason="No transaction is required.", requires_approval=False),],
        confidence=0.88,
    )

    print("Resolution model: OK")

    serialized = serialize_state(state)

    print("Serialization: OK")

    print()
    print("Sample workflow ID:")
    print(serialized["workflow_id"])

    print()
    print("Current stage:")
    print(serialized["current_stage"])

    print()
    print("Triage result:")
    pprint(serialized["triage"])

    print()
    print("=" * 70)
    print("State model check successful!")
    print("=" * 70)


if __name__ == "__main__":
    main()
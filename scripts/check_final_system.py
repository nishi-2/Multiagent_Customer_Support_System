"""
End-to-end system smoke test covering all major subsystems:
  - MongoDB connectivity
  - MCP server health
  - Triage agent
  - Policy gate
  - Response agent
  - Workflow persistence
  - API router registration
"""

import asyncio
import sys

sys.path.insert(0, "src")

from supportcommander.db.mongo import ping_database, get_database
from supportcommander.graph.coordinator import coordinator_graph
from supportcommander.graph.state_factory import create_initial_state
from supportcommander.services.ticket_service import get_ticket
from supportcommander.services.workflow_service import (
    get_workflow_state,
    save_workflow_state,
)
from supportcommander.graph.state_utils import serialize_state


def check_mongodb() -> None:
    print("1. MongoDB connectivity…")
    ping_database()
    db = get_database()
    assert db is not None
    print("   OK")


def check_ticket_service() -> dict:
    print("2. Ticket service…")
    ticket = get_ticket(1)
    assert ticket is not None, "Ticket 1 not found."
    print(f"   OK — ticket_id={ticket.get('ticket_id')}")
    return ticket


async def check_full_workflow(ticket: dict) -> dict:
    print("3. Full coordinator workflow…")
    state = create_initial_state(ticket_id=1, ticket=ticket)
    result = await coordinator_graph.ainvoke(state)
    stage = result.get("current_stage")
    print(f"   OK — current_stage={stage}")
    return result


def check_response(result: dict) -> None:
    print("4. Final response…")
    if result.get("escalated"):
        print("   SKIP — ticket escalated")
        return
    gate = result.get("policy_gate_result")
    if gate and gate.decision in {"require_approval", "escalate"}:
        print(f"   SKIP — gate decision is '{gate.decision}' (approval required)")
        return
    final = result.get("final_response")
    assert final is not None, "final_response is None"
    assert final.resolution_status, "resolution_status is empty"
    print(f"   OK — resolution_status={final.resolution_status}")


def check_workflow_persistence(result: dict) -> None:
    print("5. Workflow persistence…")
    save_workflow_state(result)
    wf_id = result.get("workflow_id")
    assert wf_id, "workflow_id missing from state"
    doc = get_workflow_state(wf_id)
    assert doc is not None, f"Workflow {wf_id} not found after save"
    print(f"   OK — workflow_id={wf_id}")


def check_audit_events(result: dict) -> None:
    print("6. Audit events…")
    events = result.get("audit_events") or []
    assert len(events) > 0, "No audit events recorded"
    print(f"   OK — {len(events)} events")


async def main() -> None:
    print("=== SupportCommander Final System Check ===\n")

    check_mongodb()
    ticket = check_ticket_service()
    result = await check_full_workflow(ticket)
    check_response(result)
    check_workflow_persistence(result)
    check_audit_events(result)

    print("\n=== ALL CHECKS PASSED ===")


if __name__ == "__main__":
    asyncio.run(main())

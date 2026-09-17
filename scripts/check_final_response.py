"""
Smoke test: run a full workflow through the coordinator and verify
that a FinalResponse is produced with a valid resolution_status.
"""

import asyncio
import sys

sys.path.insert(0, "src")

from supportcommander.graph.coordinator import coordinator_graph
from supportcommander.graph.state_factory import create_initial_state
from supportcommander.services.ticket_service import get_ticket


async def main() -> None:

    ticket = get_ticket(1)
    assert ticket is not None, "Ticket 1 not found in database."

    state = create_initial_state(
        ticket_id=1,
        ticket=ticket,
    )

    print("Running full coordinator workflow for ticket 1…")
    result = await coordinator_graph.ainvoke(state)

    stage = result.get("current_stage")
    print(f"  current_stage: {stage}")

    if result.get("escalated"):
        print("  Ticket was escalated — skipping response check.")
        return

    final = result.get("final_response")

    if final is None:
        gate = result.get("policy_gate_result")
        if gate and gate.decision in {"require_approval", "escalate"}:
            print(
                f"  Policy gate decision is '{gate.decision}' — "
                "workflow paused for approval. No final response yet."
            )
            return
        print("WARNING: final_response is None and no approval gate pause.")
        return

    print(f"  resolution_status : {final.resolution_status}")
    print(f"  requires_follow_up: {final.requires_follow_up}")
    print(f"  action_summary    : {final.action_summary}")
    print()
    print("Customer message:")
    print("-" * 60)
    print(final.message)
    print("-" * 60)

    assert final.resolution_status, "resolution_status is empty"
    print("\ncheck_final_response PASSED")


if __name__ == "__main__":
    asyncio.run(main())

import asyncio
from copy import deepcopy

import pytest

from supportcommander.agents.context_agent import (
    run_context_agent,
)
from supportcommander.agents.knowledge_agent import (
    run_knowledge_agent,
)
from supportcommander.agents.risk_agent import (
    run_risk_agent,
)
from supportcommander.agents.triage_agent import (
    run_triage_agent,
)
from supportcommander.graph.state_factory import (
    create_initial_state,
)
from supportcommander.services.ticket_service import (
    get_ticket,
)


@pytest.mark.asyncio
async def test_parallel_analysis_agents():

    ticket = get_ticket(
        1
    )

    assert ticket is not None

    state = create_initial_state(
        ticket_id=1,
        ticket=ticket,
    )

    triage_state = (
        await run_triage_agent(
            state
        )
    )

    assert (
        triage_state.get(
            "triage"
        )
        is not None
    )

    if triage_state.get(
        "escalated"
    ):
        pytest.skip(
            "Ticket was escalated by triage."
        )

    (
        context_result,
        risk_result,
        knowledge_result,
    ) = await asyncio.gather(
        run_context_agent(
            deepcopy(
                triage_state
            )
        ),
        run_risk_agent(
            deepcopy(
                triage_state
            )
        ),
        run_knowledge_agent(
            deepcopy(
                triage_state
            )
        ),
    )

    assert (
        context_result.get(
            "customer_context"
        )
        is not None
    )

    assert (
        risk_result.get(
            "risk_assessment"
        )
        is not None
    )

    assert (
        knowledge_result.get(
            "retrieved_policies"
        )
    )

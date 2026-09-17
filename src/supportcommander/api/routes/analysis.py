import asyncio
from copy import deepcopy

from fastapi import (
    APIRouter,
    HTTPException,
    status,
)

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
from supportcommander.graph.state_utils import (
    serialize_state,
)
from supportcommander.services.ticket_service import (
    get_ticket,
)


router = APIRouter(
    prefix="/api/v1/analysis",
    tags=["Analysis"],
)


@router.post(
    "/{ticket_id}"
)
async def analyze_ticket(
    ticket_id: int,
) -> dict:

    ticket = get_ticket(
        ticket_id
    )

    if ticket is None:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=(
                f"Ticket {ticket_id} "
                "was not found."
            ),
        )

    initial_state = (
        create_initial_state(
            ticket_id=ticket_id,
            ticket=ticket,
        )
    )

    triage_state = (
        await run_triage_agent(
            initial_state
        )
    )

    if triage_state.get(
        "escalated"
    ):
        return serialize_state(
            triage_state
        )

    context_state = deepcopy(
        triage_state
    )

    risk_state = deepcopy(
        triage_state
    )

    knowledge_state = deepcopy(
        triage_state
    )

    (
        context_result,
        risk_result,
        knowledge_result,
    ) = await asyncio.gather(
        run_context_agent(
            context_state
        ),
        run_risk_agent(
            risk_state
        ),
        run_knowledge_agent(
            knowledge_state
        ),
    )

    response = {
        "ticket_id":
            ticket_id,

        "triage":
            serialize_state(
                {
                    "triage":
                        triage_state[
                            "triage"
                        ]
                }
            )["triage"],

        "customer_context":
            serialize_state(
                {
                    "customer_context":
                        context_result[
                            "customer_context"
                        ]
                }
            )[
                "customer_context"
            ],

        "risk_assessment":
            serialize_state(
                {
                    "risk_assessment":
                        risk_result[
                            "risk_assessment"
                        ]
                }
            )[
                "risk_assessment"
            ],

        "retrieved_policies":
            serialize_state(
                {
                    "retrieved_policies":
                        knowledge_result[
                            "retrieved_policies"
                        ]
                }
            )[
                "retrieved_policies"
            ],
    }

    return response

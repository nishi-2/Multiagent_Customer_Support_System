from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from supportcommander.graph.nodes import (
    action_execution_node,
    approval_node,
    context_node,
    knowledge_node,
    policy_gate_node,
    resolution_planner_node,
    response_drafting_node,
    risk_node,
    startup_dispatch_node,
    startup_join_node,
    triage_node,
    verification_node,
)
from supportcommander.graph.routing import (
    route_after_policy_gate,
    route_after_startup,
)
from supportcommander.graph.state import (
    SupportGraphState,
)


builder = StateGraph(SupportGraphState)

builder.add_node("startup_dispatch", startup_dispatch_node)
builder.add_node("triage", triage_node)
builder.add_node("context", context_node)
builder.add_node("risk", risk_node)
builder.add_node("startup_join", startup_join_node)
builder.add_node("knowledge", knowledge_node)
builder.add_node("resolution_planning", resolution_planner_node)
builder.add_node("policy_gate", policy_gate_node)
builder.add_node("approval", approval_node)
builder.add_node("action_execution", action_execution_node)
builder.add_node("verification", verification_node)
builder.add_node("response_drafting", response_drafting_node)

# Phase 3: triage, context, and risk all start simultaneously
builder.add_edge(START, "startup_dispatch")
builder.add_edge("startup_dispatch", "triage")
builder.add_edge("startup_dispatch", "context")
builder.add_edge("startup_dispatch", "risk")

# All three converge at startup_join
builder.add_edge("triage", "startup_join")
builder.add_edge("context", "startup_join")
builder.add_edge("risk", "startup_join")

# Route: escalated (low-confidence triage) → END; otherwise → knowledge
builder.add_conditional_edges(
    "startup_join",
    route_after_startup,
    {
        "escalated": END,
        "continue": "knowledge",
    },
)

# knowledge has triage.intent available; retrieves policy DB + KB docs in parallel
builder.add_edge("knowledge", "resolution_planning")
builder.add_edge("resolution_planning", "policy_gate")

builder.add_conditional_edges(
    "policy_gate",
    route_after_policy_gate,
    {
        "approval": "approval",
        "action_execution": "action_execution",
        "response_drafting": "response_drafting",
    },
)

builder.add_edge("approval", END)
builder.add_edge("action_execution", "verification")
builder.add_edge("verification", "response_drafting")
builder.add_edge("response_drafting", END)

coordinator_graph = builder.compile()

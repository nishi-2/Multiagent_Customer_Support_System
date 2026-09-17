"""
Per-request LLM cost accumulation via contextvars.

Usage
-----
    acc = cost_tracker.start(workflow_id=..., ticket_id=..., user=...)
    # ... run the graph ...
    log = cost_tracker.finish(acc)           # returns the full dict
    cost_logger.save(log)                    # writes cost_logs/<user>_<ts>.json

generate_text() calls cost_tracker.register() automatically when a tracker
is active in the current async context.
"""
from __future__ import annotations

import contextvars
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from supportcommander.services.llm_models import LLMResult

# ── Pricing (USD per token) ───────────────────────────────────────────────────
# Source: https://openai.com/pricing  (as of 2025)
_PRICING: dict[str, dict[str, float]] = {
    "gpt-4o-mini":              {"input": 0.150 / 1_000_000, "output": 0.600 / 1_000_000},
    "gpt-4o-mini-2024-07-18":   {"input": 0.150 / 1_000_000, "output": 0.600 / 1_000_000},
    "gpt-4o":                   {"input": 2.50  / 1_000_000, "output": 10.00 / 1_000_000},
    "gpt-4o-2024-08-06":        {"input": 2.50  / 1_000_000, "output": 10.00 / 1_000_000},
    "gpt-4o-2024-05-13":        {"input": 5.00  / 1_000_000, "output": 15.00 / 1_000_000},
    "gpt-4-turbo":              {"input": 10.00 / 1_000_000, "output": 30.00 / 1_000_000},
    "gpt-4":                    {"input": 30.00 / 1_000_000, "output": 60.00 / 1_000_000},
    "gpt-3.5-turbo":            {"input": 0.50  / 1_000_000, "output": 1.50  / 1_000_000},
}
_FALLBACK_PRICING = {"input": 0.150 / 1_000_000, "output": 0.600 / 1_000_000}


def _price_for(model: str) -> dict[str, float]:
    """Return per-token pricing, falling back to gpt-4o-mini if model unknown."""
    if model in _PRICING:
        return _PRICING[model]
    # strip date suffix and retry  e.g. "gpt-4o-mini-2024-07-18" → "gpt-4o-mini"
    base = "-".join(model.split("-")[:3])
    return _PRICING.get(base, _FALLBACK_PRICING)


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class LLMCallRecord:
    agent: str
    called_at: str
    latency_ms: float
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    input_cost_usd: float
    output_cost_usd: float
    call_cost_usd: float


@dataclass
class CostAccumulator:
    workflow_id: str
    ticket_id: str | int
    user: str
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    _t0: float = field(default_factory=time.perf_counter, repr=False)
    calls: list[LLMCallRecord] = field(default_factory=list)

    def register(self, agent_name: str, result: "LLMResult") -> None:
        pricing = _price_for(result.model)
        in_cost  = result.input_tokens  * pricing["input"]
        out_cost = result.output_tokens * pricing["output"]
        self.calls.append(LLMCallRecord(
            agent         = agent_name,
            called_at     = datetime.now(timezone.utc).isoformat(),
            latency_ms    = round(result.latency_ms, 2),
            model         = result.model,
            input_tokens  = result.input_tokens,
            output_tokens = result.output_tokens,
            total_tokens  = result.input_tokens + result.output_tokens,
            input_cost_usd  = round(in_cost,  8),
            output_cost_usd = round(out_cost, 8),
            call_cost_usd   = round(in_cost + out_cost, 8),
        ))


# ── Context variable (one tracker per async context) ─────────────────────────

_current: contextvars.ContextVar[CostAccumulator | None] = \
    contextvars.ContextVar("cost_tracker", default=None)


def start(workflow_id: str, ticket_id: str | int, user: str = "unknown") -> CostAccumulator:
    acc = CostAccumulator(workflow_id=workflow_id, ticket_id=ticket_id, user=user)
    _current.set(acc)
    return acc


def register(agent_name: str, result: "LLMResult") -> None:
    acc = _current.get()
    if acc is not None:
        acc.register(agent_name, result)


def finish(acc: CostAccumulator) -> dict:
    """Compute totals and return the full cost log dict."""
    completed_at  = datetime.now(timezone.utc).isoformat()
    total_wall_ms = round((time.perf_counter() - acc._t0) * 1000, 2)

    total_input   = sum(c.input_tokens  for c in acc.calls)
    total_output  = sum(c.output_tokens for c in acc.calls)
    total_tokens  = total_input + total_output
    total_llm_ms  = round(sum(c.latency_ms for c in acc.calls), 2)
    total_cost    = round(sum(c.call_cost_usd for c in acc.calls), 8)

    # model breakdown  (in case multiple models used)
    models_used = sorted({c.model for c in acc.calls})

    return {
        "workflow_id":         acc.workflow_id,
        "ticket_id":           acc.ticket_id,
        "user":                acc.user,
        "started_at":          acc.started_at,
        "completed_at":        completed_at,
        "total_wall_ms":       total_wall_ms,
        "total_llm_latency_ms": total_llm_ms,
        "overhead_ms":         round(total_wall_ms - total_llm_ms, 2),
        "models_used":         models_used,
        "llm_calls_count":     len(acc.calls),
        "summary": {
            "total_input_tokens":  total_input,
            "total_output_tokens": total_output,
            "total_tokens":        total_tokens,
            "total_cost_usd":      total_cost,
        },
        "llm_calls": [
            {
                "agent":           c.agent,
                "called_at":       c.called_at,
                "model":           c.model,
                "latency_ms":      c.latency_ms,
                "input_tokens":    c.input_tokens,
                "output_tokens":   c.output_tokens,
                "total_tokens":    c.total_tokens,
                "input_cost_usd":  c.input_cost_usd,
                "output_cost_usd": c.output_cost_usd,
                "call_cost_usd":   c.call_cost_usd,
            }
            for c in acc.calls
        ],
    }

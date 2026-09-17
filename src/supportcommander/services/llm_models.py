from dataclasses import dataclass, field

@dataclass
class LLMResult:
    text: str
    model: str
    request_id: str | None
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0.0

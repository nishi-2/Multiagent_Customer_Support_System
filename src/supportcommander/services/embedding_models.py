from dataclasses import dataclass


@dataclass
class EmbeddingResult:
    embedding: list[float]
    model: str
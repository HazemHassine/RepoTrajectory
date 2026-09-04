from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ScoutAIEvaluation:
    clarity: float = 0.0  # 0-100
    usefulness: float = 0.0  # 0-100
    differentiation: float = 0.0  # 0-100
    execution_quality: float = 0.0  # 0-100
    overall_score: float = 0.0  # 0-100: weighted composite of AI dimensions
    why_it_surfaced: str = ""
    supporting_facts: list[str] = field(default_factory=list)
    uncertainty: str | None = None
    risk_flags: list[str] = field(default_factory=list)
    model_identity: str = ""
    prompt_version: str = "v1"

    @property
    def score_breakdown(self) -> dict[str, float]:
        return {
            "clarity": round(self.clarity, 2),
            "usefulness": round(self.usefulness, 2),
            "differentiation": round(self.differentiation, 2),
            "execution_quality": round(self.execution_quality, 2),
            "overall_ai_score": round(self.overall_score, 2),
        }


class AIServiceUnavailableError(RuntimeError):
    pass


class AIProvider(ABC):
    @abstractmethod
    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Compute vector embeddings for a list of input texts."""

    @abstractmethod
    async def evaluate_scout(self, candidate_data: dict[str, Any]) -> ScoutAIEvaluation:
        """Perform structured evaluation of a Scout candidate project."""

    @abstractmethod
    async def health(self) -> dict[str, Any]:
        """Return connectivity and capability status."""

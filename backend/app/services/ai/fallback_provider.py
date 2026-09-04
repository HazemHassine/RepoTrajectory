import hashlib
import math
from typing import Any

from app.services.ai.base import AIProvider, ScoutAIEvaluation


class FallbackAIProvider(AIProvider):
    """Deterministic, zero-dependency offline AI provider for tests, local development,

    and graceful degradation when hosted AI services are unavailable.
    """

    def __init__(self, dimension: int = 1536) -> None:
        self.dimension = dimension

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        results: list[list[float]] = []
        for text in texts:
            # Deterministic pseudo-vector seeded by text content
            normalized = text.strip().casefold()
            hasher = hashlib.sha256(normalized.encode("utf-8"))
            digest = hasher.digest()
            # Generate deterministic unit-normalized vector
            raw_vals: list[float] = []
            for i in range(self.dimension):
                b = digest[(i * 7) % len(digest)]
                val = ((b / 255.0) - 0.5) * 2.0
                raw_vals.append(val)
            norm = math.sqrt(sum(v * v for v in raw_vals)) or 1.0
            results.append([v / norm for v in raw_vals])
        return results

    async def evaluate_scout(self, candidate_data: dict[str, Any]) -> ScoutAIEvaluation:
        desc = str(candidate_data.get("description") or "").strip()
        topics = list(candidate_data.get("topics") or [])
        lang = str(candidate_data.get("primary_language") or "").strip()
        stars = int(candidate_data.get("stars") or 0)
        forks = int(candidate_data.get("forks") or 0)
        license_name = candidate_data.get("license")

        # Heuristic scoring
        # Clarity (0-100)
        clarity = 30.0
        if len(desc) >= 30:
            clarity += 40.0
        elif len(desc) > 10:
            clarity += 20.0
        if topics:
            clarity += min(30.0, len(topics) * 6.0)
        clarity = min(100.0, clarity)

        # Usefulness (0-100)
        usefulness = 40.0
        if lang:
            usefulness += 20.0
        if license_name:
            usefulness += 15.0
        if stars > 0:
            usefulness += min(25.0, math.log1p(stars) * 4.0)
        usefulness = min(100.0, usefulness)

        # Differentiation (0-100)
        diff = 50.0
        niche_topics = [t for t in topics if t not in {"tools", "development", "github"}]
        if niche_topics:
            diff += min(30.0, len(niche_topics) * 10.0)
        if desc and len(desc.split()) >= 8:
            diff += 10.0
        diff = min(100.0, diff)

        # Execution quality (0-100)
        exec_qual = 45.0
        if license_name:
            exec_qual += 25.0
        if forks > 0:
            exec_qual += min(20.0, forks * 5.0)
        if candidate_data.get("default_branch"):
            exec_qual += 10.0
        exec_qual = min(100.0, exec_qual)

        overall = round(
            0.25 * clarity + 0.35 * usefulness + 0.20 * diff + 0.20 * exec_qual, 1
        )

        why = (
            f"Surfaced based on strong code activity in {lang or 'open source'}"
            f" with {len(topics)} structured topics and focused scope."
        )

        facts = [
            f"Primary ecosystem: {lang or 'Multi-language'}",
            f"Documented with {len(topics)} topics: {', '.join(topics[:4]) if topics else 'None'}",
            f"Public engagement: {stars} stars, {forks} forks",
        ]
        if license_name:
            facts.append(f"Standard open source license: {license_name}")

        uncertainty = (
            "Early stage project with limited historical telemetry."
            if stars < 50
            else None
        )

        risk_flags = []
        if not license_name:
            risk_flags.append("Missing explicit open source license")
        if not desc:
            risk_flags.append("Sparse repository description")
        if stars < 5 and forks == 0:
            risk_flags.append("Low external peer review")

        return ScoutAIEvaluation(
            clarity=clarity,
            usefulness=usefulness,
            differentiation=diff,
            execution_quality=exec_qual,
            overall_score=overall,
            why_it_surfaced=why,
            supporting_facts=facts,
            uncertainty=uncertainty,
            risk_flags=risk_flags,
            model_identity="heuristic-fallback-v1",
            prompt_version="v1",
        )

    async def health(self) -> dict[str, Any]:
        return {
            "available": False,
            "status": "degraded",
            "provider": "fallback_heuristic",
            "detail": "Hosted AI credentials not configured; serving fallback scoring and search.",
        }

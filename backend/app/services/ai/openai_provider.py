import json
from typing import Any

import httpx
import structlog

from app.core.config import Settings, get_settings
from app.services.ai.base import (
    AIProvider,
    AIServiceUnavailableError,
    ScoutAIEvaluation,
)
from app.services.ai.fallback_provider import FallbackAIProvider

log = structlog.get_logger()


class OpenAIProvider(AIProvider):
    """OpenAI-compatible hosted AI provider for vector embeddings and structured Scout evaluation."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.base_url = self.settings.ai_base_url.rstrip("/")
        self.api_key = self.settings.ai_api_key
        self.embedding_model = self.settings.ai_embedding_model
        self.evaluation_model = self.settings.ai_evaluation_model
        self.fallback = FallbackAIProvider(dimension=self.settings.ai_embedding_dimension)

    def _client(self) -> httpx.AsyncClient:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return httpx.AsyncClient(base_url=self.base_url, headers=headers, timeout=25.0)

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not self.api_key:
            return await self.fallback.embed_texts(texts)
        if not texts:
            return []

        try:
            async with self._client() as client:
                response = await client.post(
                    "/embeddings",
                    json={"model": self.embedding_model, "input": texts},
                )
                if response.status_code != 200:
                    log.warning(
                        "openai_embedding_failed",
                        status=response.status_code,
                        text=response.text[:200],
                    )
                    return await self.fallback.embed_texts(texts)
                data = response.json()
                items = sorted(data.get("data", []), key=lambda x: x.get("index", 0))
                return [item["embedding"] for item in items]
        except Exception as exc:
            log.warning("openai_embedding_exception", error=str(exc))
            return await self.fallback.embed_texts(texts)

    async def evaluate_scout(self, candidate_data: dict[str, Any]) -> ScoutAIEvaluation:
        if not self.api_key:
            return await self.fallback.evaluate_scout(candidate_data)

        prompt = (
            "You are an expert Open Source Software Scout evaluating an early-stage or under-the-radar repository.\n"
            "Analyze the project evidence strictly using the provided facts. DO NOT manufacture or hallucinate repository facts.\n"
            "Repository Data:\n"
            f"- Full Name: {candidate_data.get('full_name')}\n"
            f"- Description: {candidate_data.get('description') or 'None provided'}\n"
            f"- Primary Language: {candidate_data.get('primary_language') or 'Unknown'}\n"
            f"- Topics: {', '.join(candidate_data.get('topics') or []) or 'None'}\n"
            f"- Stars: {candidate_data.get('stars', 0)}, Forks: {candidate_data.get('forks', 0)}, Open Issues: {candidate_data.get('open_issues', 0)}\n"
            f"- License: {candidate_data.get('license') or 'None'}\n"
            f"- Classification: {candidate_data.get('classification', 'software')}\n"
            f"- Last Pushed: {candidate_data.get('pushed_at') or 'Unknown'}\n\n"
            "Return a strictly valid JSON object with the following schema:\n"
            "{\n"
            '  "clarity": float (0 to 100, project problem statement and documentation clarity),\n'
            '  "usefulness": float (0 to 100, practical utility for software engineers),\n'
            '  "differentiation": float (0 to 100, novelty, unique approach, or niche strength),\n'
            '  "execution_quality": float (0 to 100, repository hygiene, structure, cadence),\n'
            '  "overall_score": float (0 to 100, holistic AI assessment),\n'
            '  "why_it_surfaced": string (1-2 sentences explaining why this repo is noteworthy),\n'
            '  "supporting_facts": list of strings (2-4 concrete bullet points derived only from provided data),\n'
            '  "uncertainty": string or null (explain any lack of data or early-stage risks),\n'
            '  "risk_flags": list of strings (e.g. "No license", "Single maintainer", "Low activity")\n'
            "}"
        )

        try:
            async with self._client() as client:
                response = await client.post(
                    "/chat/completions",
                    json={
                        "model": self.evaluation_model,
                        "messages": [
                            {"role": "system", "content": "You output JSON exclusively."},
                            {"role": "user", "content": prompt},
                        ],
                        "response_format": {"type": "json_object"},
                        "temperature": 0.2,
                    },
                )
                if response.status_code != 200:
                    log.warning(
                        "openai_eval_failed",
                        status=response.status_code,
                        text=response.text[:200],
                    )
                    return await self.fallback.evaluate_scout(candidate_data)

                payload = response.json()
                content = payload["choices"][0]["message"]["content"]
                parsed = json.loads(content)

                return ScoutAIEvaluation(
                    clarity=float(parsed.get("clarity", 50.0)),
                    usefulness=float(parsed.get("usefulness", 50.0)),
                    differentiation=float(parsed.get("differentiation", 50.0)),
                    execution_quality=float(parsed.get("execution_quality", 50.0)),
                    overall_score=float(parsed.get("overall_score", 50.0)),
                    why_it_surfaced=str(parsed.get("why_it_surfaced", "")),
                    supporting_facts=list(parsed.get("supporting_facts", [])),
                    uncertainty=parsed.get("uncertainty"),
                    risk_flags=list(parsed.get("risk_flags", [])),
                    model_identity=self.evaluation_model,
                    prompt_version="v1",
                )
        except Exception as exc:
            log.warning("openai_eval_exception", error=str(exc))
            return await self.fallback.evaluate_scout(candidate_data)

    async def health(self) -> dict[str, Any]:
        if not self.api_key:
            return {
                "available": False,
                "status": "degraded",
                "provider": "openai_compatible",
                "detail": "AI_API_KEY is not configured; using heuristic fallback.",
            }
        try:
            async with self._client() as client:
                response = await client.get("/models")
                if response.status_code < 400:
                    return {
                        "available": True,
                        "status": "healthy",
                        "provider": "openai_compatible",
                        "base_url": self.base_url,
                        "embedding_model": self.embedding_model,
                        "evaluation_model": self.evaluation_model,
                    }
                return {
                    "available": False,
                    "status": "degraded",
                    "provider": "openai_compatible",
                    "detail": f"Model endpoint returned {response.status_code}",
                }
        except Exception as exc:
            return {
                "available": False,
                "status": "degraded",
                "provider": "openai_compatible",
                "detail": f"Connection failed: {exc}",
            }

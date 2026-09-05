from app.core.config import Settings, get_settings
from app.services.ai.base import AIProvider, ScoutAIEvaluation
from app.services.ai.fallback_provider import FallbackAIProvider
from app.services.ai.openai_provider import OpenAIProvider


def get_ai_provider(settings: Settings | None = None) -> AIProvider:
    cfg = settings or get_settings()
    if cfg.ai_enabled and cfg.effective_ai_api_key:
        return OpenAIProvider(cfg)
    return FallbackAIProvider(dimension=cfg.ai_embedding_dimension)

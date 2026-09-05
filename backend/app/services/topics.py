"""Small extensible topic rules; membership is computed from collected metadata."""

from sqlalchemy import String, cast, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v2.product_schemas import TopicProject, TopicResponse
from app.db.models import CatalogRepository

TOPICS = [
    TopicResponse(slug=slug, name=name, description=description, terms=terms)
    for slug, name, description, terms in [
        (
            "agent-frameworks",
            "AI Agent Frameworks",
            "Build and coordinate software agents.",
            ["agent-framework", "multi-agent", "agentic"],
        ),
        (
            "rag",
            "RAG Infrastructure",
            "Retrieve context for language model applications.",
            ["retrieval-augmented", "rag-framework", "rag-pipeline"],
        ),
        (
            "evaluation",
            "AI Evaluation",
            "Test and evaluate model and application behavior.",
            ["llm-evaluation", "ai-evaluation", "evals"],
        ),
        (
            "observability",
            "AI Observability",
            "Inspect traces, costs and application behavior.",
            ["llm-observability", "llm-monitoring", "llm-tracing"],
        ),
        (
            "model-serving",
            "Model Serving / Inference",
            "Run models in your infrastructure.",
            ["model-serving", "inference-server", "llm-inference"],
        ),
        (
            "vector-search",
            "Vector & Search Infrastructure",
            "Index and retrieve useful information.",
            ["vector-database", "vector-search", "search-engine"],
        ),
        (
            "mcp-tooling",
            "MCP / Agent Tooling",
            "Connect development tools and agents.",
            ["model-context-protocol", "mcp-server", "mcp-client"],
        ),
        (
            "ai-infrastructure",
            "Developer AI Infrastructure",
            "Build and operate AI applications.",
            ["llm-framework", "llm-gateway", "ai-infrastructure"],
        ),
    ]
]

# Stable IDs may be explicitly curated without adding name-based evidence linkage.
INCLUDE: dict[str, set[int]] = {}
EXCLUDE: dict[str, set[int]] = {}


async def topic_projects(session: AsyncSession, topic: TopicResponse) -> list[TopicProject]:
    predicates = [
        or_(
            CatalogRepository.description.ilike(f"%{term.replace('-', ' ')}%"),
            cast(CatalogRepository.topics, String).ilike(f'%"{term}"%'),
        )
        for term in topic.terms
    ]
    stmt = (
        select(CatalogRepository)
        .where(
            CatalogRepository.archived.is_(False),
            CatalogRepository.is_fork.is_(False),
            or_(*predicates, CatalogRepository.github_id.in_(INCLUDE.get(topic.slug, set()))),
            CatalogRepository.github_id.not_in(EXCLUDE.get(topic.slug, set())),
        )
        .order_by(CatalogRepository.pushed_at.desc().nullslast())
        .limit(60)
    )
    rows = (await session.scalars(stmt)).all()
    return [
        TopicProject(
            github_id=repo.github_id,
            full_name=repo.full_name,
            description=repo.description,
            primary_language=repo.primary_language,
            pushed_at=repo.pushed_at,
            stars=repo.stars,
            matched_terms=[
                term
                for term in topic.terms
                if term in (repo.topics or [])
                or term.replace("-", " ") in (repo.description or "").casefold()
            ]
            or ["curated inclusion"],
        )
        for repo in rows
    ]

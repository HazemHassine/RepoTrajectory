"""Two-level software discovery taxonomy and precise catalog matching.

Supports parent categories and child subtopics across the software engineering landscape.
Repositories can match multiple topics; parent results represent the deduplicated union
of their children.
"""

import base64
import json
import time
from dataclasses import dataclass, field

from fastapi import HTTPException
from sqlalchemy import ColumnElement, String, and_, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v2.product_schemas import TopicProject, TopicResponse
from app.db.models import CatalogRepository


@dataclass(frozen=True)
class TopicDefinition:
    slug: str
    name: str
    description: str
    terms: list[str]  # GitHub topic tags / aliases
    phrases: list[str] = field(default_factory=list)  # Safe multi-word description phrases
    parent_slug: str | None = None


# Two-level software discovery taxonomy:
# 8 broad parents covering core engineering disciplines, with 36 focused children.
# All 8 legacy topic slugs are preserved as children under ai-machine-learning.
TAXONOMY: list[TopicDefinition] = [
    # 1. Web Development
    TopicDefinition(
        slug="web",
        name="Web",
        description="Frontend frameworks, fullstack frameworks, UI primitives, and web runtimes.",
        terms=["web", "frontend", "fullstack", "ui", "browser"],
        parent_slug=None,
    ),
    TopicDefinition(
        slug="frontend-frameworks",
        name="Frontend Frameworks",
        description="UI component libraries, reactive frameworks, and web view layers.",
        terms=[
            "react",
            "vue",
            "angular",
            "svelte",
            "solidjs",
            "frontend",
            "ui-framework",
            "web-framework",
            "preact",
            "lit",
        ],
        phrases=["frontend framework", "ui framework", "web framework", "reactive ui"],
        parent_slug="web",
    ),
    TopicDefinition(
        slug="fullstack-frameworks",
        name="Fullstack & SSR",
        description="Fullstack frameworks, server-side rendering, and static site generators.",
        terms=[
            "nextjs",
            "remix",
            "nuxt",
            "sveltekit",
            "astro",
            "gatsby",
            "fullstack",
            "ssr",
            "static-site-generator",
        ],
        phrases=["fullstack framework", "server side rendering", "static site generator"],
        parent_slug="web",
    ),
    TopicDefinition(
        slug="ui-components",
        name="UI & Design Systems",
        description="Component libraries, design systems, and styling utilities.",
        terms=[
            "tailwind",
            "tailwindcss",
            "radix-ui",
            "shadcn",
            "design-system",
            "component-library",
            "css-framework",
            "chakra-ui",
            "ant-design",
        ],
        phrases=["design system", "component library", "css framework", "ui components"],
        parent_slug="web",
    ),
    TopicDefinition(
        slug="state-management",
        name="State & Client Utilities",
        description="State management, web standards, and client-side runtimes.",
        terms=["state-management", "redux", "zustand", "webassembly", "wasm", "webrtc", "pwa"],
        phrases=["state management", "web assembly", "client state"],
        parent_slug="web",
    ),
    # 2. Backend & APIs
    TopicDefinition(
        slug="backend-apis",
        name="Backend & APIs",
        description="Server architectures, API gateways, microservices, and network protocols.",
        terms=["backend", "api", "rest-api", "microservices", "server"],
        parent_slug=None,
    ),
    TopicDefinition(
        slug="api-frameworks",
        name="API & Microframeworks",
        description="HTTP servers, RESTful microframeworks, and routing engines.",
        terms=[
            "fastapi",
            "express",
            "django",
            "flask",
            "spring-boot",
            "gin",
            "actix-web",
            "nestjs",
            "fiber",
            "rest-api",
            "microframework",
            "koa",
        ],
        phrases=["web framework", "api framework", "rest api", "http server", "microframework"],
        parent_slug="backend-apis",
    ),
    TopicDefinition(
        slug="rpc-graphql",
        name="RPC & GraphQL",
        description="Strongly typed RPC protocols, GraphQL engines, and schema toolkits.",
        terms=["graphql", "grpc", "protobuf", "trpc", "rpc", "openapi", "swagger"],
        phrases=["graphql server", "grpc service", "protocol buffers", "openapi spec"],
        parent_slug="backend-apis",
    ),
    TopicDefinition(
        slug="async-messaging",
        name="Message Queues & Streaming",
        description="Event streaming, pub/sub brokers, and asynchronous task queues.",
        terms=[
            "kafka",
            "rabbitmq",
            "celery",
            "event-driven",
            "pubsub",
            "nats",
            "message-queue",
            "zeromq",
            "event-streaming",
        ],
        phrases=["message queue", "event streaming", "task queue", "pub sub"],
        parent_slug="backend-apis",
    ),
    TopicDefinition(
        slug="api-gateways",
        name="API Gateways & Edge",
        description="Reverse proxies, rate limiters, authentication proxies, and edge routers.",
        terms=[
            "api-gateway",
            "reverse-proxy",
            "rate-limiting",
            "envoy",
            "traefik",
            "kong",
            "load-balancer",
        ],
        phrases=["api gateway", "reverse proxy", "rate limiting", "load balancer"],
        parent_slug="backend-apis",
    ),
    # 3. Data & Databases
    TopicDefinition(
        slug="data-databases",
        name="Data & Databases",
        description="Relational and NoSQL storage, analytics engines, and data pipelines.",
        terms=["database", "sql", "nosql", "data-engineering", "analytics"],
        parent_slug=None,
    ),
    TopicDefinition(
        slug="relational-databases",
        name="Relational Databases",
        description="SQL engines, storage managers, and relational databases.",
        terms=["postgresql", "postgres", "mysql", "sqlite", "sql", "rdbms", "database-engine"],
        phrases=["relational database", "sql database", "database engine", "storage engine"],
        parent_slug="data-databases",
    ),
    TopicDefinition(
        slug="nosql-cache",
        name="NoSQL & In-Memory",
        description="Document stores, key-value caches, and distributed in-memory datastores.",
        terms=[
            "redis",
            "mongodb",
            "cassandra",
            "scylladb",
            "key-value",
            "cache",
            "nosql",
            "in-memory",
        ],
        phrases=["nosql database", "key value store", "in memory cache", "document database"],
        parent_slug="data-databases",
    ),
    TopicDefinition(
        slug="data-pipelines",
        name="Data Pipelines & ETL",
        description="Data processing engines, workflow orchestrators, and stream computing.",
        terms=[
            "etl",
            "spark",
            "flink",
            "airflow",
            "data-engineering",
            "pipeline",
            "streaming-analytics",
        ],
        phrases=["data pipeline", "data processing", "workflow orchestrator", "stream processing"],
        parent_slug="data-databases",
    ),
    TopicDefinition(
        slug="database-tooling",
        name="ORMs & Database Tooling",
        description="Schema migrations, query builders, and database administration.",
        terms=[
            "orm",
            "prisma",
            "sqlalchemy",
            "migrations",
            "query-builder",
            "database-driver",
            "database-migration",
        ],
        phrases=["query builder", "database migrations", "database driver", "object relational"],
        parent_slug="data-databases",
    ),
    # 4. Infrastructure & DevOps
    TopicDefinition(
        slug="infrastructure-devops",
        name="Infrastructure & DevOps",
        description="Cloud deployment, container orchestration, CI/CD, and site reliability.",
        terms=["devops", "infrastructure", "cloud", "containers", "ci-cd"],
        parent_slug=None,
    ),
    TopicDefinition(
        slug="containers-orchestration",
        name="Containers & Orchestration",
        description="Container runtimes, clustering, and service orchestration.",
        terms=[
            "kubernetes",
            "k8s",
            "docker",
            "containers",
            "podman",
            "containerd",
            "helm",
            "orchestration",
        ],
        phrases=[
            "container orchestration",
            "docker container",
            "kubernetes cluster",
            "container runtime",
        ],
        parent_slug="infrastructure-devops",
    ),
    TopicDefinition(
        slug="infrastructure-as-code",
        name="Infrastructure as Code",
        description="Declarative provisioning, configuration management, and cloud architecture.",
        terms=[
            "terraform",
            "ansible",
            "opentofu",
            "pulumi",
            "iac",
            "cloudformation",
            "infrastructure-as-code",
        ],
        phrases=["infrastructure as code", "configuration management", "cloud provisioning"],
        parent_slug="infrastructure-devops",
    ),
    TopicDefinition(
        slug="ci-cd",
        name="CI/CD & Automation",
        description="Automated build systems, release automation, and workflow runners.",
        terms=[
            "ci-cd",
            "github-actions",
            "continuous-integration",
            "continuous-deployment",
            "automation-pipeline",
        ],
        phrases=[
            "continuous integration",
            "continuous deployment",
            "github actions",
            "build automation",
        ],
        parent_slug="infrastructure-devops",
    ),
    TopicDefinition(
        slug="service-networking",
        name="Service Mesh & Networking",
        description="Service discovery, DNS, SDN, and secure networking.",
        terms=["service-mesh", "networking", "dns", "wireguard", "proxy", "network-protocol"],
        phrases=["service mesh", "service discovery", "software defined networking"],
        parent_slug="infrastructure-devops",
    ),
    # 5. Developer Tools
    TopicDefinition(
        slug="developer-tools",
        name="Developer Tools",
        description="Build systems, compilers, CLIs, debuggers, and quality assurance.",
        terms=["developer-tools", "devtools", "cli", "compiler", "testing"],
        parent_slug=None,
    ),
    TopicDefinition(
        slug="cli-terminal",
        name="CLI & Terminal",
        description="Terminal user interfaces, command line runners, and shell environments.",
        terms=["cli", "command-line", "terminal", "tui", "shell-tool"],
        phrases=["command line tool", "terminal ui", "cli application", "shell utility"],
        parent_slug="developer-tools",
    ),
    TopicDefinition(
        slug="compilers-build",
        name="Compilers & Build Systems",
        description="Language compilers, static analyzers, linters, and bundlers.",
        terms=[
            "compiler",
            "bundler",
            "transpiler",
            "build-tool",
            "static-analysis",
            "linter",
            "formatter",
            "parser",
        ],
        phrases=["build system", "static analysis", "compiler infrastructure", "code formatter"],
        parent_slug="developer-tools",
    ),
    TopicDefinition(
        slug="testing-qa",
        name="Testing & QA",
        description="Unit testing, integration test suites, end-to-end runners, and mocking.",
        terms=[
            "testing",
            "test-framework",
            "unit-test",
            "e2e-testing",
            "jest",
            "pytest",
            "cypress",
            "playwright",
        ],
        phrases=["test framework", "testing library", "end to end testing", "unit testing"],
        parent_slug="developer-tools",
    ),
    TopicDefinition(
        slug="debugging-profiling",
        name="Debugging & Profiling",
        description="Performance profilers, runtime inspectors, and memory analyzers.",
        terms=[
            "debugger",
            "profiler",
            "profiling",
            "tracing",
            "benchmarking",
            "performance-profiler",
        ],
        phrases=["performance profiler", "memory profiling", "runtime debugging"],
        parent_slug="developer-tools",
    ),
    # 6. Security
    TopicDefinition(
        slug="security",
        name="Security",
        description="Application security, cryptography, vulnerability detection, and identity.",
        terms=["security", "cybersecurity", "auth", "cryptography", "appsec"],
        parent_slug=None,
    ),
    TopicDefinition(
        slug="auth-identity",
        name="Auth & Identity",
        description="OAuth, OpenID Connect, token authentication, and session management.",
        terms=[
            "authentication",
            "authorization",
            "oauth",
            "jwt",
            "identity",
            "sso",
            "auth-service",
        ],
        phrases=[
            "authentication library",
            "identity provider",
            "token authentication",
            "session management",
        ],
        parent_slug="security",
    ),
    TopicDefinition(
        slug="cryptography",
        name="Cryptography & Encryption",
        description="Cryptographic primitives, zero-knowledge proofs, and secure communications.",
        terms=["cryptography", "encryption", "crypto", "zero-knowledge", "zkp", "cryptographic"],
        phrases=[
            "cryptographic library",
            "zero knowledge",
            "public key encryption",
            "data encryption",
        ],
        parent_slug="security",
    ),
    TopicDefinition(
        slug="vulnerability-scanner",
        name="Vulnerability & AppSec",
        description="Static analysis for security, secrets scanning, and penetration testing.",
        terms=[
            "vulnerability-scanner",
            "secrets-detection",
            "appsec",
            "penetration-testing",
            "security-audit",
            "sast",
        ],
        phrases=[
            "vulnerability scanner",
            "security audit",
            "secret detection",
            "penetration testing",
        ],
        parent_slug="security",
    ),
    TopicDefinition(
        slug="network-security",
        name="Network & Perimeter",
        description="Packet inspection, intrusion detection, firewalls, and perimeter defense.",
        terms=["firewall", "intrusion-detection", "network-security", "waf", "packet-inspection"],
        phrases=[
            "network security",
            "packet inspection",
            "intrusion detection",
            "web application firewall",
        ],
        parent_slug="security",
    ),
    # 7. Mobile & Desktop
    TopicDefinition(
        slug="mobile-desktop",
        name="Mobile & Desktop",
        description="Cross-platform client apps, mobile operating systems, and desktop runtimes.",
        terms=["mobile", "desktop", "cross-platform", "ios", "android"],
        parent_slug=None,
    ),
    TopicDefinition(
        slug="cross-platform",
        name="Cross-Platform",
        description="Multi-target UI frameworks for mobile and desktop systems.",
        terms=["flutter", "react-native", "electron", "tauri", "cross-platform", "kmp"],
        phrases=["cross platform", "multi platform", "desktop and mobile"],
        parent_slug="mobile-desktop",
    ),
    TopicDefinition(
        slug="ios-development",
        name="iOS & Apple",
        description="Swift, Objective-C, and Apple ecosystem applications.",
        terms=["ios", "swift", "swiftui", "macos", "apple-platform"],
        phrases=["ios development", "swift library", "apple platforms"],
        parent_slug="mobile-desktop",
    ),
    TopicDefinition(
        slug="android-development",
        name="Android",
        description="Kotlin, Android SDK, Jetpack Compose, and mobile architecture.",
        terms=["android", "kotlin", "jetpack-compose", "android-development"],
        phrases=["android development", "jetpack compose", "android app"],
        parent_slug="mobile-desktop",
    ),
    TopicDefinition(
        slug="desktop-apps",
        name="Desktop Applications",
        description="Native desktop windowing, system integrations, and utilities.",
        terms=["desktop", "windows-app", "linux-desktop", "gtk", "qt", "desktop-app"],
        phrases=["desktop application", "native desktop", "window manager"],
        parent_slug="mobile-desktop",
    ),
    # 8. AI & Machine Learning
    # All 8 legacy slugs preserved as children!
    TopicDefinition(
        slug="ai-machine-learning",
        name="AI & Machine Learning",
        description="Artificial intelligence, foundation models, agents, and applied data science.",
        terms=["ai", "machine-learning", "deep-learning", "llm", "artificial-intelligence"],
        parent_slug=None,
    ),
    TopicDefinition(
        slug="agent-frameworks",
        name="AI Agent Frameworks",
        description="Build and coordinate software agents.",
        terms=[
            "agent-framework",
            "multi-agent",
            "agentic",
            "ai-agents",
            "ai-agent",
            "autonomous-agents",
            "llm-agent",
            "agent-frameworks",
        ],
        phrases=["agent framework", "multi agent", "autonomous agent", "ai agents"],
        parent_slug="ai-machine-learning",
    ),
    TopicDefinition(
        slug="rag",
        name="RAG Infrastructure",
        description="Retrieve context for language model applications.",
        terms=[
            "retrieval-augmented",
            "rag-framework",
            "rag-pipeline",
            "rag",
            "retrieval-augmented-generation",
            "rag-system",
        ],
        phrases=["retrieval augmented", "rag framework", "rag pipeline", "rag system"],
        parent_slug="ai-machine-learning",
    ),
    TopicDefinition(
        slug="evaluation",
        name="AI Evaluation",
        description="Test and evaluate model and application behavior.",
        terms=["llm-evaluation", "ai-evaluation", "evals", "model-evaluation", "llm-benchmark"],
        phrases=["llm evaluation", "ai evaluation", "model evaluation"],
        parent_slug="ai-machine-learning",
    ),
    TopicDefinition(
        slug="observability",
        name="AI Observability",
        description="Inspect traces, costs and application behavior.",
        terms=["llm-observability", "llm-monitoring", "llm-tracing", "observability", "tracing-ai"],
        phrases=["llm observability", "llm monitoring", "llm tracing"],
        parent_slug="ai-machine-learning",
    ),
    TopicDefinition(
        slug="model-serving",
        name="Model Serving / Inference",
        description="Run models in your infrastructure.",
        terms=[
            "model-serving",
            "inference-server",
            "llm-inference",
            "inference",
            "vllm",
            "ollama",
            "llm-serving",
        ],
        phrases=["model serving", "inference server", "llm inference"],
        parent_slug="ai-machine-learning",
    ),
    TopicDefinition(
        slug="vector-search",
        name="Vector & Search Infrastructure",
        description="Index and retrieve useful information.",
        terms=[
            "vector-database",
            "vector-search",
            "search-engine",
            "vectordb",
            "embeddings",
            "similarity-search",
        ],
        phrases=["vector database", "vector search", "search engine", "similarity search"],
        parent_slug="ai-machine-learning",
    ),
    TopicDefinition(
        slug="mcp-tooling",
        name="MCP / Agent Tooling",
        description="Connect development tools and agents.",
        terms=["model-context-protocol", "mcp-server", "mcp-client", "mcp"],
        phrases=["model context protocol", "mcp server", "mcp client"],
        parent_slug="ai-machine-learning",
    ),
    TopicDefinition(
        slug="ai-infrastructure",
        name="Developer AI Infrastructure",
        description="Build and operate AI applications.",
        terms=[
            "llm-framework",
            "llm-gateway",
            "ai-infrastructure",
            "llm",
            "foundation-models",
            "generative-ai",
        ],
        phrases=["llm framework", "llm gateway", "ai infrastructure"],
        parent_slug="ai-machine-learning",
    ),
]

# Map for instant slug lookups
TAXONOMY_MAP: dict[str, TopicDefinition] = {topic.slug: topic for topic in TAXONOMY}

# Map of parent slug -> list of child definitions
PARENT_CHILDREN_MAP: dict[str, list[TopicDefinition]] = {}
for _topic in TAXONOMY:
    if _topic.parent_slug:
        PARENT_CHILDREN_MAP.setdefault(_topic.parent_slug, []).append(_topic)

# Maintain backwards-compatible TOPICS list of TopicResponse instances
TOPICS: list[TopicResponse] = [
    TopicResponse(
        slug=t.slug,
        name=t.name,
        description=t.description,
        terms=t.terms,
        parent_slug=t.parent_slug,
        repository_count=0,
    )
    for t in TAXONOMY
]

# Stable IDs curated without adding name-based evidence linkage
INCLUDE: dict[str, set[int]] = {}
EXCLUDE: dict[str, set[int]] = {}


def get_topic_definition(slug: str) -> TopicDefinition | None:
    return TAXONOMY_MAP.get(slug)


def get_topic_children(parent_slug: str) -> list[TopicDefinition]:
    return PARENT_CHILDREN_MAP.get(parent_slug, [])


def build_single_topic_predicate(topic: TopicDefinition) -> ColumnElement[bool]:
    """Build a SQL predicate for a single child topic with exact tag and safe phrase matching."""
    tag_predicates = [
        cast(CatalogRepository.topics, String).ilike(f'%"{term}"%') for term in topic.terms
    ]
    phrase_predicates = [
        CatalogRepository.description.ilike(f"%{phrase}%") for phrase in topic.phrases
    ]
    all_predicates = tag_predicates + phrase_predicates
    include_ids = INCLUDE.get(topic.slug, set())
    if include_ids:
        all_predicates.append(CatalogRepository.github_id.in_(include_ids))

    base_pred = or_(*all_predicates) if all_predicates else or_()
    exclude_ids = EXCLUDE.get(topic.slug, set())
    if exclude_ids:
        return and_(base_pred, CatalogRepository.github_id.not_in(exclude_ids))
    return base_pred


def build_topic_predicate(topic: TopicDefinition) -> ColumnElement[bool]:
    """Build the SQL predicate for a topic.

    For parent topics, this is the deduplicated union (OR) of all child subtopic predicates.
    For child topics, this is the single topic matching predicate.
    """
    children = get_topic_children(topic.slug)
    if children:
        child_preds = [build_single_topic_predicate(child) for child in children]
        exclude_ids = EXCLUDE.get(topic.slug, set())
        combined = or_(*child_preds)
        if exclude_ids:
            return and_(combined, CatalogRepository.github_id.not_in(exclude_ids))
        return combined
    return build_single_topic_predicate(topic)


def extract_matched_terms(repo: CatalogRepository, topic: TopicDefinition) -> list[str]:
    """Extract which terms or phrases from the topic definition matched this repository."""
    matched: list[str] = []
    repo_topics = {str(t).strip().casefold() for t in (repo.topics or []) if str(t).strip()}
    desc_lower = (repo.description or "").casefold()

    # If it is a parent topic, collect matched terms across its children
    children = get_topic_children(topic.slug)
    relevant_terms = list(topic.terms)
    relevant_phrases = list(topic.phrases)
    if children:
        for child in children:
            relevant_terms.extend(child.terms)
            relevant_phrases.extend(child.phrases)

    for term in relevant_terms:
        term_clean = term.strip().casefold()
        if term_clean in repo_topics:
            if term not in matched:
                matched.append(term)
        elif " " in term_clean and term_clean in desc_lower:
            if term not in matched:
                matched.append(term)

    for phrase in relevant_phrases:
        phrase_clean = phrase.strip().casefold()
        if phrase_clean in desc_lower and phrase not in matched:
            matched.append(phrase)

    if not matched and repo.github_id in INCLUDE.get(topic.slug, set()):
        return ["curated inclusion"]

    return matched or (topic.terms[:1] if topic.terms else ["software"])


# In-memory cache for topic counts across the taxonomy
_CACHE_EXPIRY_SECONDS = 300.0
_cached_counts: dict[str, int] = {}
_cache_updated_at: float = 0.0


def clear_topic_cache() -> None:
    """Clear in-memory topic counts cache (useful in tests and updates)."""
    global _cached_counts, _cache_updated_at
    _cached_counts = {}
    _cache_updated_at = 0.0


async def get_cached_topic_counts(session: AsyncSession) -> dict[str, int]:
    """Get topic repository counts, refreshing the in-memory cache every 300s."""
    global _cached_counts, _cache_updated_at
    now = time.monotonic()
    if _cached_counts and (now - _cache_updated_at) < _CACHE_EXPIRY_SECONDS:
        return _cached_counts

    counts: dict[str, int] = {}
    for topic_def in TAXONOMY:
        pred = build_topic_predicate(topic_def)
        stmt = select(func.count(CatalogRepository.github_id)).where(
            CatalogRepository.archived.is_(False),
            CatalogRepository.is_fork.is_(False),
            pred,
        )
        count = int(await session.scalar(stmt) or 0)
        counts[topic_def.slug] = count

    _cached_counts = counts
    _cache_updated_at = now
    return _cached_counts


async def get_all_topics(session: AsyncSession) -> list[TopicResponse]:
    """Return all taxonomy topics with accurate repository counts."""
    counts = await get_cached_topic_counts(session)
    return [
        TopicResponse(
            slug=t.slug,
            name=t.name,
            description=t.description,
            terms=t.terms,
            parent_slug=t.parent_slug,
            repository_count=counts.get(t.slug, 0),
        )
        for t in TAXONOMY
    ]


def encode_cursor(
    slug: str,
    q: str | None,
    language: str | None,
    sort: str,
    offset: int,
) -> str:
    """Encode an opaque, tamper-evident pagination cursor bound to query context."""
    payload = {
        "slug": slug,
        "q": q or "",
        "lang": language or "",
        "sort": sort,
        "offset": offset,
    }
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("utf-8")


def decode_cursor(
    cursor: str | None,
    expected_slug: str,
    expected_q: str | None,
    expected_language: str | None,
    expected_sort: str,
) -> int:
    """Decode and strictly validate a pagination cursor against the current query context."""
    if not cursor:
        return 0
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("utf-8"))
        data = json.loads(raw.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid cursor format") from None
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Invalid cursor payload")

    if (
        data.get("slug") != expected_slug
        or data.get("q") != (expected_q or "")
        or data.get("lang") != (expected_language or "")
        or data.get("sort") != expected_sort
    ):
        raise HTTPException(status_code=400, detail="Cursor context does not match request filters")

    offset = data.get("offset")
    if not isinstance(offset, int) or offset < 0:
        raise HTTPException(status_code=400, detail="Invalid cursor offset")
    return offset


async def topic_projects(
    session: AsyncSession,
    topic: TopicResponse | TopicDefinition,
) -> list[TopicProject]:
    """Compatibility helper for existing callers expecting projects for a topic."""
    slug = topic.slug
    topic_def = get_topic_definition(slug)
    if not topic_def:
        return []

    pred = build_topic_predicate(topic_def)
    stmt = (
        select(CatalogRepository)
        .where(
            CatalogRepository.archived.is_(False),
            CatalogRepository.is_fork.is_(False),
            pred,
        )
        .order_by(
            CatalogRepository.selection_score.desc(),
            CatalogRepository.stars.desc(),
            CatalogRepository.github_id.asc(),
        )
        .limit(60)
    )
    rows = (await session.scalars(stmt)).all()
    return [
        TopicProject(
            github_id=repo.github_id,
            full_name=repo.full_name,
            description=repo.description,
            primary_language=repo.primary_language,
            matched_terms=extract_matched_terms(repo, topic_def),
            pushed_at=repo.pushed_at,
            stars=repo.stars,
        )
        for repo in rows
    ]

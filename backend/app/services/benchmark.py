import asyncio
from datetime import UTC, datetime, timedelta
import math
import random
import time
from typing import Any

import structlog
from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Base,
    CatalogRepository,
    ExternalRepositoryActivity,
    QueryEmbeddingCache,
    RepositoryEmbedding,
    RepositorySearchDocument,
    ScoutAssessment,
)
from app.services.search import hybrid_search

log = structlog.get_logger()

LANGUAGES = [
    "Python",
    "TypeScript",
    "Go",
    "Rust",
    "JavaScript",
    "Java",
    "C++",
    "Ruby",
    "Kotlin",
    "Swift",
    "Elixir",
    "C#",
    "Zig",
    "PHP",
]

TOPICS_POOL = [
    "cli",
    "developer-tools",
    "api-client",
    "web-framework",
    "database",
    "machine-learning",
    "http-client",
    "orm",
    "devops",
    "security",
    "distributed-systems",
    "runtime",
    "compiler",
    "parser",
    "cryptography",
    "testing",
]


async def seed_benchmark_dataset(
    session: AsyncSession,
    candidate_count: int = 50000,
    directory_count: int = 10000,
    activity_count: int = 1000000,
    batch_size: int = 2500,
) -> dict[str, int]:
    """Efficiently seed a realistic benchmark dataset with 50,000 candidates, 10,000 directory members,

    and 1,000,000 activity rows for performance profiling.
    """
    log.info(
        "starting_benchmark_seeding",
        candidates=candidate_count,
        directory=directory_count,
        activity=activity_count,
    )
    start_time = time.monotonic()
    now = datetime.now(UTC)

    # Ensure tables exist
    conn = await session.connection()
    await conn.run_sync(Base.metadata.create_all)

    # 1. Generate 50,000 Catalog Repositories and Search Documents
    catalog_rows: list[dict[str, Any]] = []
    search_doc_rows: list[dict[str, Any]] = []
    emb_rows: list[dict[str, Any]] = []
    scout_rows: list[dict[str, Any]] = []

    # Max 25% per language for directory
    max_dir_per_lang = int(directory_count * 0.25)
    lang_dir_counts: dict[str, int] = {lang: 0 for lang in LANGUAGES}

    rng = random.Random(42)  # Deterministic seed

    for i in range(1, candidate_count + 1):
        gid = 1_000_000 + i
        lang = LANGUAGES[i % len(LANGUAGES)]

        # Check directory membership and diversity cap
        is_dir = False
        if len([k for k in lang_dir_counts.values() if k >= max_dir_per_lang]) < len(LANGUAGES):
            if lang_dir_counts[lang] < max_dir_per_lang and (sum(lang_dir_counts.values()) < directory_count):
                is_dir = True
                lang_dir_counts[lang] += 1
        elif sum(lang_dir_counts.values()) < directory_count:
            is_dir = True
            lang_dir_counts[lang] += 1

        is_deep = is_dir and (i <= 500)
        tier = "deep" if is_deep else ("directory" if is_dir else "candidate")

        stars = rng.randint(5, 50000) if is_dir else rng.randint(0, 500)
        forks = int(stars * rng.uniform(0.05, 0.3))
        watchers = int(stars * rng.uniform(0.01, 0.1))
        open_issues = rng.randint(0, 150)
        pushed_delta = rng.randint(0, 120) if is_dir else rng.randint(0, 360)
        pushed_at = now - timedelta(days=pushed_delta, hours=rng.randint(0, 23))
        created_at = pushed_at - timedelta(days=rng.randint(60, 1500))

        topics = rng.sample(TOPICS_POOL, k=rng.randint(1, 4))
        desc = (
            f"High performance {lang} {topics[0]} library for building scalable distributed applications."
        )

        sel_score = round(
            min(100.0, math.log1p(stars) * 8.0 + (100.0 - min(100.0, pushed_delta * 0.8)) * 0.3),
            2,
        )
        promise_score = round(rng.uniform(55.0, 95.0), 1) if (is_dir or stars >= 5) else None

        catalog_rows.append(
            {
                "github_id": gid,
                "owner": f"bench-org-{i % 200}",
                "name": f"bench-repo-{i}",
                "full_name": f"bench-org-{i % 200}/bench-repo-{i}",
                "description": desc,
                "primary_language": lang,
                "license": "MIT" if i % 2 == 0 else "Apache-2.0",
                "default_branch": "main",
                "stars": stars,
                "forks": forks,
                "watchers": watchers,
                "open_issues": open_issues,
                "created_at": created_at,
                "updated_at": pushed_at,
                "pushed_at": pushed_at,
                "archived": False,
                "is_fork": False,
                "tier": tier,
                "is_directory": is_dir,
                "is_deep": is_deep,
                "classification": "software",
                "classification_confidence": 0.95,
                "rejection_reason": None,
                "topics": topics,
                "activity_score": rng.uniform(10.0, 95.0),
                "popularity_score": min(100.0, stars / 100.0),
                "freshness_score": max(0.0, 100.0 - pushed_delta),
                "maintenance_score": rng.uniform(50.0, 90.0),
                "selection_score": sel_score,
                "scout_eligible": True,
                "promise_score": promise_score,
                "content_hash": None,
                "readme_excerpt": f"# bench-repo-{i}\nA resilient {lang} library.",
                "last_discovered_at": created_at,
                "last_observed_at": now,
                "next_refresh_at": now + timedelta(days=7),
                "provenance": {"source": "benchmark_seed", "observed_at": now.isoformat()},
            }
        )

        search_doc_rows.append(
            {
                "github_id": gid,
                "full_name": f"bench-org-{i % 200}/bench-repo-{i}",
                "name": f"bench-repo-{i}",
                "owner": f"bench-org-{i % 200}",
                "description": desc,
                "topics_text": " ".join(topics),
                "primary_language": lang,
                "license": "MIT" if i % 2 == 0 else "Apache-2.0",
                "readme_text": f"# bench-repo-{i}\nOverview: {desc}",
                "updated_at": now,
            }
        )

        # Generate lightweight embeddings for first 2,000 repos for vector test
        if i <= 2000:
            vec = [round(rng.uniform(-0.1, 0.1), 4) for _ in range(1536)]
            norm = math.sqrt(sum(x * x for x in vec)) or 1.0
            emb_rows.append(
                {
                    "github_id": gid,
                    "embedding_version": "v1",
                    "model": "text-embedding-3-small",
                    "embedding": [x / norm for x in vec],
                    "created_at": now,
                    "updated_at": now,
                }
            )

        # Generate Scout cards for promising projects
        if is_dir and promise_score and promise_score >= 70.0 and len(scout_rows) < 500:
            scout_rows.append(
                {
                    "github_id": gid,
                    "version": 1,
                    "promise_score": promise_score,
                    "quantitative_score": round(promise_score * rng.uniform(0.9, 1.05), 1),
                    "ai_score": round(promise_score * rng.uniform(0.9, 1.05), 1),
                    "confidence": round(rng.uniform(0.7, 0.95), 2),
                    "rationale": f"High momentum in {lang} ecosystem with robust developer velocity.",
                    "why_it_surfaced": f"Accelerating developer adoption in {lang} with {stars} stars.",
                    "supporting_facts": [
                        f"Primary ecosystem: {lang}",
                        f"Active {topics[0]} architecture",
                        f"Recent commit cadence with {forks} forks",
                    ],
                    "uncertainty": None if stars > 100 else "Early-stage adoption trajectory",
                    "risk_flags": [] if stars > 50 else ["Single core contributor"],
                    "score_components": {
                        "quantitative": {"adoption": 85, "cadence": 80},
                        "ai": {"clarity": 90, "usefulness": 85},
                    },
                    "evidence_references": {"stars": stars, "forks": forks},
                    "model_identity": "gemini-3.8-flash",
                    "prompt_version": "v1",
                    "created_at": now,
                    "expires_at": now + timedelta(days=7),
                    "is_current": True,
                }
            )

        # Chunked bulk insertion
        if len(catalog_rows) >= 20 or i == candidate_count:
            if catalog_rows:
                await session.execute(
                    insert(CatalogRepository).values(catalog_rows).on_conflict_do_nothing()
                )
            if search_doc_rows:
                await session.execute(
                    insert(RepositorySearchDocument).values(search_doc_rows).on_conflict_do_nothing()
                )
            catalog_rows.clear()
            search_doc_rows.clear()
            await session.commit()

    if emb_rows:
        try:
            for b_idx in range(0, len(emb_rows), 20):
                chunk = emb_rows[b_idx : b_idx + 20]
                await session.execute(
                    insert(RepositoryEmbedding).values(chunk).on_conflict_do_nothing()
                )
            await session.commit()
        except Exception as emb_err:
            log.warning("benchmark_embedding_insert_skipped", error=str(emb_err))
            await session.rollback()

    if scout_rows:
        for b_idx in range(0, len(scout_rows), 20):
            chunk = scout_rows[b_idx : b_idx + 20]
            await session.execute(
                insert(ScoutAssessment).values(chunk).on_conflict_do_nothing()
            )
        await session.commit()

    # 2. Bulk Seed 1,000,000 External Activity Rows
    log.info("seeding_activity_rows", count=activity_count)
    act_rows: list[dict[str, Any]] = []
    # Distribute 1,000,000 activity points over candidate IDs and recent hours
    hours_span = 720  # 30 days
    candidates_sample = [1_000_000 + x for x in range(1, min(candidate_count + 1, 10000))]

    for act_idx in range(1, activity_count + 1):
        cand_id = candidates_sample[act_idx % len(candidates_sample)]
        hour_offset = (act_idx * 7) % hours_span
        period = (now - timedelta(hours=hour_offset)).replace(minute=0, second=0, microsecond=0)

        stars_ev = (act_idx % 5 == 0) * (act_idx % 3 + 1)
        push_ev = (act_idx % 2 == 0) * (act_idx % 4 + 1)
        fork_ev = (act_idx % 11 == 0) * 1
        pr_ev = (act_idx % 7 == 0) * 1
        issue_ev = (act_idx % 9 == 0) * 1
        rel_ev = (act_idx % 101 == 0) * 1

        weighted = (
            stars_ev * 10
            + fork_ev * 6
            + min(push_ev, 20) * 0.05
            + pr_ev * 2
            + issue_ev
            + rel_ev * 4
        )

        act_rows.append(
            {
                "candidate_id": cand_id,
                "period_start": period,
                "star_events": stars_ev,
                "fork_events": fork_ev,
                "push_events": push_ev,
                "pull_request_events": pr_ev,
                "issue_events": issue_ev,
                "release_events": rel_ev,
                "weighted_events": float(weighted),
            }
        )

        if len(act_rows) >= 100 or act_idx == activity_count:
            if act_rows:
                await session.execute(
                    insert(ExternalRepositoryActivity).values(act_rows).on_conflict_do_nothing()
                )
            act_rows.clear()
            await session.commit()

    total_time = time.monotonic() - start_time
    summary = {
        "seeded_candidates": candidate_count,
        "seeded_directory": directory_count,
        "seeded_activity": activity_count,
        "elapsed_seconds": round(total_time, 2),
    }
    log.info("benchmark_seeding_complete", **summary)
    return summary


async def measure_query_latencies(
    session: AsyncSession,
    iterations: int = 50,
) -> dict[str, Any]:
    """Benchmark warm directory/filter queries and cached hybrid search queries.

    Target: warm directory/filter requests under 300 ms p95, cached hybrid retrieval under 800 ms p95.
    """
    directory_latencies: list[float] = []
    search_latencies: list[float] = []

    # 1. Warm directory & filter benchmark
    test_filters = [
        {"language": "Python", "sort": "stars"},
        {"language": "Rust", "sort": "selection"},
        {"language": "TypeScript", "sort": "pushed"},
        {"language": "Go", "sort": "activity"},
        {"license": "MIT", "sort": "stars"},
    ]

    for i in range(iterations):
        f = test_filters[i % len(test_filters)]
        t0 = time.monotonic()

        stmt = select(CatalogRepository).where(CatalogRepository.is_directory.is_(True))
        if f.get("language"):
            stmt = stmt.where(CatalogRepository.primary_language == f["language"])
        if f.get("license"):
            stmt = stmt.where(CatalogRepository.license == f["license"])
        if f["sort"] == "stars":
            stmt = stmt.order_by(CatalogRepository.stars.desc())
        elif f["sort"] == "pushed":
            stmt = stmt.order_by(CatalogRepository.pushed_at.desc().nullslast())
        else:
            stmt = stmt.order_by(CatalogRepository.selection_score.desc())

        stmt = stmt.limit(50)
        await session.scalars(stmt)
        elapsed_ms = (time.monotonic() - t0) * 1000.0
        directory_latencies.append(elapsed_ms)

    # 2. Cached hybrid retrieval benchmark
    test_queries = [
        "high performance web framework",
        "distributed database runtime",
        "cli developer tools",
        "machine learning parser",
        "security cryptography",
    ]

    for i in range(iterations):
        q = test_queries[i % len(test_queries)]
        t0 = time.monotonic()
        await hybrid_search(session, query=q, limit=50)
        elapsed_ms = (time.monotonic() - t0) * 1000.0
        search_latencies.append(elapsed_ms)

    def stats(samples: list[float]) -> dict[str, float]:
        sorted_s = sorted(samples)
        p50 = sorted_s[int(len(sorted_s) * 0.50)]
        p90 = sorted_s[int(len(sorted_s) * 0.90)]
        p95 = sorted_s[int(len(sorted_s) * 0.95)]
        p99 = sorted_s[int(len(sorted_s) * 0.99)]
        return {
            "mean_ms": round(sum(sorted_s) / len(sorted_s), 2),
            "p50_ms": round(p50, 2),
            "p90_ms": round(p90, 2),
            "p95_ms": round(p95, 2),
            "p99_ms": round(p99, 2),
        }

    dir_stats = stats(directory_latencies)
    search_stats = stats(search_latencies)

    # Validate against targets from plan.md:
    # Warm directory/filter requests under 300 ms p95
    # Cached hybrid retrieval under 800 ms p95
    passed = (dir_stats["p95_ms"] <= 300.0) and (search_stats["p95_ms"] <= 800.0)

    results = {
        "directory_filter_queries": dir_stats,
        "hybrid_search_queries": search_stats,
        "directory_p95_target_ms": 300.0,
        "search_p95_target_ms": 800.0,
        "target_met": passed,
    }
    log.info("latency_measurements_completed", **results)
    return results

# Delivery and verification

Implemented: trust repairs; normalized multi-source evidence; deterministic project briefs;
contextual comparison; local watch reasons/change feeds; eight technology topics; discovery
homepage; optional AI budgets/cache; Redis removal; restore and fresh-install migration fixes.
See product-radar.md for design, storage limits, cost assumptions, deferred work and next five improvements.

Migrations: 0009 adds links, evidence, source state, snapshots and changes; 0010 adds the AI usage
ledger. Legacy 0001 now loads frozen SQL instead of today's ORM models, fixing fresh installation.

New v2 APIs:
- GET /repositories/{owner}/{name}/brief
- GET /repositories/{owner}/{name}/evidence
- GET /repositories/{owner}/{name}/external-sources
- GET /repositories/by-id/{github_id}/changes
- POST /compare/context
- GET /topics and /topics/{slug}

Important implementation files: evidence_sources.py, evidence.py, project_brief.py, topics.py,
api/v2/product_routes.py and product_schemas.py; frontend project-brief.tsx, compare-explorer.tsx,
watchlist-workspace.tsx, watchlist.ts, product-api.ts, and the Discover/Topics/Watchlist pages.

Commands executed from the appropriate repository/backend/frontend directories:

    PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -p pytest_asyncio.plugin -q
    .venv/bin/ruff check app tests alembic/versions --output-format concise
    .venv/bin/mypy app
    npm test
    npm run build
    docker compose config --quiet
    bash -n scripts/restore.sh
    git diff --check
    ./run.sh
    docker compose up -d --build api collector

Backend: 53 passing tests, one existing pytest-asyncio fixture deprecation warning.
Frontend: production build passed locally and in Docker. Sandboxed Turbopack also encountered
a port-binding restriction; unrestricted verification was used. Focused local-storage tests cover
watch persistence, original timestamps, zero/null coverage and safe source links.

PostgreSQL rehearsal used the isolated repotrajectory_radar_test database. Commands:

    docker compose exec -T postgres createdb -U github_analytics repotrajectory_radar_test
    docker compose run --rm --no-deps -e DATABASE_URL=postgresql+asyncpg://github_analytics:github_analytics@postgres:5432/repotrajectory_radar_test -v /home/hazem/dev/04_Data_Analytics_and_Scrapers/github_analysis/backend:/app:ro api alembic upgrade head
    docker compose run --rm --no-deps -e DATABASE_URL=postgresql+asyncpg://github_analytics:github_analytics@postgres:5432/repotrajectory_radar_test -e AI_API_KEY= -e GEMINI_API_KEY= -e PYTHONPATH=/app -v /home/hazem/dev/04_Data_Analytics_and_Scrapers/github_analysis/backend:/app:ro api python tests/postgres_radar_check.py
    docker compose run --rm --no-deps -e DATABASE_URL=postgresql+asyncpg://github_analytics:github_analytics@postgres:5432/repotrajectory_radar_test -v /home/hazem/dev/04_Data_Analytics_and_Scrapers/github_analysis/backend:/app:ro api alembic downgrade 0008
    docker compose run --rm --no-deps -e DATABASE_URL=postgresql+asyncpg://github_analytics:github_analytics@postgres:5432/repotrajectory_radar_test -v /home/hazem/dev/04_Data_Analytics_and_Scrapers/github_analysis/backend:/app:ro api alembic upgrade head

Passed: migration chain, downgrade/reapply, pgvector retrieval, no-AI lexical fallback, evidence
upsert replay, indexes, SKIP LOCKED, queue deduplication, cross-session AI budget limits.
The test database is retained, isolated from application data.

Existing quality debt remains: mypy reports nine errors in github/client.py, discovery.py,
ingestion.py and benchmark.py; repository-wide Ruff reports pre-existing style/import issues
outside the new product code. No broad unrelated cleanup was attempted.

No AI keys are required. A read-only GITHUB_TOKEN is required by the existing launcher.
The local app starts at the free port printed by ./run.sh (10100 in this verification).
Actual browser interaction testing and complete live-source coverage remain follow-up validation;
external adapters were tested with mocked HTTP, not live provider calls.

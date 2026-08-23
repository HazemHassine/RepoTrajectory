import asyncio
from datetime import UTC, datetime
from pathlib import Path

import typer
import yaml

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.github.client import GitHubClient
from app.services.analytics import calculate_metrics
from app.services.collector import (
    CollectorScheduler,
    collect_forever,
    collector_overview,
    enqueue_job,
)
from app.services.discovery import reclassify_stored_candidates
from app.services.ingestion import RepositoryIngester

cli = typer.Typer(help="GitHub OSS Intelligence ingestion tools")


async def run(names: list[str]) -> None:
    settings = get_settings()
    if not settings.github_token:
        typer.echo("Warning: GITHUB_TOKEN is unset; unauthenticated rate limits apply.", err=True)
    async with GitHubClient(
        settings.github_token,
        settings.github_api_url,
        request_interval_seconds=settings.github_request_interval_seconds,
        rate_limit_reserve=settings.github_rate_limit_reserve,
    ) as github:
        for name in names:
            typer.echo(f"Ingesting {name}…")
            try:
                async with SessionLocal() as session:
                    repo = await RepositoryIngester(session, github, settings).ingest(name)
                    await calculate_metrics(session, repo)
            except Exception as exc:
                typer.echo(f"Failed {name}: {exc}", err=True)
            else:
                typer.echo(f"Completed {name}")


@cli.command("ingest")
def ingest(repository: str) -> None:
    """Ingest one repository in owner/name form."""
    asyncio.run(run([repository]))


@cli.command("ingest-config")
def ingest_config(path: Path = Path("../repositories.yml")) -> None:
    """Ingest all repositories listed in a YAML configuration file."""
    payload = yaml.safe_load(path.read_text())
    asyncio.run(run(payload["repositories"]))


@cli.command("schedule")
def schedule() -> None:
    """Enqueue due discovery, GH Archive, reconciliation, refresh, and maintenance work."""

    async def execute() -> None:
        async with SessionLocal() as session:
            summary = await CollectorScheduler().tick(session)
        typer.echo(f"Scheduled: {summary}")

    asyncio.run(execute())


@cli.command("collector")
def collector(once: bool = typer.Option(False, help="Process one queued job and exit.")) -> None:
    """Run the autonomous scheduler and durable ingestion worker."""
    settings = get_settings()
    if not settings.github_token:
        typer.echo("GITHUB_TOKEN is required for automated collection.", err=True)
        raise typer.Exit(2)
    asyncio.run(collect_forever(settings, once=once))


@cli.command("enqueue")
def enqueue(repository: str) -> None:
    """Add a manually selected repository to the durable ingestion queue."""

    async def execute() -> None:
        async with SessionLocal() as session:
            bucket = datetime.now(UTC).strftime("%Y-%m-%d-%H%M%S")
            job_id = await enqueue_job(
                session,
                "ingest_repository",
                f"manual:{repository.casefold()}:{bucket}",
                payload={"full_name": repository},
                priority=200,
            )
            await session.commit()
        typer.echo(f"Queued {repository} as job {job_id}")

    asyncio.run(execute())


@cli.command("collector-status")
def collector_status() -> None:
    """Print queue, candidate, GH Archive, and GitHub rate-limit status."""

    async def execute() -> None:
        async with SessionLocal() as session:
            typer.echo(await collector_overview(session))

    asyncio.run(execute())


@cli.command("classify-candidates")
def classify_candidates() -> None:
    """Reapply the software/resource eligibility rules to stored candidates."""

    async def execute() -> None:
        async with SessionLocal() as session:
            counts = await reclassify_stored_candidates(session)
        typer.echo(f"Classified candidates: {counts}")

    asyncio.run(execute())


if __name__ == "__main__":
    cli()

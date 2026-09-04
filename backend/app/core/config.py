from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    app_name: str = "RepoTrajectory API"
    database_url: str = (
        "postgresql+asyncpg://github_analytics:github_analytics@localhost:15432/github_analytics"
    )
    github_token: str | None = None
    github_api_url: str = "https://api.github.com"
    log_level: str = "INFO"
    cors_origins: list[str] = ["http://localhost:3000"]
    admin_username: str = "admin"
    admin_password_hash: str | None = None
    admin_session_secret: str | None = None
    admin_session_hours: int = 8
    admin_secure_cookies: bool = False
    admin_allowed_origins: str = ",".join(
        ["http://localhost:3000", "http://127.0.0.1:3000"]
        + [f"http://localhost:{port}" for port in range(10100, 10111)]
        + [f"http://127.0.0.1:{port}" for port in range(10100, 10111)]
    )
    github_request_interval_seconds: float = 0.15
    github_rate_limit_reserve: int = 100
    ingestion_bootstrap_days: int = 180
    ingestion_release_days: int = 730
    ingestion_contributor_limit: int = 200
    ingestion_commit_limit: int = 5000
    ingestion_issue_limit: int = 3000
    ingestion_pull_request_limit: int = 3000
    ingestion_release_limit: int = 500
    raw_event_retention_days: int = 730
    collector_enabled: bool = True
    collector_poll_seconds: float = 10
    collector_lease_minutes: int = 30
    collector_candidate_limit: int = 2000
    collector_active_limit: int = 250
    collector_active_refresh_hours: int = 24
    collector_candidate_refresh_hours: int = 168
    discovery_languages: str = "Python,TypeScript,JavaScript,Go,Rust,Java"
    discovery_results_per_language: int = 200
    discovery_min_stars: int = 500
    discovery_pushed_within_days: int = 180
    discovery_probe_limit_per_reconcile: int = 50
    gh_archive_enabled: bool = True
    gh_archive_base_url: str = "https://data.gharchive.org"
    gh_archive_algorithm_version: str = "2"
    gh_archive_hours_back: int = 6
    gh_archive_lag_hours: int = 3
    gh_archive_retention_days: int = 90
    gh_archive_top_repositories_per_hour: int = 500
    ai_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    ai_api_key: str | None = None
    gemini_api_key: str | None = None
    ai_embedding_model: str = "text-embedding-3-small"
    ai_evaluation_model: str = "gemini-3.8-flash"
    ai_embedding_dimension: int = 1536
    ai_embedding_version: str = "v1"

    @property
    def effective_ai_api_key(self) -> str | None:
        return self.gemini_api_key or self.ai_api_key
    directory_limit: int = 10000
    candidate_pool_limit: int = 50000
    candidate_retention_days: int = 90
    deep_cohort_limit: int = 500
    directory_language_cap: float = 0.25
    scout_daily_eval_limit: int = 100
    search_rrf_k: int = 60
    search_default_limit: int = 50

    @property
    def discovery_language_list(self) -> list[str]:
        return [value.strip() for value in self.discovery_languages.split(",") if value.strip()]

    @property
    def admin_allowed_origin_list(self) -> list[str]:
        return [
            value.strip().rstrip("/").casefold()
            for value in self.admin_allowed_origins.split(",")
            if value.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()

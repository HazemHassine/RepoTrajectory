import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta


def clamp(value: float, low: float = 0, high: float = 100) -> float:
    return max(low, min(high, value))


def saturating(value: float, target: float) -> float:
    """Map a non-negative feature to 0..100 with diminishing returns."""
    return clamp(100 * (1 - math.exp(-max(value, 0) / target)))


def ratio_change(current: float, previous: float) -> float:
    if previous <= 0:
        return 1.0 if current > 0 else 0.0
    return (current - previous) / previous


def hhi(shares_or_counts: Iterable[float]) -> float:
    values = [max(0, value) for value in shares_or_counts]
    total = sum(values)
    return sum((value / total) ** 2 for value in values) if total else 0.0


@dataclass(frozen=True)
class MomentumInput:
    star_growth_rate: float
    contributor_growth_rate: float
    current_commits: int
    previous_commits: int
    current_prs: int
    previous_prs: int
    releases_per_month: float


def momentum_score(
    value: MomentumInput, growth_available: bool = True
) -> tuple[float, dict[str, float]]:
    components = {
        "star_growth": clamp(50 + 50 * math.tanh(value.star_growth_rate * 4)),
        "contributor_growth": clamp(50 + 50 * math.tanh(value.contributor_growth_rate * 3)),
        "commit_acceleration": clamp(
            50 + 50 * math.tanh(ratio_change(value.current_commits, value.previous_commits))
        ),
        "pr_acceleration": clamp(
            50 + 50 * math.tanh(ratio_change(value.current_prs, value.previous_prs))
        ),
        "release_cadence": saturating(value.releases_per_month, 2),
    }
    weights = {
        "star_growth": 0.25,
        "contributor_growth": 0.20,
        "commit_acceleration": 0.25,
        "pr_acceleration": 0.20,
        "release_cadence": 0.10,
    }
    active_weights = (
        weights
        if growth_available
        else {
            key: weight
            for key, weight in weights.items()
            if key not in {"star_growth", "contributor_growth"}
        }
    )
    total_weight = sum(active_weights.values())
    score = sum(components[key] * weight for key, weight in active_weights.items()) / total_weight
    return round(score, 1), {k: round(v, 1) for k, v in components.items()}


@dataclass(frozen=True)
class HealthInput:
    active_contributors: int
    median_issue_close_hours: float | None
    median_pr_merge_hours: float | None
    pr_merge_rate: float
    releases_per_month: float
    commits_per_week: float


def _responsiveness(hours: float | None, good_hours: float) -> float:
    return 0.0 if hours is None else clamp(100 * math.exp(-max(hours, 0) / (good_hours * 4)))


def health_score(value: HealthInput) -> tuple[float, dict[str, float]]:
    components = {
        "active_contributors": saturating(value.active_contributors, 12),
        "issue_resolution": _responsiveness(value.median_issue_close_hours, 72),
        "pr_merge_time": _responsiveness(value.median_pr_merge_hours, 48),
        "pr_merge_rate": clamp(value.pr_merge_rate * 100),
        "release_cadence": saturating(value.releases_per_month, 2),
        "recent_commits": saturating(value.commits_per_week, 15),
    }
    weights = {
        "active_contributors": 0.20,
        "issue_resolution": 0.15,
        "pr_merge_time": 0.15,
        "pr_merge_rate": 0.20,
        "release_cadence": 0.10,
        "recent_commits": 0.20,
    }
    return round(sum(components[k] * weights[k] for k in weights), 1), {
        k: round(v, 1) for k, v in components.items()
    }


def concentration_metrics(contributions: Sequence[int]) -> dict[str, float]:
    ordered = sorted((max(0, x) for x in contributions), reverse=True)
    total = sum(ordered)
    if not total:
        return {
            "top_1_share": 0,
            "top_3_share": 0,
            "hhi": 0,
            "risk_score": 0,
            "effective_contributors": 0,
        }
    result = {
        "top_1_share": ordered[0] / total,
        "top_3_share": sum(ordered[:3]) / total,
        "hhi": hhi(ordered),
    }
    result["risk_score"] = clamp(
        100 * (0.45 * result["top_1_share"] + 0.25 * result["top_3_share"] + 0.30 * result["hhi"])
    )
    result["effective_contributors"] = 1 / result["hhi"] if result["hhi"] else 0
    return {k: round(v, 3 if k != "risk_score" else 1) for k, v in result.items()}


def in_window(when: datetime, now: datetime, days: int) -> bool:
    return now - timedelta(days=days) <= when <= now

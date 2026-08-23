from datetime import UTC, datetime, timedelta

import pytest

from app.analytics.metrics import (
    HealthInput,
    MomentumInput,
    concentration_metrics,
    health_score,
    hhi,
    in_window,
    momentum_score,
    ratio_change,
)


def test_hhi_distinguishes_concentration() -> None:
    assert hhi([85, 10, 5]) > hhi([25, 25, 25, 25])
    assert hhi([]) == 0


def test_concentration_has_explainable_components() -> None:
    result = concentration_metrics([85, 10, 5])
    assert result["top_1_share"] == 0.85
    assert result["top_3_share"] == 1
    assert result["risk_score"] > 70
    assert result["effective_contributors"] == pytest.approx(1.37, abs=0.01)


def test_momentum_reweights_when_growth_history_is_missing() -> None:
    value = MomentumInput(0, 0, 40, 20, 16, 8, 2)
    score_without_growth, _ = momentum_score(value, growth_available=False)
    score_with_growth, _ = momentum_score(value, growth_available=True)
    assert score_without_growth > score_with_growth


def test_momentum_rewards_acceleration_without_unbounded_values() -> None:
    slow, _ = momentum_score(MomentumInput(0, 0, 10, 20, 4, 8, 0))
    fast, components = momentum_score(MomentumInput(0.15, 0.10, 40, 20, 16, 8, 2))
    assert fast > slow
    assert all(0 <= value <= 100 for value in components.values())


def test_health_handles_missing_response_data() -> None:
    score, components = health_score(HealthInput(10, None, None, 0.6, 1, 20))
    assert 0 <= score <= 100
    assert components["issue_resolution"] == 0


def test_time_window_boundaries() -> None:
    now = datetime.now(UTC)
    assert in_window(now - timedelta(days=30), now, 30)
    assert not in_window(now - timedelta(days=31), now, 30)


@pytest.mark.parametrize(
    ("current", "previous", "expected"), [(20, 10, 1), (5, 10, -0.5), (0, 0, 0), (2, 0, 1)]
)
def test_ratio_change(current: float, previous: float, expected: float) -> None:
    assert ratio_change(current, previous) == expected

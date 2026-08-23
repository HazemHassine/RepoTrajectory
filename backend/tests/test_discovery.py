from app.services.discovery import (
    ArchiveActivity,
    classify_repository,
    percentile_ranks,
    select_archive_activities,
)


def test_resource_repositories_are_withheld_before_hydration() -> None:
    result = classify_repository(
        {
            "name": "public-apis",
            "description": "A collective list of free APIs",
            "language": "Python",
            "topics": ["awesome-list", "api"],
        }
    )

    assert result.category == "learning_resource"
    assert not result.eligible
    assert result.confidence > 0.9


def test_library_and_framework_topics_are_explicitly_classified() -> None:
    library = classify_repository(
        {"name": "client", "language": "Python", "topics": ["api-client"]}
    )
    framework = classify_repository(
        {"name": "web", "language": "TypeScript", "topics": ["web-framework"]}
    )

    assert (library.category, library.eligible) == ("library", True)
    assert (framework.category, framework.eligible) == ("framework", True)


def test_generic_examples_topic_does_not_reject_real_software() -> None:
    result = classify_repository(
        {
            "name": "database-platform",
            "language": "TypeScript",
            "topics": ["database", "examples"],
        }
    )

    assert result.eligible
    assert result.category == "developer_tool"


def test_archive_projection_preserves_adoption_and_collaboration_leaders() -> None:
    activities = [
        ArchiveActivity(1, "spam/push", push_events=50_000),
        ArchiveActivity(2, "users/stars", star_events=8),
        ArchiveActivity(3, "users/stars-two", star_events=4),
        ArchiveActivity(4, "users/forks", fork_events=5),
        ArchiveActivity(5, "team/collaboration", pull_request_events=7),
        ArchiveActivity(6, "team/issues", issue_events=5),
    ]

    result = select_archive_activities(activities, 4)
    ids = {item.github_id for item in result}

    assert ids == {2, 3, 4, 5}
    assert 1 not in ids


def test_zero_signals_receive_no_percentile_credit_and_ties_share_rank() -> None:
    assert percentile_ranks([0, 10, 10, 20]) == [0, 0.5, 0.5, 1]

from app.services.analytics import is_bot


def test_known_bot_logins_are_detected() -> None:
    assert is_bot("dependabot[bot]")
    assert is_bot("github-actions")
    assert is_bot("pre-commit-ci")
    assert not is_bot("octocat")
    assert not is_bot(None)

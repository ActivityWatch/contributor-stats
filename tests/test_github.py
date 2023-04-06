from datetime import datetime
from pprint import pprint

import pytest
from github import Github


@pytest.fixture
def gh() -> Github:
    from contributor_stats.github_stats import _init_gh

    return _init_gh()


def test_comments_by_user(gh: Github):
    from contributor_stats.github_stats import _comments_by_user

    since = datetime(2021, 3, 1)
    repo = "activitywatch/aw-client"  # smaller repo for testing
    comments = _comments_by_user(gh, repo, since)
    pprint(comments)
    assert len(comments) > 0


def test_issues_by_user(gh: Github):
    from contributor_stats.github_stats import _issues_by_user

    since = datetime(2021, 3, 1)
    repo = "activitywatch/aw-client"  # smaller repo for testing
    issues = _issues_by_user(gh, repo, since)
    print("issues_by_user")
    pprint(issues)
    assert len(issues) > 0


def test_pr_comments_by_user(gh: Github):
    from contributor_stats.github_stats import _pr_comments_by_user

    since = datetime(2021, 3, 1)
    repo = "activitywatch/aw-client"  # smaller repo for testing
    pr_comments = _pr_comments_by_user(gh, repo, since)
    print("pr_comments")
    pprint(pr_comments)
    assert len(pr_comments) > 0


def test_issues_stats(gh: Github):
    from contributor_stats.github_stats import _issues_stats

    since = datetime(2021, 3, 1)
    repo = "activitywatch/aw-client"  # smaller repo for testing
    issues_stats = _issues_stats(gh, repo, since)
    print("issues_stats")
    pprint(issues_stats)
    assert len(issues_stats) > 0


def test_submitted_prs(gh: Github):
    from contributor_stats.github_stats import _submitted_prs

    since = datetime(2021, 3, 1)
    repo = "activitywatch/aw-client"  # smaller repo for testing
    submitted_prs = _submitted_prs(gh, repo, since)
    print("submitted_prs")
    pprint(submitted_prs)
    assert submitted_prs

from __future__ import annotations

import os
import logging
from datetime import datetime
from collections import defaultdict
from pprint import pprint

from github import Github

logger = logging.getLogger(__name__)
since = datetime(2020, 11, 1)


def _is_bot(username):
    return "[bot]" in username


def _sort_dict_by_value(d: dict) -> dict:
    return {k: v for k, v in sorted(d.items(), key=lambda item: item[1])}


def _comments_by_user(repo) -> dict[str, int]:
    logger.info(" - Getting comments by user...")
    comments_by_user: dict[str, int] = defaultdict(int)
    for comment in repo.get_issues_comments(since=since):
        if _is_bot(comment.user.login):
            continue
        comments_by_user[comment.user.login] += 1
    return _sort_dict_by_value(comments_by_user)


def _issues_by_user(repo) -> dict[str, int]:
    logger.info(" - Getting issues by user...")
    issues_by_user: dict[str, int] = defaultdict(int)
    for issue in repo.get_issues(state="all", since=since):
        # TODO: Don't count issues tagged as invalid
        if issue.created_at < since:
            continue
        issues_by_user[issue.user.login] += 1
    return _sort_dict_by_value(issues_by_user)


def _pr_comments_by_user(repo) -> dict[str, int]:
    logger.info(" - Getting PR comments by user...")
    pr_comments_by_user: dict[str, int] = defaultdict(int)
    for pr_comment in repo.get_pulls_comments(since=since):
        pr_comments_by_user[pr_comment.user.login] += 1
    return _sort_dict_by_value(pr_comments_by_user)


def _issues_stats(repo) -> dict[str, int]:
    # return the number of closed issues
    logger.info(" - Getting opened/closed issues...")
    opened = 0
    closed = 0
    for issue in repo.get_issues(state="all", since=since):
        if issue.created_at < since:
            opened += 1
        if issue.closed_at and issue.closed_at < since:
            closed += 1
    return {"opened": opened, "closed": closed}


def _submitted_prs(repo):
    # returns the number of merged PRs
    logger.info(" - Getting submitted PRs...")
    count = 0
    for pr in repo.get_pulls(state="all", sort="created", direction="desc"):
        if pr.created_at < since:
            break
        count += 1
    return count


def _merged_prs(repo):
    # returns the number of merged PRs
    # FIXME: Takes a long time to run
    logger.info(" - Getting merged PRs...")
    merged = 0
    for pr in repo.get_pulls(state="closed", sort="updated", direction="desc"):
        if not pr.merged or pr.merged_at < since:
            continue
        if pr.updated_at < since:
            break
        merged += 1
    return merged


def main() -> None:
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
    gh = Github(GITHUB_TOKEN)

    repostats: Dict[str, dict] = {}

    for repo in gh.get_user("ActivityWatch").get_repos():
        if repo.name not in ["activitywatch", "docs"]:
            continue
        logger.info(f"Processing for {repo.name}...")

        repostats[repo.name] = {
            "comments_by_user": _comments_by_user(repo),
            "issues_by_user": _issues_by_user(repo),
            "pr_comments_by_user": _pr_comments_by_user(repo),
            "issues": _issues_stats(repo),
            # "merged_prs": _merged_prs(repo),
            "submitted_prs": _submitted_prs(repo),
        }

    # pprint(repostats)
    # FIXME: pprint should use sort_dicts=False (added in Python 3.8)
    pprint(repostats["activitywatch"])

    all_users = set(
        user
        for repo in repostats.values()
        for user in (
            set(repo["comments_by_user"].keys()) | set(repo["issues_by_user"].keys())
        )
    )
    print(f"Total contributors: {len(all_users)}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()

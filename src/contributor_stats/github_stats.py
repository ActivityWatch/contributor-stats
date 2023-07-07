from __future__ import annotations

import itertools
import logging
import os
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import TypedDict
from dataclasses import dataclass

import pandas as pd
from github import Github
from github.Repository import Repository
from joblib import Memory
from tqdm import tqdm

logger = logging.getLogger(__name__)

# FIXME: Use path relative to script, not working dir
memory = Memory("./.cache/github-stats")


def _is_bot(username):
    return "[bot]" in username


def _sort_dict_by_value(d: dict) -> dict:
    return {k: v for k, v in sorted(d.items(), key=lambda item: item[1])}


class CommentStats(TypedDict):
    count: dict[str, int]
    words: dict[str, int]
    days: dict[str, set[date]]
    reacts_given: dict[str, int]
    reacts_received: dict[str, int]


@memory.cache(ignore=["gh"])
def _comments_by_user(gh: Github, repo_fullname: str, since: datetime) -> CommentStats:
    """Retrieve comment statistics by user"""
    logger.info(" - Getting comments by user...")
    repo: Repository = gh.get_repo(repo_fullname)

    comments_by_user: dict[str, int] = defaultdict(int)
    words_by_user: dict[str, int] = defaultdict(int)
    days_by_user: dict[str, set[date]] = defaultdict(set)
    positive_reacts_to_user: dict[str, int] = defaultdict(int)
    positive_reacts_by_user: dict[str, int] = defaultdict(int)

    for comment in repo.get_issues_comments(since=since):
        print(comment)
        if _is_bot(comment.user.login):
            continue
        comments_by_user[comment.user.login] += 1
        words_by_user[comment.user.login] += len(comment.body.split())
        days_by_user[comment.user.login].add(comment.created_at.date())
        reactions = list(comment.get_reactions())

        for reaction in reactions:
            if reaction.content in ["+1", "hooray", "heart", "rocket"]:
                # Positive reacts (given) by user
                positive_reacts_by_user[reaction.user.login] += 1
                # Positive reacts (received) to user
                positive_reacts_to_user[comment.user.login] += 1

    return CommentStats(
        count=_sort_dict_by_value(comments_by_user),
        words=_sort_dict_by_value(words_by_user),
        days=dict(days_by_user),
        reacts_given=_sort_dict_by_value(positive_reacts_by_user),
        reacts_received=_sort_dict_by_value(positive_reacts_to_user),
    )


@memory.cache(ignore=["gh"])
def _issues_by_user(gh: Github, repo_fullname: str, since: datetime) -> dict[str, int]:
    """Retrieving issue statistics by user"""
    logger.info(" - Getting issues by user...")
    repo: Repository = gh.get_repo(repo_fullname)
    issues_by_user: dict[str, int] = defaultdict(int)
    for issue in repo.get_issues(state="all", since=since):
        # TODO: Don't count issues tagged as invalid
        print(issue)
        if issue.created_at < since:
            continue
        issues_by_user[issue.user.login] += 1
    return _sort_dict_by_value(issues_by_user)


@memory.cache(ignore=["gh"])
def _pr_comments_by_user(
    gh: Github, repo_fullname: str, since: datetime
) -> dict[str, int]:
    logger.info(" - Getting PR comments by user...")
    repo: Repository = gh.get_repo(repo_fullname)
    pr_comments_by_user: dict[str, int] = defaultdict(int)
    for pr_comment in repo.get_pulls_comments(since=since):
        pr_comments_by_user[pr_comment.user.login] += 1
    return _sort_dict_by_value(pr_comments_by_user)


@memory.cache(ignore=["gh"])
def _submitted_prs(gh: Github, repo_fullname: str, since: datetime):
    """returns the number of merged PRs"""
    logger.info(" - Getting submitted PRs...")
    repo: Repository = gh.get_repo(repo_fullname)
    count_by_user: dict[str, int] = defaultdict(int)
    for pr in repo.get_pulls(state="all", sort="created", direction="desc"):
        if pr.created_at < since:
            break
        count_by_user[pr.user.login] += 1
    return count_by_user


@memory.cache(ignore=["gh"])
def _merged_prs_by_user(
    gh: Github, repo_fullname: str, since: datetime
) -> dict[str, int]:
    """returns the number of merged PRs per user"""
    logger.info(" - Getting merged PRs...")
    repo: Repository = gh.get_repo(repo_fullname)
    merged_prs_by_user: dict[str, int] = defaultdict(int)
    for pr in repo.get_pulls(state="closed", sort="updated", direction="desc"):
        if pr.updated_at < since:
            break
        if not pr.merged or pr.merged_at < since:
            continue
        merged_prs_by_user[pr.user.login] += 1
    return merged_prs_by_user


# "I" wrote this with Github Copilot, don't trust it...
# Probably uses *tons* of API calls
# TODO: Can probably be optimized by first getting all the issues/PRs/comments,
#       putting them in some cache, and then iterating over them.
@memory.cache(ignore=["gh"])
def _get_active_days_by_user(
    gh: Github, repo_fullname: str, since: datetime
) -> dict[str, set[date]]:
    """
    Iterates through all issues, comments and PRs to build a set of days where user was active.
    # return a dict {username: set([date1, ...]), ...}
    """
    logger.info(" - Getting active days by user...")
    repo: Repository = gh.get_repo(repo_fullname)
    active_days_by_user = defaultdict(set)
    # issues created
    for issue in repo.get_issues(state="all", since=since):
        if issue.created_at < since:
            break
        active_days_by_user[issue.user.login].add(issue.created_at.date())
    # comments
    for comment in repo.get_issues_comments(since=since):
        if comment.created_at < since:
            continue
        active_days_by_user[comment.user.login].add(comment.created_at.date())
    # pulls created
    for pr in repo.get_pulls(state="all", sort="created", direction="desc"):
        if pr.created_at < since:
            break
        active_days_by_user[pr.user.login].add(pr.created_at.date())
    # pulls merged
    for pr in repo.get_pulls(state="closed", sort="updated", direction="desc"):
        if pr.updated_at < since:
            break
        if not pr.merged or pr.merged_at < since:
            continue
        active_days_by_user[pr.user.login].add(pr.merged_at.date())
    # TODO: pull commits & comments
    return active_days_by_user


def _init_gh():
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
    return Github(GITHUB_TOKEN)


@dataclass
class RepoStats:
    # most stats are per user

    issues: dict[str, int]
    comments: dict[str, CommentStats]
    prs: dict[str, int]
    prs_merged: dict[str, int]
    pr_comments: dict[str, int]
    active_days: dict[str, set[date]]
    #commits: dict[str, int]
    df: pd.DataFrame


def main() -> None:
    gh = _init_gh()
    #since = datetime(2023, 1, 1)
    since = datetime(1999, 1, 1)

    repostats: dict[str, RepoStats] = {}

    for repo in tqdm(list(gh.get_user("ActivityWatch").get_repos())):
        if repo.name not in [
            "activitywatch",
            "activitywatch-old",
            "docs",
            "aw-core",
            "aw-client",
            "aw-client-js",
            "aw-server",
            "aw-server-rust",
            "aw-watcher-window",
            "aw-watcher-afk",
            "aw-watcher-input",
            "aw-watcher-web",
            "aw-webui",
            "aw-qt",
            "activitywatch.github.io",
        ]:
            continue
        logger.info(f"Processing for {repo.name}...")

        repostats[repo.name] = RepoStats(
            issues=_issues_by_user(gh, repo.full_name, since=since),
            comments=_comments_by_user(gh, repo.full_name, since=since),
            prs=_submitted_prs(gh, repo.full_name, since=since),
            prs_merged=_merged_prs_by_user(gh, repo.full_name, since=since),
            pr_comments=_pr_comments_by_user(
                gh, repo.full_name, since=since
            ),
            active_days=_get_active_days_by_user(
                gh, repo.full_name, since=since
            ),
            df=None,
        )

    # pprint(repostats)
    # FIXME: pprint should use sort_dicts=False (added in Python 3.8)
    # pprint(repostats["activitywatch"])

    all_users = set(
        user
        for repo in repostats.values()
        for user in (
            set(repo.comments['count'].keys())
            | set(repo.issues.keys())
            | set(repo.pr_comments.keys())
            | set(repo.prs_merged.keys())
        )
    )
    print(f"Total contributors: {len(all_users)}")

    # Compute stats for each repo
    for name, stats in repostats.items():
        df = pd.DataFrame(
            [
                (
                    user,
                    stats.issues.get(user, 0),
                    stats.comments['count'].get(user, 0),
                    stats.comments['words'].get(user, 0),
                    stats.prs.get(user, 0),
                    stats.pr_comments.get(user, 0),
                    stats.prs_merged.get(user, 0),
                    # active days
                    stats.active_days.get(user, set()),
                )
                for user in all_users
            ],
            columns=[
                "user",
                "issues",
                "comments",
                "comment words",
                "prs",
                "prs_merged",
                "pr_comments",
                "active_days",
            ],
        )
        df["total"] = (
            df["issues"] + df["comments"] + df["pr_comments"] + df["prs_merged"]
        )
        df = df.sort_values("total", ascending=False)
        df = df.set_index("user")
        stats.df = df

    def df_total(repostats: dict[str, pd.DataFrame]) -> pd.DataFrame:
        # Sum all repo stats into one dataframe
        df: pd.DataFrame = None
        for stats in repostats.values():
            if df is None:
                # if first repo, just copy it
                df = stats.df
            else:
                # print(df.columns)
                # print(stats["df"].columns)
                # output: ['issues', 'comments', 'pr_comments', 'submitted_prs', 'merged_prs', 'active_days', 'total']

                # note that active_days is a set, so it's not additive

                df["issues"] += stats.df["issues"]
                df["comments"] += stats.df["comments"]
                df["prs"] += stats.df["prs"]
                df["prs_merged"] += stats.df["prs_merged"]
                df["pr_comments"] += stats.df["pr_comments"]
                df["total"] = (
                    df["issues"]
                    + df["comments"]
                    + df["prs"]
                    + df["prs_merged"]
                    + df["pr_comments"]
                )

                # here the sets in active_days are added together too
                days_by_name = defaultdict(set)
                for name, days in itertools.chain(
                    df["active_days"].items(),
                    stats.df["active_days"].items(),
                ):
                    if isinstance(days, float):
                        continue
                    days_by_name[name].update(days)

                df["active_days"] = pd.Series(
                    list(days_by_name.values()),
                    index=list(days_by_name.keys()),
                    dtype=object,
                )

        df["active_days"] = df["active_days"].apply(lambda x: len(x))
        df = df.sort_values("total", ascending=True)
        return df

    df = df_total(repostats)

    pd.set_option("display.max_rows", None, "display.max_columns", None)
    print(
        df[
            [
                "issues",
                "comments",
                "prs",
                "prs_merged",
                "pr_comments",
                "active_days",
                "total"
            ]
        ]
    )
    print(df.columns)

    savepath = Path("github-activity-table.html")
    with savepath.open("w") as f:
        html = df.to_html()
        f.write(html)
    print(f"Written to {savepath}")
    print("Done!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()

from __future__ import annotations

import itertools
import json
import logging
import os
import subprocess
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable, TypedDict

import pandas as pd
from github import Github, RateLimitExceededException
from github.Repository import Repository
from joblib import Memory
from tqdm import tqdm

logger = logging.getLogger(__name__)

script_dir = Path(__file__).parent
project_dir = script_dir.parent.parent
memory = Memory(project_dir / ".cache" / "github-stats")

# Date to sync from when a repo has no recorded sync state yet.
DEFAULT_SINCE = datetime(1999, 1, 1)

# Cumulative per-user/per-repo stats, persisted between runs so each run only
# has to fetch activity since the last sync (see _load_state/_save_state).
STATE_PATH = project_dir / "github-stats-state.json"


def _is_bot(username):
    # Same filter the published table uses: app accounts end in "[bot]".
    return username.endswith("[bot]")


def _sort_dict_by_value(d: dict) -> dict:
    return {k: v for k, v in sorted(d.items(), key=lambda item: item[1])}


class CommentStats(TypedDict):
    count: dict[str, int]
    words: dict[str, int]
    days: dict[str, set[date]]


class CountWithDays(TypedDict):
    count: dict[str, int]
    days: dict[str, set[date]]


@memory.cache(ignore=["gh"])
def _comments_by_user(gh: Github, repo_fullname: str, since: datetime) -> CommentStats:
    """Retrieve comment statistics by user"""
    logger.info(" - Getting comments by user...")
    repo: Repository = gh.get_repo(repo_fullname)

    comments_by_user: dict[str, int] = defaultdict(int)
    words_by_user: dict[str, int] = defaultdict(int)
    days_by_user: dict[str, set[date]] = defaultdict(set)

    # NOTE: `since` filters on the comment's `updated_at`, not `created_at`.
    # In incremental runs (see _merge_stat), a comment edited after the
    # last sync will be re-counted here, double-counting it in the cumulative
    # totals. Considered rare enough relative to total volume to ignore.
    # NOTE: reactions are deliberately not fetched: get_reactions() costs one
    # API request per comment and the result was unused downstream.
    for comment in repo.get_issues_comments(since=since):
        print(comment)
        if _is_bot(comment.user.login):
            continue
        comments_by_user[comment.user.login] += 1
        words_by_user[comment.user.login] += len(comment.body.split())
        days_by_user[comment.user.login].add(comment.created_at.date())

    return CommentStats(
        count=_sort_dict_by_value(comments_by_user),
        words=_sort_dict_by_value(words_by_user),
        days=dict(days_by_user),
    )


@memory.cache(ignore=["gh"])
def _issues_by_user(gh: Github, repo_fullname: str, since: datetime) -> CountWithDays:
    """Retrieving issue statistics by user"""
    logger.info(" - Getting issues by user...")
    repo: Repository = gh.get_repo(repo_fullname)
    issues_by_user: dict[str, int] = defaultdict(int)
    days_by_user: dict[str, set[date]] = defaultdict(set)
    for issue in repo.get_issues(state="all", since=since):
        # TODO: Don't count issues tagged as invalid
        print(issue)
        if issue.created_at < since:
            continue
        issues_by_user[issue.user.login] += 1
        days_by_user[issue.user.login].add(issue.created_at.date())
    return CountWithDays(
        count=_sort_dict_by_value(issues_by_user), days=dict(days_by_user)
    )


@memory.cache(ignore=["gh"])
def _pr_comments_by_user(
    gh: Github, repo_fullname: str, since: datetime
) -> CountWithDays:
    logger.info(" - Getting PR comments by user...")
    repo: Repository = gh.get_repo(repo_fullname)
    pr_comments_by_user: dict[str, int] = defaultdict(int)
    days_by_user: dict[str, set[date]] = defaultdict(set)
    # NOTE: same `updated_at`-vs-`created_at` caveat as _comments_by_user above.
    for pr_comment in repo.get_pulls_comments(since=since):
        pr_comments_by_user[pr_comment.user.login] += 1
        days_by_user[pr_comment.user.login].add(pr_comment.created_at.date())
    return CountWithDays(
        count=_sort_dict_by_value(pr_comments_by_user), days=dict(days_by_user)
    )


@memory.cache(ignore=["gh"])
def _submitted_prs(gh: Github, repo_fullname: str, since: datetime) -> CountWithDays:
    """returns the number of submitted PRs per user"""
    logger.info(" - Getting submitted PRs...")
    repo: Repository = gh.get_repo(repo_fullname)
    count_by_user: dict[str, int] = defaultdict(int)
    days_by_user: dict[str, set[date]] = defaultdict(set)
    for pr in repo.get_pulls(state="all", sort="created", direction="desc"):
        if pr.created_at < since:
            break
        count_by_user[pr.user.login] += 1
        days_by_user[pr.user.login].add(pr.created_at.date())
    return CountWithDays(count=dict(count_by_user), days=dict(days_by_user))


@memory.cache(ignore=["gh"])
def _merged_prs_by_user(
    gh: Github, repo_fullname: str, since: datetime
) -> CountWithDays:
    """returns the number of merged PRs per user"""
    logger.info(" - Getting merged PRs...")
    repo: Repository = gh.get_repo(repo_fullname)
    merged_prs_by_user: dict[str, int] = defaultdict(int)
    days_by_user: dict[str, set[date]] = defaultdict(set)
    for pr in repo.get_pulls(state="closed", sort="updated", direction="desc"):
        if pr.updated_at < since:
            break
        if not pr.merged or pr.merged_at < since:
            continue
        merged_prs_by_user[pr.user.login] += 1
        days_by_user[pr.user.login].add(pr.merged_at.date())
    return CountWithDays(count=dict(merged_prs_by_user), days=dict(days_by_user))


# One fetcher per stat; each stat is fetched, merged and timestamped
# independently so a run interrupted mid-repo can checkpoint and resume.
# Active days are derived from the objects these fetchers already iterate
# (each reports the days it saw activity on), so no separate fetch is needed.
STAT_FETCHERS: dict[str, Callable] = {
    "issues": _issues_by_user,
    "comments": _comments_by_user,
    "prs": _submitted_prs,
    "prs_merged": _merged_prs_by_user,
    "pr_comments": _pr_comments_by_user,
}


def _empty_user_stats() -> dict:
    return {
        "issues": 0,
        "comments": 0,
        "comment_words": 0,
        "prs": 0,
        "prs_merged": 0,
        "pr_comments": 0,
        "active_days": set(),
    }


def _load_state() -> dict:
    """Load cumulative per-repo/per-user stats from a previous run, if any."""
    if not STATE_PATH.exists():
        return {"repos": {}}

    with STATE_PATH.open() as f:
        state = json.load(f)

    for repo_state in state.get("repos", {}).values():
        # Older states stored a single timestamp per repo; expand it to the
        # per-stat timestamps used since partial-sync checkpoints were added.
        last_synced = repo_state.get("last_synced")
        if last_synced is None:
            repo_state["last_synced"] = {}
        elif isinstance(last_synced, str):
            repo_state["last_synced"] = {stat: last_synced for stat in STAT_FETCHERS}
        # Purge bot rows saved by earlier runs that didn't filter them.
        repo_state["users"] = {
            user: user_stats
            for user, user_stats in repo_state.get("users", {}).items()
            if not _is_bot(user)
        }
        for user_stats in repo_state["users"].values():
            user_stats["active_days"] = {
                date.fromisoformat(d) for d in user_stats.get("active_days", [])
            }
    return state


def _save_state(state: dict) -> None:
    """Persist cumulative per-repo/per-user stats for the next run."""
    serializable = {
        "repos": {
            repo_name: {
                "last_synced": repo_state["last_synced"],
                "users": {
                    user: {
                        **{k: v for k, v in user_stats.items() if k != "active_days"},
                        "active_days": sorted(
                            d.isoformat() for d in user_stats["active_days"]
                        ),
                    }
                    for user, user_stats in repo_state.get("users", {}).items()
                },
            }
            for repo_name, repo_state in state.get("repos", {}).items()
        }
    }
    with STATE_PATH.open("w") as f:
        json.dump(serializable, f, indent=2, sort_keys=True)


def _merge_stat(repo_state: dict, stat: str, data) -> None:
    """Add a freshly-fetched delta for one stat onto the cumulative totals."""
    # Drop bot accounts entirely, matching the published table's filter.
    data = {
        key: {user: v for user, v in d.items() if not _is_bot(user)}
        for key, d in data.items()
    }
    users = repo_state.setdefault("users", {})
    if stat == "comments":
        for user in set(data["count"]) | set(data["words"]):
            stats = users.setdefault(user, _empty_user_stats())
            stats["comments"] += data["count"].get(user, 0)
            stats["comment_words"] += data["words"].get(user, 0)
    else:  # issues, prs, prs_merged, pr_comments
        for user, count in data["count"].items():
            users.setdefault(user, _empty_user_stats())[stat] += count
    # Every fetcher reports the days it saw activity on; set-union makes
    # merging the same day twice harmless.
    for user, days in data["days"].items():
        users.setdefault(user, _empty_user_stats())["active_days"] |= days


def _init_gh():
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
    # per_page=100 (max) to minimize pagination requests; the Actions
    # GITHUB_TOKEN only gets 1000 requests/hour.
    return Github(GITHUB_TOKEN, per_page=100)


def _commit_state() -> None:
    """Commit & push the state file so progress survives if the job is killed.

    Only does anything when running in GitHub Actions; failures are logged
    but never fatal (the end-of-workflow commit step is the primary path).
    """
    if os.getenv("GITHUB_ACTIONS") != "true" or not STATE_PATH.exists():
        return
    git = ["git", "-C", str(project_dir)]
    subprocess.run([*git, "add", str(STATE_PATH)], check=False)
    if subprocess.run([*git, "diff", "--cached", "--quiet"]).returncode == 0:
        return  # no staged changes
    commit = subprocess.run(
        [
            *git,
            "-c",
            "user.name=github-actions[bot]",
            "-c",
            "user.email=github-actions[bot]@users.noreply.github.com",
            "commit",
            "-m",
            "chore: checkpoint github stats state",
        ],
        check=False,
    )
    if commit.returncode == 0:
        push = subprocess.run([*git, "push"], check=False)
        if push.returncode != 0:
            logger.warning("Failed to push state checkpoint")


def _sleep_until_rate_limit_reset(gh: Github) -> None:
    # Checkpoint progress first: the sleep can be up to an hour, during which
    # the job may hit the 6h runner limit or get cancelled.
    _commit_state()
    wait = max(gh.rate_limiting_resettime - time.time(), 0) + 10
    logger.warning(f"Rate limit exceeded, sleeping {wait:.0f}s until reset...")
    time.sleep(wait)


def _sync_repo(gh: Github, state: dict, repo_fullname: str) -> None:
    """Fetch and merge all stat deltas for a repo, one stat at a time.

    Each stat keeps its own last-synced timestamp and is merged into the
    state as soon as it's fetched, so the state checkpointed before a
    rate-limit sleep includes partial progress, even mid-repo. A later run
    then only re-fetches the stats that were still pending.
    """
    repo_state = state["repos"].setdefault(
        repo_fullname, {"last_synced": {}, "users": {}}
    )
    last_synced = repo_state["last_synced"]
    for stat, fetcher in STAT_FETCHERS.items():
        since = (
            datetime.fromisoformat(last_synced[stat])
            if last_synced.get(stat)
            else DEFAULT_SINCE
        )
        while True:
            try:
                data = fetcher(gh, repo_fullname, since=since)
                break
            except RateLimitExceededException:
                # Persist everything merged so far so the checkpoint commit
                # made before sleeping includes partial progress.
                _save_state(state)
                _sleep_until_rate_limit_reset(gh)
        _merge_stat(repo_state, stat, data)
        # Recorded after fetching, so the next run's `since` doesn't skip
        # activity that happened while this run was fetching.
        last_synced[stat] = (
            datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        )
    _save_state(state)


@dataclass
class RepoStats:
    # most stats are per user

    issues: dict[str, int]
    comments: CommentStats
    prs: dict[str, int]
    prs_merged: dict[str, int]
    pr_comments: dict[str, int]
    active_days_set: dict[str, set[date]]
    # commits: dict[str, int]
    df: pd.DataFrame


WHITELIST = [
    "activitywatch",
    "activitywatch-old",
    "docs",
    "aw-core",
    "aw-client",
    "aw-client-js",
    "aw-client-rust",
    "aw-server",
    "aw-server-rust",
    "aw-watcher-window",
    "aw-watcher-window-wayland",
    "aw-watcher-afk",
    "aw-watcher-input",
    "aw-watcher-web",
    "aw-watcher-vim",
    "aw-watcher-vscode",
    "aw-notify",
    "aw-webui",
    "aw-qt",
    "aw-tauri",
    "aw-android",
    "aw-leaderboard-rust",
    "aw-leaderboard-firebase",
    "activitywatch.github.io",
    "awatcher",
]


def _sync(gh: Github, state: dict) -> None:
    """Fetch and merge stats for every whitelisted repo into the state."""
    while True:
        try:
            repos = [
                repo
                for repo in gh.get_user("ActivityWatch").get_repos()
                if repo.name in WHITELIST
            ]
            break
        except RateLimitExceededException:
            _sleep_until_rate_limit_reset(gh)
    for repo in tqdm(repos):
        logger.info(f"Processing for {repo.name}...")
        _sync_repo(gh, state, repo.full_name)


DISPLAY_COLUMNS = [
    "issues",
    "comments",
    "prs",
    "prs_merged",
    "pr_comments",
    "active_days",
    "total",
]

# Minimum total activity for a user to appear in either rendered artifact, so
# the table and the contributors list apply the same bar (drive-by/near-zero
# accounts are excluded from both).
MIN_ACTIVITY_TOTAL = 10


def _aggregate_stats(state: dict) -> pd.DataFrame:
    """Aggregate per-repo stats from saved state into one bot-filtered
    DataFrame sorted by activity, most active first (no API calls).

    Returns columns ``['user'] + DISPLAY_COLUMNS``. Both the HTML activity
    table and the contributors avatar list are rendered from this.
    """
    repostats: dict[str, RepoStats] = {}
    for repo_fullname, repo_state in state["repos"].items():
        users = repo_state["users"]
        name = repo_fullname.split("/")[-1]
        repostats[name] = RepoStats(
            issues={user: stats["issues"] for user, stats in users.items()},
            comments=CommentStats(
                count={user: stats["comments"] for user, stats in users.items()},
                words={user: stats["comment_words"] for user, stats in users.items()},
                days={},
            ),
            prs={user: stats["prs"] for user, stats in users.items()},
            prs_merged={user: stats["prs_merged"] for user, stats in users.items()},
            pr_comments={user: stats["pr_comments"] for user, stats in users.items()},
            active_days_set={
                user: stats["active_days"] for user, stats in users.items()
            },
            df=None,
        )

    all_users = set(
        user
        for repo in repostats.values()
        for user in (
            set(repo.comments["count"].keys())
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
                    stats.comments["count"].get(user, 0),
                    stats.comments["words"].get(user, 0),
                    stats.prs.get(user, 0),
                    stats.pr_comments.get(user, 0),
                    stats.prs_merged.get(user, 0),
                    # active days
                    stats.active_days_set.get(user, set()),
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
                "active_days_set",
            ],
        )

        # issues include PRs, so we need to subtract them.
        # A PR created mid-run (after the issues fetch but before the PR
        # fetch) can make prs briefly exceed issues; the next incremental
        # run counts that PR as an issue and self-corrects the cumulative
        # totals, so clip instead of crashing.
        neg = df["prs"] > df["issues"]
        if neg.any():
            logger.warning(
                f"prs > issues for {df.loc[neg, 'user'].tolist()}, clipping"
            )
        df["issues"] = (df["issues"] - df["prs"]).clip(lower=0)

        df["total"] = (
            df["issues"]
            + df["comments"]
            + df["prs"]
            + df["pr_comments"]
            + df["prs_merged"]
        )
        df = df.sort_values("total", ascending=False)
        df = df.set_index("user")
        stats.df = df

    def df_total(repostats: dict[str, pd.DataFrame]) -> pd.DataFrame:
        # Sum all repo stats into one dataframe
        assert len(repostats) > 0
        df: pd.DataFrame = None
        for stats in repostats.values():
            if df is None:
                # if first repo, just copy it
                df = stats.df
            else:
                # print(df.columns)
                # print(stats["df"].columns)
                # output: ['issues', 'comments', 'pr_comments', 'submitted_prs', 'merged_prs', 'active_days_set', 'total']

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
                    df["active_days_set"].items(),
                    stats.df["active_days_set"].items(),
                ):
                    if isinstance(days, float):
                        continue
                    days_by_name[name].update(days)

                df["active_days_set"] = pd.Series(
                    list(days_by_name.values()),
                    index=list(days_by_name.keys()),
                    dtype=object,
                )
                df["active_days"] = df["active_days_set"].apply(lambda x: len(x))
        df = df.sort_values("total", ascending=True)
        return df

    df = df_total(repostats)

    pd.set_option("display.max_rows", None, "display.max_columns", None)
    print(df[DISPLAY_COLUMNS])
    print(df.columns)

    # reset index to make user a column (better in HTML)
    df = df.reset_index()

    # filter out bots (named end in "[bot]")
    df = df[~df["user"].str.endswith("[bot]")]

    # most active first
    df = df.sort_values(
        ["total", "active_days", "user"], ascending=[False, False, True]
    )

    return df[["user"] + DISPLAY_COLUMNS]


def _render_table(df: pd.DataFrame) -> None:
    """Render the HTML activity table from aggregated stats."""
    # drop near-inactive accounts (same bar as the contributors list)
    df = df[df["total"] > MIN_ACTIVITY_TOTAL].copy()

    # linkify GitHub usernames
    df["user"] = df["user"].apply(lambda x: f'<a href="https://github.com/{x}">{x}</a>')

    # replace "_" with space and title-ize the column names
    df.columns = [
        col.replace("_", " ").title().replace("Pr", "PR") for col in df.columns
    ]

    savepath = Path("github-activity-table.html")
    with savepath.open("w") as f:
        html = df.to_html(
            index=False,
            justify="left",
            classes="table table-sm",
            border=0,
            escape=False,
        )
        f.write(html)
    print(f"Written to {savepath}")


# Number of top contributors (by total GitHub activity) whose avatars are shown
# on the website's contributors page. Chosen to roughly preserve the size of the
# previously hand-maintained _data/contributors.yml.
NUM_CONTRIBUTORS = 64


def _render_contributors(df: pd.DataFrame) -> None:
    """Render the contributors avatar list consumed by the website's
    _data/contributors.yml (the top contributors by total activity)."""
    # same activity bar as the table, so the two artifacts stay consistent even
    # if the contributor pool ever shrinks below NUM_CONTRIBUTORS
    eligible = df[df["total"] > MIN_ACTIVITY_TOTAL]
    users = eligible["user"].head(NUM_CONTRIBUTORS).tolist()
    savepath = Path("contributors.yml")
    with savepath.open("w") as f:
        f.write("\n".join(f"- {user}" for user in users) + "\n")
    print(f"Written {len(users)} contributors to {savepath}")
    print("Done!")


def main(render_only: bool = False) -> None:
    state = _load_state()
    if not render_only:
        gh = _init_gh()
        _sync(gh, state)
    df = _aggregate_stats(state)
    _render_table(df)
    _render_contributors(df)


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(
        description="Sync GitHub contribution stats and render the activity table."
    )
    parser.add_argument(
        "--render-only",
        action="store_true",
        help="Render the table from github-stats-state.json without calling "
        "the GitHub API (no token required).",
    )
    args = parser.parse_args()
    main(render_only=args.render_only)

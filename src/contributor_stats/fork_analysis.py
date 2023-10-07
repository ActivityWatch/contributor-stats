"""
Script to Analyze Forks for Unique Contributions to ActivityWatch Repository

This script uses the GitHub API to analyze forks of the ActivityWatch repository
to identify unique contributions that are not yet incorporated into the upstream.
It's designed to be run in a CI environment where the GITHUB_TOKEN is set.

Requirements:
- Requires the GITHUB_TOKEN environment variable to be set for API authentication.
- Python packages required: requests, json, datetime, os

Output:
- A JSON file named "unique_commits.json" that contains:
    - GitHub username that owns the fork
    - Last checked timestamp in ISO format
    - Array of unique commits, with each commit containing:
        - SHA
        - Author Name
        - Author Email
        - Commit Message
"""
import json
import os
from datetime import datetime, timedelta

import requests


def get_forks(owner, repo, token, page=1):
    url = f"https://api.github.com/repos/{owner}/{repo}/forks?page={page}&per_page=100"
    headers = {}
    if token:
        headers["Authorization"] = f"token {token}"
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()


def get_commits(owner, repo, token, sha="master", page=1):
    url = f"https://api.github.com/repos/{owner}/{repo}/commits?sha={sha}&page={page}&per_page=100"
    headers = {}
    if token:
        headers["Authorization"] = f"token {token}"
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()


def save_to_file(data, filename):
    with open(filename, "w") as f:
        json.dump(data, f, indent=2)


def load_from_file(filename):
    try:
        with open(filename, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def is_outdated(timestamp):
    last_checked = datetime.fromisoformat(timestamp)
    return datetime.now() - last_checked > timedelta(days=30)


def main():
    upstream_owner = "ActivityWatch"
    repo_name = "activitywatch"
    token = os.environ.get("GITHUB_TOKEN")

    # Load previous results
    results = load_from_file("unique_commits.json")

    # Get upstream commits
    upstream_commits = get_commits(upstream_owner, repo_name, token)
    print(f"Found {len(upstream_commits)} upstream commits")
    upstream_commit_shas = {commit["sha"] for commit in upstream_commits}

    # Get all forks
    page = 1
    while True:
        forks = get_forks(upstream_owner, repo_name, token, page=page)
        if not forks:
            break

        for fork in forks:
            owner = fork["owner"]["login"]
            print(f"Checking {owner}/{repo_name}")
            fork_data = results.get(owner, {})

            if "last_checked" in fork_data and not is_outdated(
                fork_data["last_checked"]
            ):
                continue

            try:
                fork_commits = get_commits(owner, repo_name, token)
            except requests.exceptions.HTTPError as e:
                print(f"Failed to get commits for {owner}: {e}")
                continue

            unique_commits_data = []
            for commit in fork_commits:
                if commit["sha"] not in upstream_commit_shas:
                    unique_commit_info = {
                        "sha": commit["sha"],
                        "author": commit["commit"]["author"]["name"],
                        "email": commit["commit"]["author"]["email"],
                        "message": commit["commit"]["message"],
                    }
                    unique_commits_data.append(unique_commit_info)

            results[owner] = {
                "last_checked": datetime.now().isoformat(),
                "unique_commits": unique_commits_data,
            }

        # Save intermediate results
        save_to_file(results, "unique_commits.json")

        page += 1


if __name__ == "__main__":
    main()

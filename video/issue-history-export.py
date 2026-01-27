#!/usr/bin/env python3
"""
Export GitHub issue history for ActivityWatch repos.

This script fetches issue activity (creation, comments, closure) from GitHub
and exports it in a format suitable for visualization.

Usage:
    ./issue-history-export.py [--output issues.csv] [--format csv|gource]

Output formats:
    csv: Standard CSV with timestamp, repo, issue, event_type, author
    gource: Gource-compatible log format for visualization
"""

import subprocess
import json
import sys
from datetime import datetime
from pathlib import Path

# ActivityWatch repos to include
REPOS = [
    "ActivityWatch/activitywatch",
    "ActivityWatch/aw-core",
    "ActivityWatch/aw-server",
    "ActivityWatch/aw-server-rust",
    "ActivityWatch/aw-qt",
    "ActivityWatch/aw-webui",
    "ActivityWatch/aw-watcher-afk",
    "ActivityWatch/aw-watcher-window",
    "ActivityWatch/aw-watcher-web",
    "ActivityWatch/docs",
    "ActivityWatch/activitywatch.github.io",
]

def fetch_issues(repo: str, max_issues: int = 500) -> list:
    """Fetch issues and their timeline from a GitHub repo."""
    print(f"Fetching issues from {repo}...", file=sys.stderr)
    
    # Fetch issues with comments count
    cmd = [
        "gh", "api", "-X", "GET", 
        f"/repos/{repo}/issues",
        "-f", "state=all",
        "-f", "per_page=100",
        "--paginate",
        "--jq", """
            .[] | {
                number: .number,
                title: .title,
                state: .state,
                created_at: .created_at,
                closed_at: .closed_at,
                user: .user.login,
                comments: .comments,
                is_pr: (.pull_request != null)
            }
        """
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            print(f"  Warning: Failed to fetch {repo}: {result.stderr}", file=sys.stderr)
            return []
        
        issues = []
        for line in result.stdout.strip().split('\n'):
            if line:
                try:
                    issues.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        
        return issues[:max_issues]
    except subprocess.TimeoutExpired:
        print(f"  Warning: Timeout fetching {repo}", file=sys.stderr)
        return []

def fetch_issue_comments(repo: str, issue_number: int) -> list:
    """Fetch comments for a specific issue."""
    cmd = [
        "gh", "api", "-X", "GET",
        f"/repos/{repo}/issues/{issue_number}/comments",
        "--jq", '.[] | {created_at: .created_at, user: .user.login}'
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            return []
        
        comments = []
        for line in result.stdout.strip().split('\n'):
            if line:
                try:
                    comments.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        return comments
    except subprocess.TimeoutExpired:
        return []

def to_timestamp(iso_date: str) -> int:
    """Convert ISO date string to Unix timestamp."""
    if not iso_date:
        return 0
    try:
        dt = datetime.fromisoformat(iso_date.replace('Z', '+00:00'))
        return int(dt.timestamp())
    except:
        return 0

def export_gource_format(events: list) -> str:
    """Convert events to Gource-compatible log format.
    
    Gource format: timestamp|author|action|path
    Actions: A (add), M (modify), D (delete)
    """
    lines = []
    for event in sorted(events, key=lambda e: e['timestamp']):
        # Map event types to gource actions
        if event['type'] == 'created':
            action = 'A'  # Add = issue opened
        elif event['type'] == 'comment':
            action = 'M'  # Modify = comment added
        elif event['type'] == 'closed':
            action = 'D'  # Delete = issue closed
        else:
            action = 'M'
        
        # Create path like: repo/issues/issue-number
        path = f"{event['repo']}/issues/{event['issue_number']}"
        
        lines.append(f"{event['timestamp']}|{event['author']}|{action}|{path}")
    
    return '\n'.join(lines)

def export_csv_format(events: list) -> str:
    """Convert events to CSV format."""
    lines = ["timestamp,datetime,repo,issue_number,type,author,title"]
    for event in sorted(events, key=lambda e: e['timestamp']):
        dt = datetime.fromtimestamp(event['timestamp']).isoformat()
        title = event.get('title', '').replace(',', ' ').replace('"', "'")[:50]
        lines.append(f"{event['timestamp']},{dt},{event['repo']},{event['issue_number']},{event['type']},{event['author']},{title}")
    return '\n'.join(lines)

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Export GitHub issue history")
    parser.add_argument('--output', '-o', default='issues.csv', help='Output file')
    parser.add_argument('--format', '-f', choices=['csv', 'gource'], default='csv')
    parser.add_argument('--include-comments', action='store_true', help='Include comment events (slower)')
    args = parser.parse_args()
    
    all_events = []
    
    for repo in REPOS:
        issues = fetch_issues(repo)
        print(f"  Found {len(issues)} issues in {repo}", file=sys.stderr)
        
        for issue in issues:
            if issue.get('is_pr'):
                continue  # Skip PRs for now
            
            repo_short = repo.split('/')[-1]
            
            # Issue created event
            all_events.append({
                'timestamp': to_timestamp(issue['created_at']),
                'repo': repo_short,
                'issue_number': issue['number'],
                'type': 'created',
                'author': issue['user'],
                'title': issue['title']
            })
            
            # Issue closed event
            if issue.get('closed_at'):
                all_events.append({
                    'timestamp': to_timestamp(issue['closed_at']),
                    'repo': repo_short,
                    'issue_number': issue['number'],
                    'type': 'closed',
                    'author': issue['user'],  # Could fetch closer
                    'title': issue['title']
                })
            
            # Fetch comments if requested (slower due to API rate limits)
            if args.include_comments and issue.get('comments', 0) > 0:
                comments = fetch_issue_comments(repo, issue['number'])
                for comment in comments:
                    all_events.append({
                        'timestamp': to_timestamp(comment['created_at']),
                        'repo': repo_short,
                        'issue_number': issue['number'],
                        'type': 'comment',
                        'author': comment['user'],
                        'title': issue['title']
                    })
    
    print(f"\nTotal events: {len(all_events)}", file=sys.stderr)
    
    # Export in requested format
    if args.format == 'gource':
        output = export_gource_format(all_events)
    else:
        output = export_csv_format(all_events)
    
    # Write output
    output_path = Path(args.output)
    output_path.write_text(output)
    print(f"Wrote {len(all_events)} events to {output_path}", file=sys.stderr)

if __name__ == '__main__':
    main()

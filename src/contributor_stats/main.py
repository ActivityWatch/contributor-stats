import sys
import os
import subprocess
import unicodedata
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List, MutableMapping, Optional, Set, Tuple
from collections import OrderedDict, defaultdict
from contextlib import contextmanager

original_cwd = os.getcwd()
__path__ = os.path.dirname(os.path.realpath(__file__))
sys.path.append(os.path.join(__path__, "gitstats"))

import gitstats

logger = logging.getLogger(__name__)

AuthorInfo = MutableMapping[str, dict]
Table = MutableMapping[str, AuthorInfo]
# Author name -> commit email -> number of commits made with it
Emails = MutableMapping[str, MutableMapping[str, int]]

zero_row = OrderedDict(commits=0, active_days=[], lines_added=0, lines_removed=0, blame=0)

# Emails that identify a git client default or a shared/anonymous address rather
# than a person, and must therefore never be used to merge two authors together.
GENERIC_EMAILS = {
    "noreply@github.com",
    "you@example.com",
    "root@localhost",
    "git@localhost",
}


def foldername(path) -> str:
    if os.path.isdir(path):
        return os.path.basename(path)
    else:
        return os.path.dirname(path)


def merge_author(a1: MutableMapping, a2: MutableMapping) -> AuthorInfo:
    # TODO: Needs to merge more properties
    a1["active_days"] = set(a1["active_days"]).union(set(a2["active_days"]))
    a1["commits"] += a2["commits"]
    a1["lines_added"] += a2["lines_added"]
    a1["lines_removed"] += a2["lines_removed"]
    a1["blame"] = a1.get("blame", 0) + a2.get("blame", 0)

    return a1


def normalize_name(name: str) -> str:
    """
    Normalize an author name, so that different spellings of the same name compare equal.
    """
    # Run the following and be amazed by the power of Unicode:
    #   bool('å' == "å")  # False
    # This weird unicode char was in Måns name, so now we have to unicode normalize everything.
    # Never done this before, so thanks for making me learn Måns, or perhaps should I write Måns.
    new_name = unicodedata.normalize("NFKC", name)
    if new_name != name:
        logger.info("Name '{}' was normalized to '{}'".format(name, new_name))
        name = new_name

    return name.replace("å", "å")


def normalize_email(email: str) -> str:
    """
    Normalize a commit email, returning an empty string for the emails that can't be
    used to identify an author (malformed, or a well-known generic address).
    """
    email = email.strip().lower()
    if "@" not in email or email in GENERIC_EMAILS:
        return ""
    return email


def git_author_emails(path) -> Emails:
    """
    Maps each author name in the history to the emails they have committed with,
    and how many commits they made with each of them.

    Uses the same (mailmap-resolved) names as gitstats, so that the keys line up
    with the names in the tables.
    """
    output = subprocess.check_output(
        ["git", "-C", str(path), "log", "--format=%aN%x09%aE", "HEAD"], text=True
    )
    emails: Emails = defaultdict(lambda: defaultdict(int))
    for line in output.splitlines():
        name, _, email = line.partition("\t")
        email = normalize_email(email)
        if not name or not email:
            continue
        emails[normalize_name(name)][email] += 1
    return emails


def merge_emails(emails: Iterable[Emails]) -> Emails:
    """Combines the author -> email mappings of several repos into one."""
    merged: Emails = defaultdict(lambda: defaultdict(int))
    for repo_emails in emails:
        for name, counts in repo_emails.items():
            for email, commits in counts.items():
                merged[name][email] += commits
    return merged


def group_names_by_email(emails: Emails) -> List[List[str]]:
    """
    Groups the author names that share at least one commit email.

    Grouping is transitive: if "a" and "b" share an email, and "b" and "c" share
    another, then all three end up in the same group.
    """
    parent = {name: name for name in emails}

    def find(name: str) -> str:
        while parent[name] != name:
            parent[name] = parent[parent[name]]
            name = parent[name]
        return name

    def union(name: str, other: str) -> None:
        root, other_root = find(name), find(other)
        if root != other_root:
            parent[other_root] = root

    names_by_email: Dict[str, List[str]] = defaultdict(list)
    for name, counts in emails.items():
        for email in counts:
            names_by_email[email].append(name)

    for group in names_by_email.values():
        for other in group[1:]:
            union(group[0], other)

    groups: Dict[str, List[str]] = defaultdict(list)
    for name in parent:
        groups[find(name)].append(name)
    return list(groups.values())


def author_aliases(emails: Emails) -> Dict[str, str]:
    """
    Maps every author name that has an alias (another name used with one of the
    same commit emails) to the single name to display them under.

    The name with the most commits wins, ties broken by name to keep the result
    deterministic (which also happens to prefer "Brayo" over "brayo", since
    uppercase sorts first). The mapping is computed across all repos at once, so
    that the same person gets the same name in every table.
    """
    aliases = {}
    for group in group_names_by_email(emails):
        if len(group) < 2:
            continue
        keep = min(group, key=lambda name: (-sum(emails[name].values()), name))
        logger.info("Merging {} into '{}' (shared commit email)".format(
            sorted(name for name in group if name != keep), keep))
        for name in group:
            if name != keep:
                aliases[name] = keep
    return aliases


def get_authorInfos(data, aliases: Optional[Dict[str, str]] = None) -> Tuple[AuthorInfo, Dict[str, str]]:
    """
    Returns the stats per author, with the aliases of a person merged into a single
    entry, and a mapping from every name in the history to the name it was merged
    into (used to attribute blame lines to the merged author).
    """
    names = data.getAuthors()
    aliases = dict(aliases or {})

    authorInfos: AuthorInfo = {}
    for name in names:
        _authorInfo = data.getAuthorInfo(name)
        name = normalize_name(name)
        if name in authorInfos:
            # Two spellings of the name normalized into the same one
            _authorInfo = merge_author(dict(authorInfos[name]), _authorInfo)
        authorInfos[name] = _authorInfo

    # Every name maps to itself, until merged into another one
    merged_into = {name: name for name in authorInfos}

    def merge_into(keep: str, alias: str) -> None:
        merged: Any = authorInfos.pop(alias)
        if keep in authorInfos:
            merged = merge_author(dict(authorInfos[keep]), merged)
        authorInfos[keep] = merged
        for name, into in merged_into.items():
            if into == alias:
                merged_into[name] = keep

    # Merge the names that committed with the same email
    for alias in sorted(authorInfos):
        keep = aliases.get(alias, alias)
        if keep != alias:
            merge_into(keep, alias)

    # Manual merges, for the aliases that don't share a commit email
    author_merges = [
        ("Erik Bjäreholt", ["Erik BjÃ¤reholt", "Erik Bjareholt"]),
        ("Johan Bjäreholt", ["johan-bjareholt"]),
        ("Nikana", ["nikanar"]),
        ("Johannes Ahnlide", ["ahnlabb"]),
        ("Nicolae Stroncea", ["nicolae-stroncea", "Nicolae", "nicolae"]),
        ("Bill Ang Li", ["Bill-linux"]),
        ("dependabot[bot]", ["dependabot-preview[bot]"]),
        ("Otto-AA", ["A_A"]),
        ("Brayo", ["brayo"])
    ]
    for name, _aliases in author_merges:
        for alias in _aliases:
            if alias in authorInfos:
                merge_into(name, alias)

    return authorInfos, merged_into


def git_blame_stats(path) -> dict[str, int]:
    """
    Uses the following command to get stats of lines last touched by each author:
        git ls-tree --name-only -z -r HEAD -- $1 | xargs -0 -n1 git blame --line-porcelain | grep "^author "|sort|uniq -c|sort -nr
    """
    os.chdir(path)
    output = subprocess.check_output(
        "git ls-tree --name-only -z -r HEAD -- . | xargs -0 -n1 git blame --line-porcelain | grep '^author '|sort|uniq -c|sort -nr", shell=True, text=True
    )
    if output.startswith("usage:"):
        print(os.getcwd())
        raise Exception(output)
    os.chdir(original_cwd)
    return {" ".join(line.split()[2:]): int(line.split()[0]) for line in output.split("\n") if line}


def generate_from_repo(path: Path, aliases: Optional[Dict[str, str]] = None) -> Tuple[str, Table]:
    path = Path(path).resolve()
    if aliases is None:
        aliases = author_aliases(git_author_emails(path))

    # TODO: Could use caching to speed up (not much point since it usually runs in CI)
    data = gitstats.GitDataCollector()

    # `data.collect` always gets the current directory for whatever reason,
    # os.chdir works as a workaround
    os.chdir(path)
    data.collect(path)
    data.refine()
    os.chdir(original_cwd)

    blame = git_blame_stats(path)
    blame_lines = sum(blame.values())

    print("Generated stats for: {}".format(data.projectname))

    rows = {}
    authorInfos, merged_into = get_authorInfos(data, aliases)

    # Attribute the blame lines of every alias to the author it was merged into
    blame_by_author: Dict[str, int] = defaultdict(int)
    for blamed_name, lines in blame.items():
        name = normalize_name(blamed_name)
        blame_by_author[merged_into.get(name, name)] += lines

    for name, info in authorInfos.items():
        rows[name] = merge_author(zero_row.copy(), info)
        rows[name]["blame"] = blame_by_author.get(name, 0)  # type: ignore[assignment]

    for name in rows:
        rows[name]["blame_percent"] = rows[name]["blame"] / blame_lines * 100  # type: ignore

    return data.projectname, rows


def table_print(rows: Table):
    header = "{name:<21} | {activedays:<11} | {commits:<8} | {adds:<8} | {deletes:<8} | {blame}".format(
        name="Name",
        commits="Commits",
        activedays="Active days",
        adds="Added",
        deletes="Removed",
        blame="Blame",
    )
    print(header)
    print("-" * len(header))
    for name, row in rows.items():
        print(
            "{name:<21} | {n_active_days:<11} | {commits:<8} | +{lines_added:<7} | -{lines_removed:<7} | {blame_percent_str}".format(
                name=name, n_active_days=len(row["active_days"]), **row
            )
        )
    print("-" * len(header))


class HTML:
    def __init__(self):
        self.s = ""
        self.indent_level = 0
        self.inline_mode = False

    @contextmanager
    def tag(self, tag_type, attr=None, inline=False):
        tag_start = "<" + tag_type + (" " + attr if attr else "") + ">"
        self += tag_start
        self.indent_level += 1
        yield
        self.indent_level -= 1
        self += "</{}>".format(tag_type)

    def __iadd__(self, other):
        self.s += (self.indent_level * "    ") + other + "\n"
        return self


def table2html(rows: Table) -> str:
    html = HTML()
    # keys = rows[list(rows.keys())[0]].keys()
    keys = ["active_days", "commits", "lines_added", "lines_removed", "blame_percent_str"]

    with html.tag("table", 'class="table table-sm"'):
        # Header
        with html.tag("tr"):
            html += "<th>Name</th>"
            for key in keys:
                if key.endswith("_str"):
                    key = key.replace("_str", "")
                if key.endswith("_percent"):
                    key = key.replace("_percent", " %")
                html += "<th>{}</th>".format(key.replace("_", " ").title())

        # Rows
        for name, row in rows.items():
            with html.tag("tr"):
                html += "<td>{}</td>".format(name)
                for key in keys:
                    value: Any = row[key]
                    if key == "active_days":
                        value = len(value)

                    html += "<td>{}</td>".format(value)
    return html.s


def save_table(name, html, directory="tables") -> None:
    if not os.path.exists(directory):
        os.makedirs(directory)
    filename = "{}.html".format(name)
    filepath = os.path.join("tables", filename)
    with open(filepath, "w") as f:
        f.write(html)
    print("Saved table: {}".format(filepath))


def merge_tables(tables: Dict[str, Table]):
    names = set()
    for _, table in tables.items():
        for name, _ in table.items():
            names.add(name)

    merged_table: Table = OrderedDict([(name, dict(**zero_row)) for name in names])  # type: ignore[dict-item]
    for table in tables.values():
        for name in names:
            if name in table:
                merged_table[name] = merge_author(merged_table[name], table[name])

    # handle blame
    blame_lines = sum(row["blame"] for row in merged_table.values())  # type: ignore[misc]
    for name in merged_table:
        merged_table[name]["blame_percent"] = merged_table[name]["blame"] / blame_lines * 100  # type: ignore

    return merged_table


def main():
    tables = {}

    if len(sys.argv) >= 1:
        repos = [Path(d) for d in sys.argv[1:]]
    else:
        print("No arguments given, looking in repos/ folder")
        p = Path("./repos")
        # Look one and two levels deep
        # Second level might only really be necessary, but meh
        repos = list(p.parent for p in p.glob("./*/.git"))
        repos += list(p.parent for p in p.glob("./*/*/.git") if p.parent not in repos)

    print("Found repos: {}".format([str(r) for r in repos]))

    # Resolve aliases across all repos at once, so that a person gets the same
    # name in every table (and thus a single row in the merged "total" table)
    aliases = author_aliases(merge_emails(git_author_emails(path) for path in repos))

    for path in repos:
        repo_name, rows = generate_from_repo(str(path), aliases)
        tables[repo_name] = rows

    tables["total"] = merge_tables(tables)

    # Sort the tables by days active, then commits, then adds, then by name (to achieve deterministic ordering)
    for key in tables:
        tables[key] = OrderedDict(
            sorted(
                tables[key].items(),
                key=lambda item: [
                    -len(item[1]["active_days"]),
                    -item[1]["commits"],
                    -item[1]["lines_added"],
                    item[0],
                ],
            )
        )

    for table in tables:
        for row in tables[table].values():
            row["blame_percent_str"] = "{:.2f}%".format(row["blame_percent"]).replace("0.00%", "0%")

    for name, rows in tables.items():
        print(name)
        table_print(rows)

        html = table2html(rows)
        save_table(name, html)

        print()
        # print(html)


if __name__ == "__main__":
    main()

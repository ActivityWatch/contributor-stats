import sys
import os
from typing import Dict, List
from collections import OrderedDict, defaultdict
import unicodedata
import logging
from contextlib import contextmanager

original_cwd = os.getcwd()
path = os.path.dirname(os.path.realpath(__file__))
sys.path.append(os.path.join(path, "gitstats"))

import gitstats

logger = logging.getLogger(__name__)

AuthorInfo = Dict[str, dict]
Table = Dict[str, AuthorInfo]

zero_row = OrderedDict(commits=0, active_days=[], lines_added=0, lines_removed=0)


def foldername(path) -> str:
    if os.path.isdir(path):
        return os.path.basename(path)
    else:
        return os.path.dirname(path)


def merge_author(a1: OrderedDict, a2: dict) -> AuthorInfo:
    # TODO: Needs to merge more properties
    a1["commits"] += a2["commits"]
    a1["lines_added"] += a2["lines_added"]
    a1["lines_removed"] += a2["lines_removed"]
    a1["active_days"] = set(a1["active_days"]).union(set(a2["active_days"]))

    return a1


def get_authorInfos(data) -> AuthorInfo:
    names = data.getAuthors()

    authorInfos = {}
    for name in names:
        _authorInfo = data.getAuthorInfo(name)

        # Run the following and be amazed by the power of Unicode:
        #   bool('å' == "å")  # False
        # This weird unicode char was in Måns name, so now we have to unicode normalize everything.
        # Never done this before, so thanks for making me learn Måns, or perhaps should I write Måns.
        _new_name = unicodedata.normalize('NFKC', name)
        if _new_name != name:
            logger.info("Name '{}' was normalized to '{}'".format(name, _new_name))
            name = _new_name

        name = name.replace("å", "å")
        authorInfos[name] = _authorInfo

    author_merges = [("Johan Bjäreholt", "johan-bjareholt"), ("Nikana", "nikanar")]
    for keep_name, replace_name in author_merges:
        if replace_name in authorInfos:
            to_keep = authorInfos.pop(replace_name)
            if keep_name in authorInfos:
                to_merge_with = authorInfos.pop(keep_name)
                to_keep = merge_author(to_merge_with, to_keep)
            authorInfos[keep_name] = to_keep

    return authorInfos


def generate_from_repo(path) -> Table:
    # TODO: Could use caching to speed up
    data = gitstats.GitDataCollector()

    # `data.collect` always gets the current directory for whatever reason,
    # os.chdir works as a workaround
    os.chdir(path)
    data.collect(path)
    data.refine()
    os.chdir(original_cwd)

    print("Generated stats for: {}".format(data.projectname))

    rows = {}
    authorInfos = get_authorInfos(data)
    for name, info in authorInfos.items():
        rows[name] = merge_author(zero_row.copy(), info)

    return data.projectname, rows


def table_print(rows: Table):
    header = "{name:<21} | {commits:<8} | {activedays:<11} | {adds:<8} | {deletes:<8}".format(
             name="Name", commits="Commits", activedays="Active days", adds="Added", deletes="Removed")
    print(header)
    print("-" * len(header))
    for name, row in rows.items():
        print("{name:<21} | {commits:<8} | {n_active_days:<11} | +{lines_added:<7} | -{lines_removed:<7}".format(
              name=name, n_active_days=len(row["active_days"]), **row))
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


def table2html(rows: Table):
    html = HTML()
    keys = rows[list(rows.keys())[0]].keys()

    with html.tag("table", 'class="table"'):
        # Header
        with html.tag("tr"):
            html += "<th>Name</th>"
            for key in keys:
                html += "<th>{}</th>".format(key.replace("_", " ").title())

        # Rows
        for name, row in rows.items():
            with html.tag("tr"):
                html += "<td>{}</td>".format(name)
                for key in keys:
                    value = row[key]
                    if key == "active_days":
                        value = len(value)
                    html += "<td>{}</td>".format(value)
    return html.s


def save_table(name, rows, directory="tables"):
    if not os.path.exists(directory):
        os.makedirs(directory)
    filename = "{}.html".format(name)
    filepath = os.path.join("tables", filename)
    with open(filepath, "w") as f:
        f.write(html)
    print("Saved table: {}".format(filepath))


def merge_tables(tables: Dict[str, Table]):
    names = set()
    for table_name, table in tables.items():
        for name, row in table.items():
            names.add(name)

    merged_table = OrderedDict([(name, zero_row.copy()) for name in names])
    for table in tables.values():
        for name in names:
            if name in table:
                merged_table[name] = merge_author(merged_table[name], table[name])

    return merged_table


if __name__ == "__main__":
    # TODO: Autodetect all submodules
    tables = {}

    for path in sys.argv[1:]:
        path = os.path.abspath(path)

        repo_name, rows = generate_from_repo(path)
        tables[repo_name] = rows

    tables["total"] = merge_tables(tables)

    # Sort the tables by commits
    for key in tables.keys():
        print(tables[key])
        tables[key] = OrderedDict(sorted(tables[key].items(), key=lambda item: -item[1]['commits']))

    for name, rows in tables.items():
        print(name)
        table_print(rows)

        html = table2html(rows)
        save_table(name, html)

        print()
        # print(html)

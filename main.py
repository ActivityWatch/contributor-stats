import sys
import os
from typing import Dict

original_cwd = os.getcwd()
path = os.path.dirname(os.path.realpath(__file__))
sys.path.append(os.path.join(path, "gitstats"))

import gitstats


def merge_author(a1, a2):
    # TODO: Needs to merge more properties
    a1["commits"] += a2["commits"]
    a1["lines_added"] += a2["lines_added"]
    a1["lines_removed"] += a2["lines_removed"]


def getAuthorInfos(data) -> Dict[str, dict]:
    names = data.getAuthors()
    authorInfos = {name: data.getAuthorInfo(name) for name in names}

    author_merges = [("Johan Bjäreholt", "johan-bjareholt")]
    for a1_name, a2_name in author_merges:
        if a1_name in authorInfos and a2_name in authorInfos:
            a1 = authorInfos.pop(a1_name)
            a2 = authorInfos.pop(a2_name)
            authorInfos[a1_name] = merge_author(a1, a2)

    return authorInfos


def generateForRepo(path):
    path = os.path.abspath(path)

    # TODO: Could use caching to speed up
    data = gitstats.GitDataCollector()

    # `data.collect` always gets the current directory for whatever reason,
    # os.chdir works as a workaround
    os.chdir(path)
    data.collect(path)
    os.chdir(original_cwd)

    data.refine()

    print(data.projectname)
    print("Active days: {}".format(len(data.getActiveDays())))

    print("{name:<21} | {commits:<8} | {adds:<8} | {deletes:<8}".format(name="Name", commits="Commits", adds="Added", deletes="Removed"))

    for author in getAuthorInfos(data):
        authorInfo = data.getAuthorInfo(author)
        print("{name:<21} | {commits:<8} | +{lines_added:<7} | -{lines_removed:<7}".format(name=author, **authorInfo))


if __name__ == "__main__":
    for repopath in sys.argv[1:]:
        generateForRepo(repopath)
        print("=" * 60)

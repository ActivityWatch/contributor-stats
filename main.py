import sys

sys.path.append("./gitstats")

import gitstats


def generateForRepo(path):
    data = gitstats.GitDataCollector()

    # Could use caching to speed up
    data.collect(path)

    data.refine()

    print(data.getActiveDays())


if __name__ == "__main__":
    for repopath in ["../", "../aw-core"]:
        generateForRepo(repopath)

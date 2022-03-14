contributor-stats
=================

A project to generate full contributor stats across all ActivityWatch and SuperuserLabs repositories.

Output from this tool is shown on [the ActivityWatch website](https://activitywatch.net/contributors/) for ActivityWatch repos, and not yet anywhere for SuperuserLabs repos (but will someday).

## Features

 - Generate tables from git history with number of active days, number of commits, and diff stats.
 - Generate statistics from GitHub activity (issues, comments, PRs).
 - Create a video visualization, such as the one made for [ActivityWatch]().

## Gource visualization

This also includes scripts to produce a visualization of the commit history with [gource](https://gource.io/).

Usage:

```
cd video
./gource-output.sh
```

NOTE: It assumes you have the repos cloned with a certain directory structure. You will probably need to modify the script to suit your folder structure.

### Output

[![Example of visualization rendered with gource](http://img.youtube.com/vi/zjIn43lZq3U/0.jpg)](http://www.youtube.com/watch?v=zjIn43lZq3U "ActivityWatch Development Visualization 2014-2020, with Gource")

contributor-stats
=================

A project to generate full contributor stats across all ActivityWatch and SuperuserLabs repositories.

Output from this tool is shown on [the ActivityWatch website](https://activitywatch.net/contributors/) for ActivityWatch repos, and not yet anywhere for SuperuserLabs repos (but will someday).

## Gource visualization

This also includes scripts to produce a visualization of the commit history with gource.

Usage:

```
./gource-output.sh
```

NOTE: It assumes you have the repos cloned with a certain directory structure. You will probably need to modify the script to suit your folder structure.

contributor-stats
=================

[![Build](https://github.com/ActivityWatch/contributor-stats/actions/workflows/build.yml/badge.svg)](https://github.com/ActivityWatch/contributor-stats/actions/workflows/build.yml)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Typechecking: Mypy](http://www.mypy-lang.org/static/mypy_badge.svg)](http://mypy-lang.org/)

A project to generate full contributor stats across all ActivityWatch and SuperuserLabs repositories.

Output from this tool is shown on [the ActivityWatch website](https://activitywatch.net/contributors/) for ActivityWatch repos, and not yet anywhere for SuperuserLabs repos (but will someday).

## Features

 - Generate tables from git history with number of active days, number of commits, and diff stats.
 - Generate statistics from GitHub activity (issues, comments, PRs).
 - Create a video visualization, such as the one made for [ActivityWatch](http://www.youtube.com/watch?v=zjIn43lZq3U).

## Gource visualization

This also includes scripts to produce a visualization of the commit history with [gource](https://gource.io/).

### Usage

```bash
cd video
./gource-output.sh
```

### Directory Structure

The script assumes a specific directory layout relative to the video folder:

```txt
../../../                      # rootdir
├── activitywatch/             # Main bundle repo (cloned as activitywatch or .)
│   ├── aw-core/
│   ├── aw-client/
│   ├── aw-server/
│   │   └── aw-webui/
│   ├── aw-server-rust/
│   ├── aw-qt/
│   ├── aw-watcher-afk/
│   ├── aw-watcher-window/
│   └── ...
├── other/                     # Other official repos
│   ├── aw-client-js/
│   ├── aw-watcher-web/
│   ├── aw-watcher-window-wayland/
│   ├── aw-tauri/
│   ├── aw-sync/
│   ├── aw-notify/
│   ├── activitywatch.github.io/
│   ├── aw-research/
│   ├── aw-watcher-vscode/
│   └── aw-watcher-vim/
├── community/                 # Community-contributed projects
│   ├── awatcher/              # https://github.com/2e3s/awatcher
│   ├── aw-watcher-media-player/
│   ├── aw-watcher-jetbrains/
│   └── activitywatch-plasmoid/
├── docs/
└── old/
    └── activitywatch-old/
```

### Including Community Repos

To include community projects in the visualization:

1. Create a `community/` directory next to the main repos
2. Clone the community repos you want to include:

```bash
mkdir -p community
cd community
git clone https://github.com/2e3s/awatcher
git clone https://github.com/2e3s/aw-watcher-media-player
git clone https://github.com/OlivierMary/aw-watcher-jetbrains
git clone https://github.com/NicoWeio/activitywatch-plasmoid
```

The script will automatically skip repos that aren't found, so you can include as many or as few community repos as desired.

### Output

[![Example of visualization rendered with gource](http://img.youtube.com/vi/zjIn43lZq3U/0.jpg)](http://www.youtube.com/watch?v=zjIn43lZq3U "ActivityWatch Development Visualization 2014-2020, with Gource")

### Adding music

After generating `gource.mp4`, you can add music with:

```bash
./gource-output-add-music.sh
```

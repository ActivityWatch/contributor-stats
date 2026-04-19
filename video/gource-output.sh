#!/bin/bash
# ActivityWatch Gource Visualization Script
# Updated 2026-04 to include community repos and extend timeline 2014-2025+

set -e

rootdir=../../../
tmpdir=.cache/gource
communitydir=.cache/community  # Directory for auto-cloned community repos
rm -rf $tmpdir
mkdir -p $tmpdir
mkdir -p $communitydir

echo "=== ActivityWatch Development Visualization ==="
echo "Building gource visualization with official + community repos"

# Auto-clone/update community repos (external contributors)
# These are fetched from GitHub so the script works standalone,
# without needing repos pre-cloned to $rootdir/community/
echo ""
echo "=== Fetching community repos ==="
community_repos=(
    "2e3s/awatcher"                    # Popular Rust watcher for X11/Wayland
    "kepptic/aw-watcher-enhanced"      # Enhanced window watcher with OCR/LLM
    "2e3s/aw-watcher-media-player"     # Media playback tracking
    "brayo-pip/aw-watcher-lastfm"      # Last.fm scrobbles
    "Otto-AA/aw-watcher-vscode"        # VSCode extension
    "OlivierMary/aw-watcher-jetbrains" # JetBrains extension
    "NicoWeio/activitywatch-plasmoid"  # KDE Plasma widget
    "phrp720/aw-sync-suite"            # Prometheus/Grafana sync
)

for repo in "${community_repos[@]}"; do
    name=$(basename $repo)
    if [ -d "$communitydir/$name" ]; then
        echo "  Updating $name..."
        (cd "$communitydir/$name" && git pull --quiet) || echo "    (pull failed, using cached)"
    else
        echo "  Cloning $name..."
        git clone --quiet "https://github.com/$repo.git" "$communitydir/$name" 2>/dev/null || echo "    (clone failed, skipping)"
    fi
done

# Bundle repo (official ActivityWatch)
echo ""
echo "=== Processing official repos ==="
gource --output-custom-log $tmpdir/activitywatch.txt $rootdir

# ===========================================
# Official ActivityWatch modules
# ===========================================
modules=(
    aw-core
    # clients
    aw-client
    other/aw-client-js
    # server
    aw-server
    aw-server-rust
    # ui
    aw-server/aw-webui
    aw-qt
    # watchers
    aw-watcher-afk
    aw-watcher-window
    other/aw-watcher-web
    other/aw-watcher-window-wayland
    # website and docs
    other/activitywatch.github.io
    docs
    # misc
    other/aw-research
    # experimental
    other/aw-tauri
    # sync and notifications
    other/aw-sync
    other/aw-notify
    # old
    old/activitywatch-old
    # hidden due it causing a mess
    #other/aw-android
)

for path in "${modules[@]}"; do
    name=$(basename $path)
    loc=$(echo $name | sed -E "s#.+-watcher-.+#watchers/$name#g")
    loc=$(echo $loc | sed -E "s#.+-client.*#clients/$name#g")
    loc=$(echo $loc | sed -E "s#.+-server.*#servers/$name#g")
    loc=$(echo $loc | sed -E "s#docs|activitywatch.github.io#website/$name#g")
    echo "  $name -> $loc"
    if [ -d "$rootdir/$path" ]; then
        gource --output-custom-log $tmpdir/$name.txt $rootdir/$path 2>/dev/null || echo "    (skipped)"
        sed -i -r "s#(.+)\\|#\\1|/$loc#" $tmpdir/$name.txt 2>/dev/null || true
    else
        echo "    -> Skipping (not found): $rootdir/$path"
    fi
done

# Process community repos (auto-cloned from GitHub)
echo ""
echo "=== Processing community repos ==="
for repo in "${community_repos[@]}"; do
    name=$(basename $repo)
    if [[ $name == *"watcher"* ]] || [[ $name == "awatcher" ]]; then
        loc="watchers/community/$name"
    elif [[ $name == *"plasmoid"* ]] || [[ $name == *"widget"* ]]; then
        loc="widgets/$name"
    else
        loc="community/$name"
    fi
    if [ -d "$communitydir/$name" ]; then
        echo "  $name -> $loc"
        gource --output-custom-log $tmpdir/community-$name.txt $communitydir/$name 2>/dev/null || echo "    (skipped)"
        sed -i -r "s#(.+)\\|#\\1|/$loc#" $tmpdir/community-$name.txt 2>/dev/null || true
    fi
done

# Also process any locally-cloned community repos (if present)
community_local=(
    community/awatcher
    community/aw-watcher-media-player
    other/aw-watcher-vscode
    other/aw-watcher-vim
    community/aw-watcher-jetbrains
    community/activitywatch-plasmoid
)

for path in "${community_local[@]}"; do
    name=$(basename $path)
    # Skip if already processed from auto-clone
    [ -f "$tmpdir/community-$name.txt" ] && continue
    if [[ $name == *"watcher"* ]] || [[ $name == "awatcher" ]]; then
        loc="watchers/community/$name"
    elif [[ $name == *"plasmoid"* ]] || [[ $name == *"widget"* ]]; then
        loc="widgets/$name"
    else
        loc="community/$name"
    fi
    echo "  $name -> $loc (local)"
    if [ -d "$rootdir/$path" ]; then
        gource --output-custom-log $tmpdir/$name.txt $rootdir/$path 2>/dev/null || echo "    (skipped)"
        sed -i -r "s#(.+)\\|#\\1|/$loc#" $tmpdir/$name.txt 2>/dev/null || true
    else
        echo "    -> Skipping (not found): $rootdir/$path"
    fi
done

# Remove all files in activitywatch-old repo when rewrite began
# TODO: Remove in a logical order (deepest first)
sed -E 's/.+[|](.+)[|].+[|](.+)/1461708000|\1|D|\2/g' $tmpdir/activitywatch-old.txt 2>/dev/null | uniq > $tmpdir/fixes.txt || true

gourcelog=$tmpdir/combined.gource

# Combine all the logs into one log
cat $tmpdir/*.txt 2>/dev/null | sort -n > $gourcelog

# Rename activitywatch-old so it behaves like top dir
sed -i 's#activitywatch-old/##g' $gourcelog

# Remove .github folders (they make a mess)
sed -i -E 's#.+/.github/##g' $gourcelog

# Color certain file extensions a certain way
sed -i 's/[.]py/\0|4B8BBE/g' $gourcelog      # Python - blue
sed -i 's/[.]rs$/\0|FFAA33/g' $gourcelog     # Rust - orange
sed -i 's/[.]js/\0|F0DB4F/g' $gourcelog      # JavaScript - yellow
sed -i 's/[.]ts/\0|007ACC/g' $gourcelog      # TypeScript - blue
sed -i 's/[.]vue/\0|41B883/g' $gourcelog     # Vue - green
sed -i 's/[.]go$/\0|00ADD8/g' $gourcelog     # Go - cyan
sed -i 's/[.]kt$/\0|7F52FF/g' $gourcelog     # Kotlin - purple
sed -i 's/[.]java$/\0|B07219/g' $gourcelog   # Java - brown

# Docs
sed -i -E 's/[.](md|rst|txt)|LICENSE$/\0|FF5555/g' $gourcelog
sed -i -E 's/[.](png|jpg|dot|svg)/\0|FFAA55/g' $gourcelog
sed -i -E 's/[.](css|scss)/\0|cc6699/g' $gourcelog
sed -i -E 's/[.](pug|html)/\0|cc6699/g' $gourcelog

# Misc files
sed -i -E 's/Makefile|requirements(-dev)?.txt|Pipfile$/\0|444444/g' $gourcelog
sed -i -E 's/[.](sh|cmd|editorconfig|ya?ml|gitmodules|.+ignore|gitkeep|gitattributes|lock|toml|babelrc|ps1|spec|service|scpt|bat|in)$/\0|444444/g' $gourcelog

# Fix some commit names
sed -i 's/johan-bjareholt/Johan Bjäreholt/g' $gourcelog
sed -i -E 's/Erik Bj.{1,4}reholt/Erik Bjäreholt/g' $gourcelog
sed -i 's/dependabot.+/dependabot/g' $gourcelog
sed -i 's/Bill-linux/Bill Ang Li/g' $gourcelog
# Community contributor name fixes
sed -i 's/2e3s/Denis Gavrilov/g' $gourcelog
sed -i 's/NicoWeio/Nicolai Weitkemper/g' $gourcelog

# Remove names which have been spamming commits in CI (accidental bad CI config)
sed -i 's/.*ErikBjare.*//g' $gourcelog

# Prepare avatars
# TODO: Doesn't fetch avatars from all repos (only the ones with most contributors)
# TODO: Dynamic avatar evolution - change user avatars over time to reflect
#       their profile picture at that point in history. This would require:
#       1. GitHub API to fetch historical avatar URLs (if available) or
#       2. Wayback Machine integration to get historical profile pictures
#       3. Gource custom avatar timeline support (may need patching gource)
#       For now, avatars are static (most recent profile picture)
if [ -d .git/avatar ]; then
    perl fetch-avatars.pl 2>/dev/null || echo "Avatar fetch skipped"
    # run for bundle repo, move avatars to local .git/avatars
    fetchsrc=$(realpath fetch-avatars.pl)
    if [ -d "$rootdir/.git" ]; then
        pushd $rootdir > /dev/null; perl $fetchsrc 2>/dev/null || true; popd > /dev/null
        [ -d "$rootdir/.git/avatar" ] && mv $rootdir/.git/avatar/* .git/avatar 2>/dev/null || true
    fi
    if [ -d "$rootdir/aw-server/aw-webui/.git" ]; then
        pushd $rootdir/aw-server/aw-webui > /dev/null; perl $fetchsrc 2>/dev/null || true; popd > /dev/null
        [ -d "$rootdir/aw-server/aw-webui/.git/avatar" ] && mv $rootdir/aw-server/aw-webui/.git/avatar/* .git/avatar 2>/dev/null || true
    fi
    if [ -d "$rootdir/docs/.git" ]; then
        pushd $rootdir/docs > /dev/null; perl $fetchsrc 2>/dev/null || true; popd > /dev/null
        [ -d "$rootdir/docs/.git/avatar" ] && mv $rootdir/docs/.git/avatar/* .git/avatar 2>/dev/null || true
    fi
    # Fetch avatars for auto-cloned community contributors
    for repo in "${community_repos[@]}"; do
        name=$(basename $repo)
        if [ -d "$communitydir/$name/.git" ]; then
            pushd $communitydir/$name > /dev/null; perl $fetchsrc 2>/dev/null || true; popd > /dev/null
            [ -d "$communitydir/$name/.git/avatar" ] && mv $communitydir/$name/.git/avatar/* .git/avatar 2>/dev/null || true
        fi
    done
fi

# Rename avatars to suit committer name
[ -f ".git/avatar/johan-bjareholt.png" ] && cp .git/avatar/johan-bjareholt.png '.git/avatar/Johan Bjäreholt.png' 2>/dev/null || true

# Resolutions:
#  - 2560x1440 (for upload)
#  - 1920x1080 (for preview)
#  - 1280x720  (for debug)
res_4k=2560x1440
res_high=2560x1440
res_med=1920x1080
res_low=1280x720

# this would be nice, but unfortunately counts directories...
# --file-extension-fallback
gource_options=(
    --title 'ActivityWatch Development 2014-2025+ (https://activitywatch.net)'
    --caption-file gource-captions.txt
    --user-image-dir ../.git/avatar/
    --key --file-idle-time 0
    --seconds-per-day 0.1 --time-scale 1
    --max-user-speed 1000
    --user-friction 1
    --highlight-all-users
    --highlight-dirs
    --date-format "%Y-%m-%d"  # %H:%M
    --font-scale 2
    --font-size 12
    --filename-time 4
    --caption-size 36  # doesn't seem to use font-scale
    --dir-font-size 8
    --file-font-size 14  # doesn't seem to use font-scale
    --elasticity 0.01  # idk what's a good value here
    --padding 1.5  # seems to do nothing, valid values: 0.0-2.0
    #--disable-auto-rotate
    --background-colour 000000
    -$res_med
    $gourcelog
)

echo ""
echo "=== Visualizing ==="
gource "${gource_options[@]}"

# To render video
echo ""
echo "=== Rendering video ==="
gource "${gource_options[@]}" -o - | ffmpeg -y -r 60 -f image2pipe -vcodec ppm -i - -vcodec libx264 -preset ultrafast -pix_fmt yuv420p -crf 1 -threads 0 -bf 0 gource.mp4
echo "Done! Output: gource.mp4"

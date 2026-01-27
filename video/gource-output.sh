#!/bin/bash

set -e

rootdir=../../../
tmpdir=.cache/gource
rm -rf $tmpdir
mkdir -p $tmpdir

echo "Building stuff"

# Bundle repo
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

# ===========================================
# Community-contributed projects
# These are popular community projects from awesome-activitywatch
# Clone them to $rootdir/community/ before running
# ===========================================
community_modules=(
    # Watchers
    community/awatcher                    # Popular X11/Wayland watcher by @2e3s
    community/aw-watcher-media-player     # Media playback watcher by @2e3s
    # Editor integrations
    other/aw-watcher-vscode              # VSCode extension
    other/aw-watcher-vim                 # Vim extension
    community/aw-watcher-jetbrains       # JetBrains IDEs
    # Desktop widgets
    community/activitywatch-plasmoid     # KDE Plasma widget by @NicoWeio
)

for path in "${modules[@]}"; do
    name=$(basename $path)
    loc=$(echo $name | sed -E "s#.+-watcher-.+#watchers/$name#g")
    loc=$(echo $loc | sed -E "s#.+-client.*#clients/$name#g")
    loc=$(echo $loc | sed -E "s#.+-server.*#servers/$name#g")
    loc=$(echo $loc | sed -E "s#docs|activitywatch.github.io#website/$name#g")
    echo $name $loc
    if [ -d "$rootdir/$path" ]; then
        gource --output-custom-log $tmpdir/$name.txt $rootdir/$path
        sed -i -r "s#(.+)\\|#\\1|/$loc#" $tmpdir/$name.txt
    else
        echo "  -> Skipping (not found): $rootdir/$path"
    fi
done

# Process community modules
for path in "${community_modules[@]}"; do
    name=$(basename $path)
    # Categorize community modules
    if [[ $name == *"watcher"* ]] || [[ $name == "awatcher" ]]; then
        loc="watchers/community/$name"
    elif [[ $name == *"plasmoid"* ]] || [[ $name == *"widget"* ]]; then
        loc="widgets/$name"
    else
        loc="community/$name"
    fi
    echo "$name -> $loc (community)"
    if [ -d "$rootdir/$path" ]; then
        gource --output-custom-log $tmpdir/$name.txt $rootdir/$path
        sed -i -r "s#(.+)\\|#\\1|/$loc#" $tmpdir/$name.txt
    else
        echo "  -> Skipping (not found): $rootdir/$path"
    fi
done

# Remove all files in activitywatch-old repo when rewrite began
# TODO: Remove in a logical order (deepest first)
sed -E 's/.+[|](.+)[|].+[|](.+)/1461708000|\1|D|\2/g' $tmpdir/activitywatch-old.txt 2>/dev/null | uniq > $tmpdir/fixes.txt || true

gourcelog=$tmpdir/combined.gource

# Combine all the logs into one log
cat $tmpdir/*.txt | sort -n > $gourcelog

# Rename activitywatch-old so it behaves like top dir
sed -i 's#activitywatch-old/##g' $gourcelog

# Remove .github folders (they make a mess)
sed -i -E 's#.+/.github/##g' $gourcelog

# Color certain file extensions a certain way
sed -i 's/[.]py/\0|4B8BBE/g' $gourcelog
sed -i 's/[.]rs$/\0|FFAA33/g' $gourcelog
sed -i 's/[.]js/\0|F0DB4F/g' $gourcelog
sed -i 's/[.]ts/\0|007ACC/g' $gourcelog
sed -i 's/[.]vue/\0|41B883/g' $gourcelog

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
# run for contributor-stats repo, initialized .git/avatars folder
if [ -d .git/avatar ]; then
    perl fetch-avatars.pl  
    # run for bundle repo, move avatars to local .git/avatars
    fetchsrc=$(realpath fetch-avatars.pl)
    pushd $rootdir; perl $fetchsrc; popd; mv $rootdir/.git/avatar/* .git/avatar 2>/dev/null || true
    pushd $rootdir/aw-server/aw-webui; perl $fetchsrc; popd; mv $rootdir/aw-server/aw-webui/.git/avatar/* .git/avatar 2>/dev/null || true
    pushd $rootdir/docs; perl $fetchsrc; popd; mv $rootdir/docs/.git/avatar/* .git/avatar 2>/dev/null || true
fi

# Rename avatars to suit committer name
[ -f ../.git/avatar/johan-bjareholt.png ] && cp ../.git/avatar/johan-bjareholt.png '../.git/avatar/Johan Bjäreholt.png'

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
    --title 'ActivityWatch (https://activitywatch.net)'
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

echo "Visualizing"
gource "${gource_options[@]}"

# To render video
gource "${gource_options[@]}" -o - | ffmpeg -y -r 60 -f image2pipe -vcodec ppm -i - -vcodec libx264 -preset ultrafast -pix_fmt yuv420p -crf 1 -threads 0 -bf 0 gource.mp4

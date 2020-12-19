#!/bin/bash

set -e

rootdir=../../
tmpdir=.cache/gource
rm -rf $tmpdir
mkdir -p $tmpdir

echo "Building stuff"

# Bundle repo
gource --output-custom-log $tmpdir/activitywatch.txt $rootdir

modules=(
    aw-core
    aw-client
    aw-server
    aw-server-rust
    aw-server/aw-webui
    aw-watcher-afk
    aw-watcher-window
    aw-qt
    docs
    other/aw-watcher-web
    other/aw-client-js
    other/aw-research
    other/activitywatch.github.io
    old/activity-watch
    #other/aw-android
)
for path in "${modules[@]}"; do
    name=$(basename $path)
    echo $name
    gource --output-custom-log $tmpdir/$name.txt $rootdir/$path
    sed -i -r "s#(.+)\\|#\\1|/$name#" $tmpdir/$name.txt
done

# TODO: Remove all files in old/activity-watch when rewrite began
sed -E 's/.+[|](.+)[|].+[|](.+)/1461708000|\1|D|\2/g' $tmpdir/activity-watch.txt | uniq > $tmpdir/fixes.txt

cat $tmpdir/*.txt | sort -n > $tmpdir/combined.txt.gource

# Color certain file extensions a certain way
sed -i 's/[.]py/\0|4B8BBE/g' $tmpdir/combined.txt.gource
sed -i 's/[.]rs$/\0|FFAA33/g' $tmpdir/combined.txt.gource
sed -i 's/[.]js/\0|FFFF00/g' $tmpdir/combined.txt.gource
sed -i 's/[.]vue/\0|41B883/g' $tmpdir/combined.txt.gource

# Docs
sed -i -E 's/[.](md|rst|txt)|LICENSE$/\0|FF5555/g' $tmpdir/combined.txt.gource
sed -i -E 's/[.](png|jpg|dot|svg)/\0|FFAA55/g' $tmpdir/combined.txt.gource

# Misc files
sed -i -E 's/Makefile|requirements(-dev)?.txt|Pipfile|[.](sh|cmd|editorconfig|ya?ml|gitmodules|.+ignore|gitkeep|gitattributes|lock|toml|babelrc|ps1|spec|service|scpt|bat)$/\0|444444/g' $tmpdir/combined.txt.gource

# Fix some commit names
sed -i 's/johan-bjareholt/Johan Bjäreholt/g' $tmpdir/combined.txt.gource
sed -i -E 's/Erik Bj.{1,4}reholt/Erik Bjäreholt/g' $tmpdir/combined.txt.gource
sed -i 's/dependabot.+/dependabot/g' $tmpdir/combined.txt.gource
sed -i 's/Bill-linux/Bill Ang Li/g' $tmpdir/combined.txt.gource

# Prepare avatars
# TODO: Doesn't fetch avatars from all repos (only the ones with most contributors)
# run for contributor-stats repo, initialized .git/avatars folder
if [ -x .git/avatars ]; then
    perl fetch-avatars.pl  
    # run for bundle repo, move avatars to local .git/avatars
    fetchsrc=$(realpath fetch-avatars.pl)
    pushd $rootdir; perl $fetchsrc; popd; mv $rootdir/.git/avatar/* .git/avatar
    pushd $rootdir/aw-server/aw-webui; perl $fetchsrc; popd; mv $rootdir/aw-server/aw-webui/.git/avatar/* .git/avatar
    pushd $rootdir/docs; perl $fetchsrc; popd; mv $rootdir/docs/.git/avatar/* .git/avatar
fi

# Rename avatars to suit committer name
cp .git/avatar/johan-bjareholt.png '.git/avatar/Johan Bjäreholt.png'

gource_options=(
    --title 'ActivityWatch (https://activitywatch.net)'
    --caption-file gource-captions.txt
    --user-image-dir .git/avatar/
    --key --file-idle-time 0
    --seconds-per-day 0.1 --time-scale 1
    --max-user-speed 500
    --highlight-all-users
    --elasticity 0.01
    $tmpdir/combined.txt.gource
)

echo "Visualizing"
#gource "${gource_options[@]}"

# To render video
gource "${gource_options[@]}" -2560x1440 -o - | ffmpeg -y -r 60 -f image2pipe -vcodec ppm -i - -vcodec libx264 -preset ultrafast -pix_fmt yuv420p -crf 1 -threads 0 -bf 0 gource.mp4

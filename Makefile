REPOS_AW=ActivityWatch/activitywatch \
		 ActivityWatch/docs \
		 ActivityWatch/activitywatch.github.io \
		 ActivityWatch/aw-core \
		 ActivityWatch/aw-server \
		 ActivityWatch/aw-server-rust \
		 ActivityWatch/aw-webui \
		 ActivityWatch/aw-qt \
		 ActivityWatch/aw-tauri \
		 ActivityWatch/aw-android \
		 ActivityWatch/aw-client \
		 ActivityWatch/aw-client-js \
		 ActivityWatch/aw-client-rust \
		 ActivityWatch/aw-watcher-web \
		 ActivityWatch/aw-watcher-afk \
		 ActivityWatch/aw-watcher-window \
		 ActivityWatch/aw-watcher-window-wayland \
		 ActivityWatch/aw-watcher-vim \
		 ActivityWatch/aw-watcher-vscode \
		 ActivityWatch/aw-watcher-input \
		 ActivityWatch/aw-leaderboard-rust \
		 ActivityWatch/aw-leaderboard-firebase \
		 ActivityWatch/aw-supabase \
		 ActivityWatch/aw-notify \
		 2e3s/awatcher

REPOS_SL=SuperuserLabs/thankful \
		 SuperuserLabs/thankful-contracts \
		 SuperuserLabs/thankful-server \
		 SuperuserLabs/superuserlabs.github.io

build-aw: clone-aw
	python3 src/contributor_stats/main.py $(addprefix repos/,$(REPOS_AW))

build-sl: clone-sl
	python3 src/contributor_stats/main.py $(addprefix repos/,$(REPOS_SL))

clone-aw: $(patsubst %, repos/%, $(REPOS_AW))
clone-sl: $(patsubst %, repos/%, $(REPOS_SL))

repoorg = $(word 2,$(subst /, ,$1))
reponame = $(word 3,$(subst /, ,$1))

repos/%:
	git clone https://github.com/$(call repoorg,$@)/$(call reponame,$@).git $@

clean:
	rm -f tables/*
	rm -rf repos/*

test:
	poetry run python3 -m pytest tests/

typecheck:
	poetry run python3 -m mypy src/contributor_stats tests --ignore-missing-imports

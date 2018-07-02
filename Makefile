REPOS=activitywatch \
	  docs \
	  activitywatch.github.io \
	  aw-core \
	  aw-server \
	  aw-webui \
	  aw-qt \
	  aw-client \
	  aw-client-js \
	  aw-client-rust \
	  aw-watcher-web \
	  aw-watcher-afk \
	  aw-watcher-window \
	  aw-watcher-vim \
	  aw-watcher-vscode


build: clone
	python3 main.py

clone: $(patsubst %, repos/%, $(REPOS))

reponame = $(word 2,$(subst /, ,$1))

repos/%:
	git clone https://github.com/ActivityWatch/$(call reponame,$@).git $@

clean:
	rm -f tables/*
	rm -rf repos/*

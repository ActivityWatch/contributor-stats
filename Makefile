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
	python3 main.py ${REPOS}

clone: ${REPOS}

activitywatch:
	git clone https://github.com/ActivityWatch/activitywatch.git

docs:
	git clone https://github.com/ActivityWatch/docs.git

activitywatch.github.io:
	git clone https://github.com/ActivityWatch/activitywatch.github.io.git

aw-%:
	git clone https://github.com/ActivityWatch/$@.git

clean:
	rm -f tables/*
	rm -rf activitywatch
	rm -rf docs
	rm -rf aw-*

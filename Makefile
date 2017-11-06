build:
	python3 main.py ./activitywatch \
					./activitywatch/aw-core \
					./activitywatch/aw-server \
					./activitywatch/aw-client \
					./activitywatch/aw-qt \
					./activitywatch/aw-watcher-afk \
					./activitywatch/aw-watcher-window \
					./aw-client-js \
					./aw-watcher-web \
					./aw-webui \
					./docs

clone:
	git clone --recurse-submodules https://github.com/ActivityWatch/activitywatch.git
	git clone --recurse-submodules https://github.com/ActivityWatch/aw-client-js.git
	git clone --recurse-submodules https://github.com/ActivityWatch/aw-watcher-web.git
	git clone --recurse-submodules https://github.com/ActivityWatch/aw-webui.git
	git clone --recurse-submodules https://github.com/ActivityWatch/docs.git

clean:
	rm -f tables/*
	rm -rf activitywatch
	rm -rf aw-client-js
	rm -rf aw-watcher-web
	rm -rf aw-webui
	rm -rf docs

build: activitywatch
	python3 main.py ./activitywatch \
					./activitywatch/aw-core \
					./activitywatch/aw-server \
					./activitywatch/aw-webui \
					./activitywatch/aw-client \
					./activitywatch/aw-qt \
					./activitywatch/aw-watcher-afk \
					./activitywatch/aw-watcher-window \
					./activitywatch/aw-watcher-web

activitywatch:
	git clone --recurse-submodules https://github.com/ActivityWatch/activitywatch.git


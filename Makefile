build: clone
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

clone: activitywatch/ aw-watcher-web/ aw-webui/ docs/ aw-client-js/

activitywatch/:
	git clone --recurse-submodules https://github.com/ActivityWatch/activitywatch.git

aw-watcher-web/:
	git clone --recurse-submodules https://github.com/ActivityWatch/aw-watcher-web.git

aw-webui/:
	git clone --recurse-submodules https://github.com/ActivityWatch/aw-webui.git

docs/:
	git clone --recurse-submodules https://github.com/ActivityWatch/docs.git

aw-client-js/:
	git clone --recurse-submodules https://github.com/ActivityWatch/aw-client-js.git

clean:
	rm -f tables/*
	rm -rf activitywatch
	rm -rf aw-client-js
	rm -rf aw-watcher-web
	rm -rf aw-webui
	rm -rf docs

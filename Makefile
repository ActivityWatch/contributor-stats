build: activitywatch
	python3 main.py ./activitywatch ./activitywatch/aw-core ./activitywatch/aw-server ./activitywatch/aw-webui

activitywatch:
	git clone --recurse-submodules https://github.com/ActivityWatch/activitywatch.git


REPOS=thankful \
	  thankful-contracts \
	  thankful-server \
	  superuserlabs.github.io

build: clone
	python3 main.py

clone: $(patsubst %, repos/%, $(REPOS))

reponame = $(word 2,$(subst /, ,$1))

repos/%:
	git clone https://github.com/SuperuserLabs/$(call reponame,$@).git $@

clean:
	rm -f tables/*
	rm -rf repos/*

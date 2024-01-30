.PHONY:
init:
	pip install tox pre-commit
	pre-commit install

.PHONY:
html: index.rst _static/burndown.png _static/graph_02C.00.png _static/graph_02C.03.png _static/graph_02C.04.png _static/graph_02C.05.png _static/graph_02C.06.png _static/graph_02C.07.png _static/graph_02C.08.png _static/graph_02C.09.png _static/graph_02C.10.png _static/graph_02C.11.png
	tox run -e html

.PHONY:
lint:
	tox run -e lint,linkcheck

.PHONY:
add-author:
	tox run -e add-author

.PHONY:
sync-authors:
	tox run -e sync-authors

.PHONY:
clean:
	rm -rf _build
	rm -rf .technote
	rm -rf .tox
	git checkout index.rst
	rm -f _static/burndown.png

index.rst: bin/generate_dmtn.py
	PYTHONPATH=milestones python3 bin/generate_dmtn.py

_static/burndown.png:
	PYTHONPATH=milestones python3 milestones/milestones.py burndown --output=_static/burndown.png --months=3

_static/graph_%.png:
	PYTHONPATH=milestones python3 milestones/milestones.py graph --wbs=$* --output=$@.dot
	dot -Tpng $@.dot > $@




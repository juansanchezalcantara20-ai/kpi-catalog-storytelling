# One command reproduces everything:  make all
SOURCE ?= auto
PY ?= python

.PHONY: install lint test validate data site powerbi docs serve all clean

install:
	$(PY) -m pip install -e ".[dev]"

lint:
	ruff check .
	ruff format --check .

test:
	$(PY) -m pytest

validate:
	$(PY) -m kpistory validate

data:
	$(PY) -m kpistory data --source $(SOURCE)

site:
	$(PY) -m kpistory site

powerbi:
	$(PY) -m kpistory powerbi

docs: site
	mkdocs build --strict

serve: site
	mkdocs serve

all: lint test validate data site powerbi
	mkdocs build --strict

clean:
	rm -rf site data/processed docs/cases docs/catalog docs/antipatterns.md docs/data-sources.md

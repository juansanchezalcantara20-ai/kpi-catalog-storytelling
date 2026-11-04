# One command reproduces everything:  make all
SOURCE ?= auto
PY ?= python

.PHONY: install lint test validate data site dashboard docs serve all clean legibilidad privacidad

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

dashboard:
	$(PY) -m kpistory dashboard

docs: site
	mkdocs build --strict

serve: site
	mkdocs serve

# Checks that need the built site (readability, coherence of the published numbers, privacy).
legibilidad:
	KPISTORY_REQUIRE_SITE=1 $(PY) -m pytest tests/test_legibilidad.py tests/test_coherencia.py

privacidad:
	$(PY) -m kpistory privacidad

all: lint test validate data site dashboard
	mkdocs build --strict
	$(MAKE) legibilidad privacidad

clean:
	rm -rf site data/processed docs/cases docs/catalog docs/antipatterns.md docs/data-sources.md docs/dashboard

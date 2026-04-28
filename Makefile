.EXPORT_ALL_VARIABLES:


# if you wrap everything in uv run, it runs slower.
ifeq ($(origin VIRTUAL_ENV),undefined)
    VENV := uv run
else
    VENV :=
endif

uv.lock: pyproject.toml
	@echo "Installing dependencies"
	@uv sync

clean-pyc:
	@echo "Removing compiled files"


clean-test:
	@echo "Removing coverage data"
	@rm -f .coverage || true
	@rm -f .coverage.* || true

clean: clean-pyc clean-test

# tests can't be expected to pass if dependencies aren't installed.
# tests are often slow and linting is fast, so run tests on linted code.
test: clean uv.lock install_plugins
	@echo "Running unit tests"
	# $(VENV) pytest --doctest-modules hermetic
	# $(VENV) python -m unittest discover
	$(VENV) pytest test -vv -n 2 --cov=hermetic --cov-report=html --cov-fail-under 5 --cov-branch --cov-report=xml --junitxml=junit.xml -o junit_family=legacy --timeout=5 --session-timeout=600
	$(VENV) bash ./scripts/basic_checks.sh
#	$(VENV) bash basic_test_with_logging.sh



isort:
	@echo "Formatting imports"
	$(VENV) isort .

jiggle_version:
ifeq ($(CI),true)
	@echo "Running in CI mode"
	jiggle_version check
else
	@echo "Running locally"
	jiggle_version hash-all
	# jiggle_version bump --increment auto
endif

.PHONY: black
black: isort jiggle_version
	@echo "Formatting code"
	$(VENV) metametameta pep621
	$(VENV) black hermetic # --exclude .venv
	$(VENV) black test # --exclude .venv
	$(VENV) git2md hermetic --ignore __init__.py __pycache__ --output SOURCE.md

.PHONY: pre-commit
pre-commit: isort black
	@echo "Pre-commit checks"
	$(VENV) pre-commit run --all-files

.PHONY: bandit
bandit:
	@echo "Security checks"
	# $(VENV)  bandit hermetic -r --quiet
	@echo "Bandit isn't 3.14 ready"
	@touch .build_history/bandit

.PHONY: pylint
pylint: isort black
	@echo "Linting with pylint"
	$(VENV) ruff --fix
	$(VENV) pylint hermetic --fail-under 9.8
	@touch .build_history/pylint

# for when using -j (jobs, run in parallel)
.NOTPARALLEL: .build_history/isort .build_history/black

check: mypy test pylint bandit pre-commit update_dev_status dog_food

#.PHONY: publish_test
#publish_test:
#	rm -rf dist && poetry version minor && poetry build && twine upload -r testpypi dist/*

.PHONY: publish
publish: test
	rm -rf dist && hatch build

.PHONY: mypy
mypy:
	$(VENV) echo $$PYTHONPATH
	# $(VENV) mypy hermetic --ignore-missing-imports --check-untyped-defs


check_docs:
	$(VENV) interrogate hermetic --verbose  --fail-under 70
	$(VENV) pydoctest --config .pydoctest.json | grep -v "__init__" | grep -v "__main__" | grep -v "Unable to parse"

make_docs:
	pdoc hermetic --html -o docs --force

check_md:
	$(VENV) linkcheckMarkdown README.md
	$(VENV) markdownlint README.md --config .markdownlintrc
	$(VENV) mdformat README.md docs/*.md


check_spelling:
	$(VENV) pylint hermetic --enable C0402 --rcfile=.pylintrc_spell
	$(VENV) pylint docs --enable C0402 --rcfile=.pylintrc_spell
	$(VENV) codespell README.md --ignore-words=private_dictionary.txt
	$(VENV) codespell hermetic --ignore-words=private_dictionary.txt
	$(VENV) codespell docs --ignore-words=private_dictionary.txt

check_changelog:
	# pipx install keepachangelog-manager
	$(VENV) changelogmanager validate

check_all_docs: check_docs check_md check_spelling check_changelog

check_self:
	# Can it verify itself?
	$(VENV) ./scripts/dog_food.sh

#audit:
#	# $(VENV) python -m hermetic audit
#	$(VENV) tool_audit single hermetic --version=">=2.0.0"

install_plugins:
	echo "N/A"

.PHONY: issues
issues:
	echo "N/A"

core_all_tests:
	./scripts/exercise_core_all.sh hermetic "compile --in examples/compile/src --out examples/compile/out --dry-run"
	uv sync

update_dev_status:
	echo "troml-dev-status update . is not 3.14 ready!"

dog_food:
	# troml-dev-status validate .
	metametameta sync-check
	jiggle_version check
	# troml-dev-status --totalhelp
	# bitrab
	# pycodetags <command?>
	# cli-tool-audit
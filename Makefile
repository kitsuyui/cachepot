.PHONY: lint
lint: flake8 mypy check_import_order check_format

.PHONY: test
test: pytest

.PHONY: format
format: isort black pyupgrade

.PHONY: isort
isort:
	isort cachepot tests

.PHONY: black
black:
	black cachepot tests

.PHONY: flake8
flake8:
	flake8 cachepot tests

.PHONY: pyupgrade
pyupgrade:
	pyupgrade --py37-plus cachepot/*.py tests/*.py

.PHONY: mypy
mypy:
	mypy cachepot tests

.PHONY: check_import_order
check_import_order:
	isort --check-only --diff cachepot tests

.PHONY: check_format
check_format:
	black --check cachepot tests

.PHONY: pytest
pytest:
	pytest --cov=cachepot tests --doctest-modules --cov-report=xml

.PHONY: build
build:
	python3 -m build .

.PHONY: clean
clean:
	rm -rf cachepot.egg-info dist

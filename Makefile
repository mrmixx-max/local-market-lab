.PHONY: setup lint test demo clean

setup:
	pip install -e ".[dev]"

test:
	pytest tests/ -q

demo:
	python -m apps.cli.main demo

clean:
	find . -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache

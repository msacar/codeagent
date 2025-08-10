.PHONY: help install setup index insight insight-cli server watch clean test

help:
	@echo "Available commands:"
	@echo "  make install    - Install dependencies"
	@echo "  make setup      - Initialize CocoIndex database schema"
	@echo "  make index      - Run indexing pipeline"
	@echo "  make insight    - Start CocoInsight server (via main.py)"
	@echo "  make insight-cli - Start CocoInsight server (via CLI)"
	@echo "  make watch      - Watch for changes and auto-reindex"
	@echo "  make clean      - Clean cached data"
	@echo "  make test       - Run tests"

install:
	pip install -e .

setup:
	python -c "from codeagent.pipeline.flow import build_index; import cocoindex; cocoindex.init(); build_index.setup(report_to_stdout=True)"

index:
	python -c "from codeagent.pipeline.flow import run_index; run_index()"

# CocoInsight via main.py shim
insight:
	cocoindex server -ci main.py --address 0.0.0.0:3000 --reload

# CocoInsight directly via flow file (alternative)
insight-direct:
	cocoindex server -ci codeagent/pipeline/flow.py --address 0.0.0.0:3000 --reload

server: insight

watch:
	python -c "from codeagent.cli import watch; watch()"

clean:
	rm -rf .cocoindex_cache
	rm -rf __pycache__
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

test:
	python test_structure.py

test-queries:
	python test_queries.py

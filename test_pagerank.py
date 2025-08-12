#!/usr/bin/env python
"""
Test PageRank functionality
"""

import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from codeagent.pagerank import CodePageRank
from codeagent.pipeline.batch_pagerank import BatchPageRankProcessor
from codeagent.repomap import RepoMap


def test_pagerank_core():
    """Test core PageRank functionality"""
    print("Testing core PageRank...")

    ranker = CodePageRank()

    # Add some test data
    ranker.add_definitions("file1.py", ["func1", "ClassA"])
    ranker.add_definitions("file2.py", ["func2", "ClassB"])
    ranker.add_references("file1.py", ["func2", "ClassB"])
    ranker.add_references("file2.py", ["func1"])

    # Build graph
    graph = ranker.build_file_graph()
    print(f"  Graph nodes: {list(graph.nodes())}")
    print(f"  Graph edges: {list(graph.edges())}")

    # Calculate ranks
    ranks = ranker.calculate_ranks()
    print(f"  File ranks: {ranks}")

    # Get top files
    top_files = ranker.get_important_files(2)
    print(f"  Top files: {top_files}")

    print("✓ Core PageRank working")


def test_batch_processor():
    """Test batch PageRank processor"""
    print("\nTesting batch PageRank processor...")

    # Use current directory for testing
    processor = BatchPageRankProcessor(".")

    # Process a small subset
    processor.process_directory(
        patterns=["*.py"], exclude_patterns=["**/node_modules/**", "**/dist/**"]
    )

    # Get top files
    top_files = processor.get_top_files(5)
    print(f"  Found {len(processor._file_ranks)} files")
    print(f"  Top 5 files:")
    for file, rank in top_files:
        print(f"    - {file}: {rank:.6f}")

    print("✓ Batch processor working")


def test_repo_map():
    """Test repository map generation"""
    print("\nTesting repository map...")

    repo_map = RepoMap(".", max_tokens=500)

    # Generate a small map
    map_content = repo_map.generate()

    lines = map_content.split("\n")
    print(f"  Generated {len(lines)} lines")
    print(f"  First 5 lines:")
    for line in lines[:5]:
        print(f"    {line}")

    print("✓ Repository map working")


if __name__ == "__main__":
    print("=" * 60)
    print("PageRank Functionality Tests")
    print("=" * 60)

    try:
        test_pagerank_core()
        test_batch_processor()
        test_repo_map()

        print("\n" + "=" * 60)
        print("All PageRank tests passed! ✓")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

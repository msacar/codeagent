"""
Repository map generation using PageRank.
Similar to Aider's repo map, shows important files and symbols
with contextual code snippets.
"""

import os
from typing import List, Tuple, Optional
from pathlib import Path
from ..codesitter.parser import parse_defs_and_refs
from ..codesitter.spans import slice_body
from .batch_pagerank import BatchPageRankProcessor


class RepoMap:
    """
    Generate a repository map showing the most important code elements.
    Uses PageRank to identify key files and symbols.
    """

    def __init__(self, root_dir: Optional[str] = None, max_tokens: int = 2000):
        self.root_dir = root_dir or os.getenv("CODEAGENT_ROOT", os.getcwd())
        self.max_tokens = max_tokens
        self.processor = BatchPageRankProcessor(self.root_dir)

    def generate(self, focus_files: Optional[List[str]] = None) -> str:
        """
        Generate a repository map.

        Args:
            focus_files: Optional list of files to prioritize in the map

        Returns:
            A formatted string showing the repository structure and key code
        """
        # Process all files to compute PageRank
        self.processor.process_directory()

        # Get top files by PageRank
        top_files = self.processor.get_top_files(20)

        # If focus files are provided, boost their priority
        if focus_files:
            focus_set = set(focus_files)
            # Boost focus file ranks
            boosted_files = []
            for file, rank in top_files:
                if file in focus_set:
                    boosted_files.append((file, rank * 2.0))
                else:
                    boosted_files.append((file, rank))
            # Re-sort with boosted ranks
            top_files = sorted(boosted_files, key=lambda x: x[1], reverse=True)

        # Generate map content
        map_lines = []
        map_lines.append("=" * 60)
        map_lines.append("REPOSITORY MAP (PageRank-based)")
        map_lines.append("=" * 60)
        map_lines.append("")

        # Add file tree with ranks
        map_lines.append("## Top Files by Importance:")
        for i, (file, rank) in enumerate(top_files[:10], 1):
            map_lines.append(f"{i:2}. {file:50} [rank: {rank:.4f}]")
        map_lines.append("")

        # Add key symbols with context
        map_lines.append("## Key Code Elements:")
        map_lines.append("")

        token_count = sum(len(line.split()) for line in map_lines)

        # Show critical lines from top files
        for file, file_rank in top_files:
            if token_count > self.max_tokens:
                break

            file_path = Path(self.root_dir) / file
            if not file_path.exists():
                continue

            try:
                # Parse file to get symbols
                defs, _ = parse_defs_and_refs(str(file_path), file)

                # Sort definitions by their rank
                ranked_defs = []
                for d in defs:
                    symbol_rank = self.processor.get_symbol_rank(file, d.name)
                    ranked_defs.append((d, symbol_rank))
                ranked_defs.sort(key=lambda x: x[1], reverse=True)

                # Show top symbols from this file
                if ranked_defs:
                    map_lines.append(f"### {file}")

                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()

                    shown_symbols = 0
                    for d, rank in ranked_defs[:3]:  # Top 3 symbols per file
                        if token_count > self.max_tokens:
                            break

                        # Get concise context around the symbol
                        _, _, snippet = slice_body(
                            content, d.start_line, d.end_line, pad_before=1, pad_after=1
                        )

                        # Add symbol info (Tree-sitter is 0-based; display 1-based)
                        map_lines.append(
                            f"  {d.symbol_kind} {d.name} [L{d.start_line + 1}]"
                        )

                        # Add first few lines of the symbol
                        snippet_lines = snippet.split("\n")[:3]
                        for line in snippet_lines:
                            if line.strip():
                                map_lines.append(f"    {line}")

                        if len(snippet.split("\n")) > 3:
                            map_lines.append("    ...")

                        map_lines.append("")
                        shown_symbols += 1
                        token_count = sum(len(line.split()) for line in map_lines)

                    if shown_symbols > 0:
                        map_lines.append("")

            except Exception as e:
                print(f"Error processing {file}: {e}")
                continue

        return "\n".join(map_lines)

    def get_context_for_symbols(self, symbols: List[Tuple[str, str]]) -> str:
        """
        Get contextual code for specific symbols.

        Args:
            symbols: List of (file, symbol_name) tuples

        Returns:
            Formatted context string
        """
        context_lines = []

        for file, symbol in symbols:
            file_path = Path(self.root_dir) / file
            if not file_path.exists():
                continue

            try:
                defs, _ = parse_defs_and_refs(str(file_path), file)

                # Find the matching definition
                for d in defs:
                    if d.name == symbol:
                        with open(
                            file_path, "r", encoding="utf-8", errors="ignore"
                        ) as f:
                            content = f.read()

                        _, _, snippet = slice_body(
                            content, d.start_line, d.end_line, pad_before=2, pad_after=2
                        )

                        context_lines.append(f"## {file}:{symbol}")
                        context_lines.append(
                            f"   {d.symbol_kind} at line {d.start_line + 1}"
                        )
                        context_lines.append("")
                        context_lines.append(snippet)
                        context_lines.append("")
                        break

            except Exception as e:
                print(f"Error getting context for {file}:{symbol}: {e}")

        return "\n".join(context_lines)

"""
Chat-aware context map using personalized PageRank.
Optimizes the repo map for the current chat context, similar to Aider's approach.
"""

import os
import re
from typing import Dict, List, Set, Optional
from pathlib import Path
import networkx as nx

from .codesitter.parser import parse_defs_and_refs
from .codesitter.spans import slice_body


# Patterns for extracting file paths and identifiers from prompts
PATH_TOKEN = re.compile(r"[\w/.-]+\.(?:ts|tsx|js|jsx|py)$")
IDENT_TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")


class ContextMapBuilder:
    """
    Build a context map optimized for the current chat using personalized PageRank.
    """

    def __init__(
        self,
        root_dir: str,
        include: Optional[List[str]] = None,
        exclude: Optional[List[str]] = None,
        processor=None,
    ):
        self.root_dir = root_dir
        self._include = include
        self._exclude = exclude
        self._graph = None
        self._file_symbols: Dict[str, List[dict]] = {}
        # Get top files from database on initialization
        self._top_files = None
        self._top_symbols = None
        self.processor = processor

    def _extract_mentions(self, prompt: str) -> Set[str]:
        """Extract file paths and symbol names mentioned in the prompt."""
        seeds = set()

        # Extract file paths from prompt
        files = PATH_TOKEN.findall(prompt)
        all_files = (
            set(self.processor._file_ranks.keys())
            if self.processor._file_ranks
            else set()
        )

        for f in files:
            # Match by suffix against known files
            for known_file in all_files:
                if known_file.endswith(f):
                    seeds.add(known_file)

        # Extract identifiers from prompt and find files that define them
        for ident in IDENT_TOKEN.findall(prompt):
            # Look for files that define this symbol
            for file, symbols in self.processor.ranker.file_defs.items():
                if ident in symbols:
                    seeds.add(file)

        return seeds

    def _build_personalized_graph(self, seed_files: Set[str]) -> nx.MultiDiGraph:
        """Build a graph with personalization for seed files."""
        # Get the base graph from the processor
        G = self.processor.ranker.build_file_graph()

        # Add personalization scores
        personalization = {}
        for node in G.nodes():
            if node in seed_files:
                personalization[node] = 1.0
            else:
                personalization[node] = 0.1

        return G, personalization

    def build_context_map(
        self,
        prompt: str = "",
        chat_files: Optional[List[str]] = None,
        map_tokens: Optional[int] = None,
        top_files: Optional[int] = None,
    ) -> List[dict]:
        """
        Build a context map optimized for the current chat.

        Args:
            prompt: The user's query/prompt
            chat_files: Explicit files to include as seeds
            map_tokens: Approximate token budget for the map
            top_files: Maximum number of files to include

        Returns:
            List of dicts with file, rank, and highlights
        """
        # Defaults if caller didn't provide them
        if map_tokens is None:
            map_tokens = int(os.getenv("CODEAGENT_MAP_TOKENS", "1200"))
        if top_files is None:
            top_files = int(os.getenv("CODEAGENT_TOP_FILES", "25"))

        # Lazy-init processor if caller didn't attach one
        if self.processor is None:
            from codeagent.pipeline.batch_pagerank import BatchPageRankProcessor

            self.processor = BatchPageRankProcessor(self.root_dir)

        # Process directory to build graph
        self.processor.process_directory(
            patterns=self._include, exclude_patterns=self._exclude
        )

        # Build seed set from prompt and chat files
        seeds = set(chat_files or [])
        seeds |= self._extract_mentions(prompt)

        # If no seeds, use uniform personalization
        if not seeds:
            personalization = None
        else:
            # Build personalization vector
            all_files = set(self.processor._file_ranks.keys())
            personalization = {}
            for f in all_files:
                personalization[f] = 1.0 if f in seeds else 0.0

        # Get graph and compute personalized PageRank
        G = self.processor.ranker.build_file_graph()

        if G.nodes():
            if personalization:
                # Normalize personalization
                total = sum(personalization.values())
                if total > 0:
                    personalization = {k: v / total for k, v in personalization.items()}

            try:
                ranks = nx.pagerank(
                    G, alpha=0.85, personalization=personalization, weight="weight"
                )
            except nx.PowerIterationFailedConvergence:
                # Fallback to unweighted
                ranks = nx.pagerank(G, alpha=0.85, personalization=personalization)
        else:
            ranks = {}

        # Sort by rank and get top files
        sorted_files = sorted(ranks.items(), key=lambda x: x[1], reverse=True)[
            :top_files
        ]

        # Build result with highlights
        result = []
        approx_tokens = 0
        token_limit = map_tokens * 4  # Rough approximation: 1 token ≈ 4 chars

        for file, rank in sorted_files:
            if approx_tokens >= token_limit:
                break

            file_path = Path(self.root_dir) / file
            if not file_path.exists():
                continue

            # Get highlights (top symbols from this file)
            highlights = []

            try:
                # Parse file to get symbols
                defs, _ = parse_defs_and_refs(str(file_path), file)

                # Sort definitions by importance (could use symbol ranks here)
                symbol_ranks = []
                for d in defs[:4]:  # Limit to top 4 symbols per file
                    symbol_rank = self.processor.get_symbol_rank(file, d.name)
                    symbol_ranks.append((d, symbol_rank))

                symbol_ranks.sort(key=lambda x: x[1], reverse=True)

                # Read file content
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                for d, _ in symbol_ranks:
                    # Get symbol context
                    header = f"{d.symbol_kind} {d.name}"

                    # Get first line of body
                    _, _, snippet = slice_body(
                        content, d.start_line, d.end_line, pad_before=0, pad_after=0
                    )

                    lines = snippet.split("\n")
                    first_line = lines[0] if lines else ""
                    if len(first_line) > 120:
                        first_line = first_line[:120] + "…"

                    piece_len = len(header) + len(first_line)
                    if approx_tokens + piece_len > token_limit and highlights:
                        break

                    approx_tokens += piece_len
                    highlights.append(
                        {
                            "header": header,
                            "body": first_line,
                            "start": d.start_line,
                            "end": d.end_line,
                        }
                    )

            except Exception as e:
                print(f"Error processing {file}: {e}")

            result.append({"file": file, "rank": rank, "highlights": highlights})

        return result

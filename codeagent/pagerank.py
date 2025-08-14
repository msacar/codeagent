"""
PageRank implementation for code ranking (Aider-style).
Builds a dependency graph from definitions and references,
then runs PageRank to find important files and symbols.
"""

import re
from collections import defaultdict
from typing import Dict, List, Set, Tuple
import networkx as nx


class CodePageRank:
    def __init__(self):
        self.defines: Dict[str, Set[str]] = defaultdict(
            set
        )  # symbol -> files that define it
        self.references: Dict[str, List[str]] = defaultdict(
            list
        )  # symbol -> files that reference it
        self.file_refs: Dict[str, List[str]] = defaultdict(
            list
        )  # file -> symbols it references
        self.file_defs: Dict[str, List[str]] = defaultdict(
            list
        )  # file -> symbols it defines

    def add_definitions(self, file: str, symbols: List[str]):
        """Add symbol definitions from a file."""
        for symbol in symbols:
            self.defines[symbol].add(file)
            self.file_defs[file].append(symbol)

    def add_references(self, file: str, symbols: List[str]):
        """Add symbol references from a file."""
        for symbol in symbols:
            self.references[symbol].append(file)
            self.file_refs[file].append(symbol)

    def build_file_graph(self) -> nx.MultiDiGraph:
        """
        Build a directed graph of file dependencies.
        Edge from referencer -> definer, weighted by reference strength.
        """
        G = nx.MultiDiGraph()

        # Add all files as nodes
        all_files = set()
        for files in self.defines.values():
            all_files.update(files)
        for file in self.file_refs.keys():
            all_files.add(file)

        for file in all_files:
            G.add_node(file)

        # Create edges from referencer to definer
        for symbol, defining_files in self.defines.items():
            for referencing_file in self.references.get(symbol, []):
                for defining_file in defining_files:
                    if referencing_file != defining_file:
                        # Calculate edge weight based on reference characteristics
                        weight = self._calculate_edge_weight(
                            symbol, referencing_file, defining_file
                        )
                        G.add_edge(
                            referencing_file,
                            defining_file,
                            symbol=symbol,
                            weight=weight,
                        )

        return G

    def _calculate_edge_weight(
        self, symbol: str, referencer: str, definer: str
    ) -> float:
        """
        Calculate edge weight using Aider's heuristics:
        - Case style matching (camelCase vs snake_case)
        - Reference frequency
        - Symbol importance
        """
        weight = 1.0

        # Check case style consistency
        if self._is_camel_case(symbol):
            # Boost if both files use camelCase conventions
            if any(self._is_camel_case(s) for s in self.file_defs.get(definer, [])):
                weight *= 1.2
        elif self._is_snake_case(symbol):
            # Boost if both files use snake_case conventions
            if any(self._is_snake_case(s) for s in self.file_defs.get(definer, [])):
                weight *= 1.2

        # Dampen by frequency (common symbols are less important)
        total_refs = len(self.references.get(symbol, []))
        # Apply higher threshold first so the 20+ case isn't shadowed
        if total_refs > 20:
            weight *= 0.6
        elif total_refs > 10:
            weight *= 0.8

        # Boost for likely important symbols
        if symbol.startswith("_"):  # Private symbols
            weight *= 0.7
        elif symbol and symbol[0].isupper():  # Classes/Types (guard empty)
            weight *= 1.3

        # --- Practical signal shaping for codebases with TypeScript/tests ---
        # 1) Downweight edges *to* pure type declaration files and @types bundles.
        #    .d.ts are type-only; they accumulate many references by design.
        if definer.endswith(".d.ts") or "/@types/" in definer:
            weight *= 0.25

        # 2) Downweight edges *from* tests to source to avoid tests dominating.
        if (
            "/__tests__/" in referencer
            or ".test." in referencer
            or ".spec." in referencer
        ):
            weight *= 0.5

        return weight

    def _is_camel_case(self, name: str) -> bool:
        """Check if name uses camelCase."""
        return bool(re.match(r"^[a-z][a-zA-Z0-9]*$", name))

    def _is_snake_case(self, name: str) -> bool:
        """Check if name uses snake_case."""
        return bool(re.match(r"^[a-z][a-z0-9_]*$", name))

    def calculate_ranks(self, damping: float = 0.85) -> Dict[str, float]:
        """
        Run PageRank on the file dependency graph.
        Returns dict of file -> rank score.
        """
        G = self.build_file_graph()

        if not G.nodes():
            return {}

        # Run PageRank
        try:
            ranks = nx.pagerank(G, alpha=damping, weight="weight")
        except nx.PowerIterationFailedConvergence:
            # Fallback to unweighted if convergence fails
            ranks = nx.pagerank(G, alpha=damping, weight=None)

        return ranks

    def get_symbol_ranks(
        self, file_ranks: Dict[str, float]
    ) -> Dict[Tuple[str, str], float]:
        """
        Calculate symbol ranks based on file ranks.
        Returns dict of (file, symbol) -> rank.
        """
        symbol_ranks = {}

        for file, rank in file_ranks.items():
            # Distribute file rank among its symbols
            file_symbols = self.file_defs.get(file, [])
            if file_symbols:
                symbol_rank = rank / len(file_symbols)
                for symbol in file_symbols:
                    symbol_ranks[(file, symbol)] = symbol_rank

        return symbol_ranks

    def get_important_files(self, top_n: int = 10) -> List[Tuple[str, float]]:
        """Get the top N most important files by PageRank."""
        ranks = self.calculate_ranks()
        sorted_ranks = sorted(ranks.items(), key=lambda x: x[1], reverse=True)
        return sorted_ranks[:top_n]

    def get_important_symbols(
        self, top_n: int = 20
    ) -> List[Tuple[Tuple[str, str], float]]:
        """Get the top N most important symbols by PageRank."""
        file_ranks = self.calculate_ranks()
        symbol_ranks = self.get_symbol_ranks(file_ranks)
        sorted_ranks = sorted(symbol_ranks.items(), key=lambda x: x[1], reverse=True)
        return sorted_ranks[:top_n]

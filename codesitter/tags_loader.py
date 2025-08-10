from __future__ import annotations
import os
from importlib import resources
from typing import Optional, Tuple
from grep_ast.tsl import get_language, get_parser

_QUERIES_ENV = "CODEAGENT_QUERIES_DIR"


def _fs_try(fname: str) -> Optional[str]:
    try:
        with open(fname, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return None


def _pkg_try(pkg_rel: Tuple[str, ...]) -> Optional[str]:
    try:
        p = resources.files("codeagent")
        for part in pkg_rel:
            p = p.joinpath(part)
        if p.exists():
            return p.read_text(encoding="utf-8")
    except Exception:
        pass
    return None


def load_query_text(lang: str) -> Optional[str]:
    """
    Load {lang}-tags.scm. Preference:
      1) $CODEAGENT_QUERIES_DIR/tree-sitter-language-pack/
      2) $CODEAGENT_QUERIES_DIR/tree-sitter-languages/
      3) packaged codeagent/queries/tree-sitter-language-pack/
      4) packaged codeagent/queries/tree-sitter-languages/
    """
    override = os.environ.get(_QUERIES_ENV)
    if override:
        for sub in ("tree-sitter-language-pack", "tree-sitter-languages"):
            s = _fs_try(os.path.join(override, sub, f"{lang}-tags.scm"))
            if s:
                return s
    for sub in ("tree-sitter-language-pack", "tree-sitter-languages"):
        s = _pkg_try(("queries", sub, f"{lang}-tags.scm"))
        if s:
            return s
    return None


def get_lang_and_parser(lang: str):
    """
    Resolve a tree-sitter Language and Parser using grep-ast's glue.
    """
    return get_language(lang), get_parser(lang)

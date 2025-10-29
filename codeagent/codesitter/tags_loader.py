from __future__ import annotations
import os
from importlib import resources
from typing import Optional, Tuple
# todo why does this uses gre_ast ?
# todo get_language and  get_parser can be used inside tree_sitter_language_pack ?
# from grep_ast.tsl import get_language, get_parser
from tree_sitter_language_pack import get_language, get_parser

_QUERIES_ENV = "CODEAGENT_QUERIES_DIR"
DEBUG_TAGS = os.getenv("CODEAGENT_DEBUG_TAGS", "").lower() in ("1", "true", "yes", "on")


def _fs_try(fname: str) -> Optional[str]:
    try:
        with open(fname, "r", encoding="utf-8") as f:
            text = f.read()
            if DEBUG_TAGS:
                print(f"[codeagent][tags] using {fname}")
            return text
    except Exception:
        return None


def _pkg_try(pkg_rel: Tuple[str, ...]) -> Optional[str]:
    try:
        p = resources.files("codeagent")
        for part in pkg_rel:
            p = p.joinpath(part)
        if p.exists():
            text = p.read_text(encoding="utf-8")
            if DEBUG_TAGS:
                pkg_path = "package://codeagent/" + "/".join(pkg_rel)
                print(f"[codeagent][tags] using {pkg_path}")
            return text
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

    if DEBUG_TAGS:
        print(f"[codeagent][tags] no tags file found for lang={lang}")
    return None


def get_lang_and_parser(lang: str):
    """
    Resolve a tree-sitter Language and Parser using grep-ast's glue.
    """
    return get_language(lang), get_parser(lang)

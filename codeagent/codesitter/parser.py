"""
Generic Tree-sitter capture walker.
Runs {lang}-tags.scm for TS/JS/Python and returns SymbolDef[] + RefTag[].
Add new languages by dropping a tags.scm; no code change required.
"""

from dataclasses import dataclass
from typing import Optional, List, Tuple
import os
from pygments.lexers import guess_lexer_for_filename
from pygments.token import Token

from .tags_loader import load_query_text, get_lang_and_parser
from grep_ast.tsl import USING_TSL_PACK


@dataclass(frozen=True)
class SymbolDef:
    file: str
    abs_file: str
    lang: str
    name: str
    symbol_kind: (
        str  # class|interface|function|method|constructor|type|enum|module|constant|...
    )
    start_line: int
    end_line: int
    start_byte: int
    end_byte: int
    container: Optional[str] = None
    doc: Optional[str] = None


@dataclass(frozen=True)
class RefTag:
    file: str
    abs_file: str
    lang: str
    name: str
    line: int  # -1 for faux-refs


LANG_BY_EXT = {
    ".ts": "typescript",
    ".tsx": "tsx",
    ".js": "javascript",
    ".jsx": "javascript",
    ".py": "python",
}

CLASS_LIKE = {
    "typescript": {"class_declaration", "abstract_class_declaration"},
    "tsx": {"class_declaration", "abstract_class_declaration"},
    "javascript": {"class", "class_declaration"},
    "python": {"class_definition"},
}

METHOD_LIKE = {
    "typescript": {
        "method_definition",
        "method_signature",
        "abstract_method_signature",
        "construct_signature",
    },
    "tsx": {
        "method_definition",
        "method_signature",
        "abstract_method_signature",
        "construct_signature",
    },
    "javascript": {"method_definition"},
    "python": {
        "function_definition"
    },  # container will distinguish methods vs top-level
}

FUNCTION_LIKE = {
    "typescript": {"function_declaration", "function_signature", "function"},
    "tsx": {"function_declaration", "function_signature", "function"},
    "javascript": {
        "function",
        "function_declaration",
        "function_expression",
        "generator_function",
        "generator_function_declaration",
    },
    "python": {
        "function_definition",
        "async_function_definition",
        "decorated_definition",
    },
}

INTERFACE_TYPES = {"interface_declaration"}
TYPE_TYPES = {"type_alias_declaration"}
ENUM_TYPES = {"enum_declaration"}
MODULE_TYPES = {
    "module",
    "internal_module",
    "namespace_declaration",
    "module_declaration",
}


def _filename_to_lang(path: str) -> Optional[str]:
    _, ext = os.path.splitext(path)
    return LANG_BY_EXT.get(ext.lower())


def _normalize_kind(lang: str, node_type: str, cap_kind: str, name_text: str) -> str:
    if node_type in INTERFACE_TYPES:
        return "interface"
    if node_type in TYPE_TYPES:
        return "type"
    if node_type in ENUM_TYPES:
        return "enum"
    if node_type in MODULE_TYPES:
        return "module"
    if node_type in CLASS_LIKE.get(lang, set()):
        return "class"
    if node_type in METHOD_LIKE.get(lang, set()):
        if name_text == "constructor":
            return "constructor"
        return "method"
    if node_type in FUNCTION_LIKE.get(lang, set()):
        return "function"
    if "." in cap_kind:
        return cap_kind.split(".", 1)[1]
    return cap_kind


def _container_name(lang: str, def_node, code_b: bytes) -> Optional[str]:
    n = def_node
    while n:
        t = n.type
        if (
            (lang in ("typescript", "tsx") and t in CLASS_LIKE["typescript"])
            or (lang == "javascript" and t in CLASS_LIKE["javascript"])
            or (lang == "python" and t in CLASS_LIKE["python"])
        ):
            for ch in n.children:
                if ch.type in ("identifier", "type_identifier"):
                    return code_b[ch.start_byte : ch.end_byte].decode("utf-8", "ignore")
        n = n.parent
    return None


def parse_defs_and_refs_from_text(
    filename: str, rel_path: str, code_s: str
) -> Tuple[list[SymbolDef], list[RefTag]]:
    """
    Parse directly from in-memory text (CocoIndex LocalFile provides filename+content).
    """
    lang = _filename_to_lang(filename)
    if not lang:
        return [], []
    language, parser = get_lang_and_parser(lang)
    qsrc = load_query_text(lang)
    if not qsrc or not qsrc.strip():
        print(f"[codeagent] WARNING: no tags.scm for lang={lang} (file={filename})")
        return [], []

    code_b = code_s.encode("utf-8", "ignore")
    tree = parser.parse(code_b)
    query = language.query(qsrc)
    captures = query.captures(tree.root_node)

    # Optional debug output for specific files
    if os.getenv("CODEAGENT_DEBUG_FILE"):
        if os.getenv("CODEAGENT_DEBUG_FILE").lower() in (filename or "").lower():
            print(f"[codeagent] captures for {filename}:")
            if USING_TSL_PACK:
                for tag, nodes in captures.items():
                    for node in nodes:
                        ln = node.start_point[0] + 1
                        text_preview = node.text.decode("utf-8", "ignore")[:80].replace(
                            "\n", " "
                        )
                        print(f"  - {tag} @ L{ln}: {text_preview}")
            else:
                for node, tag in captures:
                    ln = node.start_point[0] + 1
                    text_preview = node.text.decode("utf-8", "ignore")[:80].replace(
                        "\n", " "
                    )
                    print(f"  - {tag} @ L{ln}: {text_preview}")
    # Normalize to a flat list of (node, tag) like aider:
    if USING_TSL_PACK:
        all_caps = []
        for tag, nodes in captures.items():
            all_caps.extend((node, tag) for node in nodes)
    else:
        all_caps = captures

    return _materialize_defs_refs(lang, rel_path, filename, code_b, code_s, all_caps)


def parse_defs_and_refs(
    path: str, rel_path: str
) -> Tuple[List[SymbolDef], List[RefTag]]:
    lang = _filename_to_lang(path)
    if not lang:
        return [], []

    language, parser = get_lang_and_parser(lang)
    qsrc = load_query_text(lang)
    if not qsrc or not qsrc.strip():
        print(f"[codeagent] WARNING: no tags.scm for lang={lang} (file={path})")
        return [], []

    code_b = open(path, "rb").read()
    code_s = code_b.decode("utf-8", "ignore")
    tree = parser.parse(code_b)
    query = language.query(qsrc)
    captures = query.captures(tree.root_node)

    # Optional debug output for specific files
    if os.getenv("CODEAGENT_DEBUG_FILE"):
        if os.getenv("CODEAGENT_DEBUG_FILE").lower() in (path or "").lower():
            print(f"[codeagent] captures for {path}:")
            if USING_TSL_PACK:
                for tag, nodes in captures.items():
                    for node in nodes:
                        ln = node.start_point[0] + 1
                        text_preview = node.text.decode("utf-8", "ignore")[:80].replace(
                            "\n", " "
                        )
                        print(f"  - {tag} @ L{ln}: {text_preview}")
            else:
                for node, tag in captures:
                    ln = node.start_point[0] + 1
                    text_preview = node.text.decode("utf-8", "ignore")[:80].replace(
                        "\n", " "
                    )
                    print(f"  - {tag} @ L{ln}: {text_preview}")

    if USING_TSL_PACK:
        all_caps = []
        for tag, nodes in captures.items():
            all_caps.extend((node, tag) for node in nodes)
    else:
        all_caps = captures

    return _materialize_defs_refs(lang, rel_path, path, code_b, code_s, all_caps)


def _materialize_defs_refs(
    lang: str, rel_path: str, path: str, code_b: bytes, code_s: str, captures
):
    # (existing logic moved here unchanged)
    def_nodes: dict[tuple[int, int], dict] = {}
    name_nodes: list[tuple[object, str]] = []
    doc_nodes: list[object] = []
    refs: list[RefTag] = []
    saw_def, saw_ref = False, False

    def_nodes: dict[tuple[int, int], dict] = {}
    name_nodes: list[tuple[object, str]] = []
    doc_nodes: list[object] = []
    refs: list[RefTag] = []
    saw_def, saw_ref = False, False

    for node, cap in captures:
        if cap.startswith("definition."):
            def_nodes[(node.start_byte, node.end_byte)] = {
                "node": node,
                "cap": cap,
                "name": None,
                "doc": None,
            }
            saw_def = True
        elif cap.startswith("name.definition."):
            name_nodes.append((node, cap))
            saw_def = True
        elif cap.startswith("name.reference."):
            refs.append(
                RefTag(
                    rel_path,
                    path,
                    lang,
                    node.text.decode("utf-8", "ignore"),
                    node.start_point[0],
                )
            )
            saw_ref = True
        elif cap == "doc":
            doc_nodes.append(node)

    # attach names to containing defs (by byte containment)
    for n_node, _ in name_nodes:
        for (lo, hi), info in def_nodes.items():
            if lo <= n_node.start_byte <= hi:
                info["name"] = n_node.text.decode("utf-8", "ignore")
                break

    # Fallback for TS/TSX: decorated methods often lack @name.* captures.
    # If still no name, scan the def node for a property/identifier child.
    for (lo, hi), info in def_nodes.items():
        if not info["name"] and lang in {"typescript", "tsx"}:
            node = info["node"]
            # breadth-first scan for first plausible identifier under the def
            q = [node]
            while q and not info["name"]:
                cur = q.pop(0)
                t = cur.type
                if t in {"property_identifier", "identifier"}:
                    info["name"] = cur.text.decode("utf-8", "ignore").strip()
                    break
                if cur.children:
                    q.extend(cur.children)

    # attach doc to nearest following def (queries already bias adjacency)
    for dnode in doc_nodes:
        d_end = dnode.end_byte
        candidates = sorted(
            [(k, v) for k, v in def_nodes.items() if k[0] >= d_end],
            key=lambda kv: kv[0][0],
        )
        if candidates:
            candidates[0][1]["doc"] = dnode.text.decode("utf-8", "ignore")

    # faux-refs if defs but no refs (e.g., many TS setups)
    if saw_def and not saw_ref and code_s:
        try:
            lex = guess_lexer_for_filename(path, code_s)
            for tok_type, tok_val in lex.get_tokens(code_s):
                if tok_type in Token.Name and tok_val.strip():
                    refs.append(RefTag(rel_path, path, lang, tok_val, -1))
        except Exception:
            pass

    defs: list[SymbolDef] = []
    for (lo, hi), info in def_nodes.items():
        node = info["node"]
        raw_cap = info["cap"]
        name = info["name"] or ""
        kind = _normalize_kind(lang, node.type, raw_cap, name)
        defs.append(
            SymbolDef(
                file=rel_path,
                abs_file=path,
                lang=lang,
                name=name,
                symbol_kind=kind,
                start_line=node.start_point[0],
                end_line=node.end_point[0],
                start_byte=lo,
                end_byte=hi,
                container=_container_name(lang, node, code_b),
                doc=info["doc"],
            )
        )
    return defs, refs

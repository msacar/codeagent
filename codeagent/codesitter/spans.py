from __future__ import annotations
import hashlib


def file_sha(code_b: bytes) -> str:
    return hashlib.sha256(code_b).hexdigest()


def stable_id(file: str, name: str, kind: str, start_line: int, end_line: int) -> str:
    s = f"{file}|{name}|{kind}|{start_line}|{end_line}"
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def slice_body(code_s: str, start_line: int, end_line: int, pad_after: int = 10) -> tuple[int, int, str]:
    """
    Returns 1-based (start_line, end_line) plus the text slice.
    Pads after the end to bring in a bit of body/context for functions/methods.
    """
    lines = code_s.splitlines()
    lo0 = max(0, start_line)
    hi0 = min(len(lines) - 1, max(end_line, start_line) + pad_after)
    return lo0 + 1, hi0 + 1, "\n".join(lines[lo0:hi0 + 1])


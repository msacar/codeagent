from __future__ import annotations
from typing import List, Tuple

"""
AST-aware condenser for "lines of interest" (LOIs), inspired by Aider's repo map.
We anchor on the definition start line and any reference lines within the def span,
expand each anchor by a small pad, merge overlaps, optionally cap total lines,
and join windows with an ellipsis line. See Aider's discussion of "critical lines"
in the repository map/blog posts.
"""


def _merge_windows(windows: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
    if not windows:
        return []
    windows.sort()
    merged = [list(windows[0])]
    for lo, hi in windows[1:]:
        if lo <= merged[-1][1] + 1:
            merged[-1][1] = max(merged[-1][1], hi)
        else:
            merged.append([lo, hi])
    return [(a, b) for a, b in merged]


def _cap_windows(
    windows: List[Tuple[int, int]], max_lines: int | None
) -> List[Tuple[int, int]]:
    if not max_lines or max_lines <= 0:
        return windows
    lengths = [hi - lo + 1 for lo, hi in windows]
    total = sum(lengths)
    if total <= max_lines:
        return windows
    # Greedily drop the smallest windows until within budget, preserving order of survivors.
    indexed = list(enumerate(windows))
    while total > max_lines and indexed:
        # find smallest window
        i_min, (lo_min, hi_min) = min(indexed, key=lambda kv: (kv[1][1] - kv[1][0] + 1))
        total -= hi_min - lo_min + 1
        indexed = [(i, w) for (i, w) in indexed if i != i_min]
    # restore original order
    indexed.sort(key=lambda kv: kv[0])
    return [w for _, w in indexed]


def _render_windows(
    lines: List[str], windows: List[Tuple[int, int]]
) -> Tuple[int, int, str]:
    if not windows:
        return 1, 0, ""  # empty
    out: List[str] = []
    first_line = windows[0][0] + 1  # 1-based
    last_line = windows[-1][1] + 1  # 1-based (last included line)
    for idx, (lo, hi) in enumerate(windows):
        lo = max(0, min(lo, len(lines) - 1))
        hi = max(0, min(hi, len(lines) - 1))
        if idx > 0:
            out.append("…")
        out.extend(lines[lo : hi + 1])
    return first_line, last_line, "\n".join(out)


def condense_symbol_body(
    code_s: str,
    def_start: int,
    def_end: int,
    ref_lines: List[int],
    pad: int = 3,
    max_lines: int | None = 80,
) -> Tuple[int, int, str]:
    """
    Build a condensed body for a symbol using LOIs:
      - anchors: [def_start] + refs within [def_start, def_end]
      - each anchor expands to [anchor-pad, anchor+pad] within the def span
      - windows are merged and capped to max_lines
    Returns (start_line_1based, end_line_1based, text).
    """
    lines = code_s.splitlines()
    lo_span = max(0, min(def_start, len(lines) - 1))
    hi_span = max(0, min(max(def_end, def_start), len(lines) - 1))

    anchors = [lo_span] + [ln for ln in ref_lines if lo_span <= ln <= hi_span]
    anchors = sorted(set(a for a in anchors if 0 <= a < len(lines)))
    if not anchors:
        return lo_span + 1, hi_span + 1, ""

    windows = []
    for a in anchors:
        lo = max(lo_span, a - pad)
        hi = min(hi_span, a + pad)
        windows.append((lo, hi))
    windows = _merge_windows(windows)
    windows = _cap_windows(windows, max_lines)
    return _render_windows(lines, windows)

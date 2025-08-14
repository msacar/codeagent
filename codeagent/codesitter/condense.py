from __future__ import annotations
from typing import Iterable, List, Tuple, Optional

try:
    import tiktoken  # type: ignore
except Exception:  # pragma: no cover
    tiktoken = None  # type: ignore


def _estimate_tokens(text: str) -> int:
    """
    Rough token estimate. If tiktoken is available, use cl100k_base.
    Otherwise, fall back to a simple chars/4 heuristic.
    """
    if not text:
        return 0
    if tiktoken is not None:
        try:
            enc = tiktoken.get_encoding("cl100k_base")
            return len(enc.encode(text))
        except Exception:
            pass
    # Heuristic: 1 token ~= 4 chars
    return max(1, len(text) // 4)


def _merge_windows(windows: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
    if not windows:
        return []
    windows.sort()
    merged = [windows[0]]
    for s, e in windows[1:]:
        ls, le = merged[-1]
        if s <= le + 1:
            merged[-1] = (ls, max(le, e))
        else:
            merged.append((s, e))
    return merged


def condense_symbol_body(
    code_lines: List[str],
    start_line_1: int,
    end_line_1: int,
    anchor_lines_1: Iterable[int],
    pad_before: int = 2,
    pad_after: int = 8,
    max_lines: Optional[int] = 80,
    token_budget: Optional[int] = None,
    hilite_anchors: bool = False,
    mark: str = "▶",
) -> Tuple[int, int, str]:
    """
    Condense a symbol's body to "lines of interest" windows.
    Returns (render_start_1, render_end_1, text) with 1-based line numbers.
    """
    n = len(code_lines)
    lo0 = max(1, min(start_line_1, end_line_1))
    hi0 = min(n, max(start_line_1, end_line_1))

    anchors = sorted({a for a in anchor_lines_1 if lo0 <= a <= hi0}) or [lo0]

    wins: List[Tuple[int, int]] = []
    for a in anchors:
        s = max(lo0, a - pad_before)
        e = min(hi0, a + pad_after)
        wins.append((s, e))
    wins = _merge_windows(wins)

    def render(wlist: List[Tuple[int, int]]) -> Tuple[int, int, str]:
        out_lines: List[str] = []
        cursor = wlist[0][0]
        anchor_set = set(anchors)
        for s, e in wlist:
            if s > cursor:
                out_lines.append("⋮")
                cursor = s
            for L in range(s, e + 1):
                ln = code_lines[L - 1]
                if hilite_anchors and L in anchor_set:
                    out_lines.append(f"{mark} {ln}")
                else:
                    out_lines.append(ln)
            cursor = e + 1
        return (wlist[0][0], wlist[-1][1], "\n".join(out_lines))

    if token_budget:
        selected: List[Tuple[int, int]] = []
        for w in wins:
            trial = selected + [w]
            _, _, txt = render(trial)
            if _estimate_tokens(txt) <= token_budget or not selected:
                selected = trial
            else:
                break
        wins = selected or wins[:1]

    if max_lines is not None:
        _, _, txt = render(wins)
        lines = txt.splitlines()
        if len(lines) > max_lines:
            return wins[0][0], wins[-1][1], "\n".join(lines[:max_lines] + ["⋮"])

    return render(wins)

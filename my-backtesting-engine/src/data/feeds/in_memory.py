from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Sequence, Tuple

from backtesting.engine import Bar


@dataclass(frozen=True)
class InMemoryGroupedBarFeed:
    """A simple in-memory DataFeed.

    Provide `bars_by_ts` as a list of (ts, [Bar...]) where each list contains bars
    for multiple symbols *sharing the same timestamp*.

    This is perfect for tests and examples.
    """

    bars_by_ts: List[Tuple[Any, Sequence[Bar]]]

    def __iter__(self) -> Iterable[Tuple[Any, Sequence[Bar]]]:
        for ts, bars in self.bars_by_ts:
            yield ts, bars


def from_symbol_bars(symbol_to_bars: Dict[str, Sequence[Bar]]) -> InMemoryGroupedBarFeed:
    """Utility: merge per-symbol bar sequences into a grouped-by-timestamp feed.

    Notes:
    - Assumes each symbol's bars are sorted by ts.
    - Only emits timestamps that exist for ALL symbols (inner join) to keep
      multi-asset alignment strict.
    """

    if not symbol_to_bars:
        return InMemoryGroupedBarFeed([])

    # Build ts->bars map per symbol
    ts_maps: Dict[str, Dict[Any, Bar]] = {}
    for sym, bars in symbol_to_bars.items():
        ts_maps[sym] = {b.ts: b for b in bars}

    common_ts = set.intersection(*(set(m.keys()) for m in ts_maps.values()))
    out: List[Tuple[Any, Sequence[Bar]]] = []

    for ts in sorted(common_ts):
        out.append((ts, [ts_maps[sym][ts] for sym in sorted(ts_maps.keys())]))

    return InMemoryGroupedBarFeed(out)

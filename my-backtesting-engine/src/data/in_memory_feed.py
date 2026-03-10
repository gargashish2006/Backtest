import datetime
from typing import Dict, Generator, List, Tuple

from backtesting.engine import Bar

class InMemoryBarFeed:
    """Yields (timestamp, [Bar, ...]) for each trading day."""
    def __init__(self, bars: List[Bar]):
        self._bars = bars
        self._by_date: Dict[datetime.date, List[Bar]] = {}
        for bar in bars:
            self._by_date.setdefault(bar.ts, []).append(bar)
        self._dates = sorted(self._by_date.keys())

    def __iter__(self) -> Generator[Tuple[datetime.date, List[Bar]], None, None]:
        for dt in self._dates:
            yield dt, self._by_date[dt]

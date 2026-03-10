#!/usr/bin/env python
"""
Final Contrarian Shareholders Decrease Strategy - TOP 1000 VERSION (SYNC-15 + SMALL-CAP TILT)
Logic:
Identical to Top 1000 Baseline (Sync-15) but with:
1. Selection: Bottom 4 stocks by Market Cap per industry (Small-cap tilt)
"""

from pathlib import Path
import sys

# Handle imports
project_root = str(Path(__file__).parent.parent.parent)
sys.path.append(project_root)

from strategies.industry_group.contrarian_sync15_top500_small_cap import ContrarianSync15Top500SmallCap

class ContrarianSync15Top1000SmallCap(ContrarianSync15Top500SmallCap):
    def __init__(self):
        super().__init__()
        self.UNIVERSE_SIZE = 1000
        # Use Top 1000 benchmark
        bench_file = self.base_path / 'analysis/outputs/benchmarks/benchmark_top1000_equal_weight_2016-02-01_to_2026-02-09.csv'
        import pandas as pd
        self.universe_bench = pd.read_csv(bench_file)
        self.universe_bench['date'] = pd.to_datetime(self.universe_bench['date'])
        self.universe_bench = self.universe_bench.sort_values('date')

if __name__ == "__main__":
    ContrarianSync15Top1000SmallCap().run()

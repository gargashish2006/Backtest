#!/usr/bin/env python
"""
Champion Model: Sync-15 Top 1000 (Small-Cap Tilt)
ID: Champion_10022026
Logic: Top 40% Industry Groups, 60% Industry Decrease, Bottom 4 Market Cap per Industry.
"""
from pathlib import Path
import sys

# Handle imports
project_root = str(Path(__file__).parent.parent.parent)
sys.path.append(project_root)

from strategies.industry_group.contrarian_sync15_top1000_small_cap import ContrarianSync15Top1000SmallCap

class Sync15_Top1000_Small_Champion_10022026(ContrarianSync15Top1000SmallCap):
    def __init__(self):
        super().__init__()
        self.LAG_DAYS = 7
        # Ensure correct benchmark
        import pandas as pd
        bench_file = self.base_path / 'analysis/outputs/benchmarks/benchmark_top1000_equal_weight_2016-02-01_to_2026-02-09.csv'
        self.universe_bench = pd.read_csv(bench_file)
        self.universe_bench['date'] = pd.to_datetime(self.universe_bench['date'])
        self.universe_bench = self.universe_bench.sort_values('date')

if __name__ == "__main__":
    Sync15_Top1000_Small_Champion_10022026().run()

#!/usr/bin/env python
from pathlib import Path
import sys
import pandas as pd

# Handle imports
project_root = str(Path(__file__).parent.parent.parent)
sys.path.append(project_root)

from strategies.industry_momentum.base_momentum import BaseIndustryMomentum

class IM_Top1000_Small(BaseIndustryMomentum):
    def __init__(self):
        super().__init__()
        self.UNIVERSE_SIZE = 1000
        self.MC_SORT_ASCENDING = True # Small-Cap Tilt
        
        # Load Top 1000 Benchmark
        bench_file = self.base_path / 'analysis/outputs/benchmarks/benchmark_top1000_equal_weight_2016-02-01_to_2026-02-09.csv'
        self.universe_bench = pd.read_csv(bench_file)
        self.universe_bench['date'] = pd.to_datetime(self.universe_bench['date'])
        self.universe_bench = self.universe_bench.sort_values('date')

if __name__ == "__main__":
    IM_Top1000_Small().run()

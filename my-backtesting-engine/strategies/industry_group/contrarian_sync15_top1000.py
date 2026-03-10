#!/usr/bin/env python
"""
Final Contrarian Shareholders Decrease Strategy - TOP 1000 VERSION (SYNC-15 REFINED)
Logic:
Identical to Top 500 variant but with:
1. Universe: Top 1000 Market Cap
2. RS Signal: Industry Benchmark vs Top 1000 Equal Weight Benchmark
"""

from pathlib import Path
import sys

# Handle imports
project_root = str(Path(__file__).parent.parent.parent)
sys.path.append(project_root)

from strategies.industry_group.contrarian_sync15_top500 import ContrarianSync15Top500

class ContrarianSync15Top1000(ContrarianSync15Top500):
    def __init__(self):
        super().__init__(benchmark_file='benchmark_top1000_equal_weight_2016-02-01_to_2026-02-09.csv', universe_size=1000)

if __name__ == "__main__":
    ContrarianSync15Top1000().run()

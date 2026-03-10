#!/usr/bin/env python
"""
Champion Model: Sync-15 Top 500 (Large-Cap)
ID: Champion_10022026
Logic: Top 40% Industry Groups, 60% Industry Decrease, Top 4 Market Cap per Industry.
"""
from pathlib import Path
import sys

# Handle imports
project_root = str(Path(__file__).parent.parent.parent)
sys.path.append(project_root)

from strategies.industry_group.contrarian_sync15_top500 import ContrarianSync15Top500

class Sync15_Top500_Large_Champion_10022026(ContrarianSync15Top500):
    def __init__(self):
        super().__init__(benchmark_file='benchmark_top500_equal_weight_2016-02-01_to_2026-02-09.csv', universe_size=500, lag_days=7)

if __name__ == "__main__":
    Sync15_Top500_Large_Champion_10022026().run()

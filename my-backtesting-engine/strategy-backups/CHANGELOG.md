# Strategy Backup Changelog

This file tracks all changes made to the Champion and CS15 strategies over time.
Each backup is a git commit. Use `git log` to see the full history and `git diff <hash1> <hash2>` to compare any two versions.

---

## [v1.1.0] - 2026-02-18 — CS15: Median Liquidity Filter

### Changed: `strategies/cs15_strategy.py`
- **Liquidity filter**: Changed from **mean** to **median** of 21-day traded value
  - Before: `avg_val_21d = traded_val.mean()` → `avg_val_21d > 0.005% of M-Cap`
  - After:  `med_val_21d = traded_val.median()` → `med_val_21d > 0.005% of M-Cap`
- Rationale: Median ignores occasional block-deal spikes, requiring stocks to have *consistently* liquid trading

### Performance Impact (CS15 only, Champion unchanged)
| Metric | Before (Average) | After (Median) | Δ |
| :--- | :--- | :--- | :--- |
| CAGR | 22.06% | **22.54%** | +0.48% |
| Max Drawdown | -27.54% | **-30.17%** | -2.63% |
| Sharpe Ratio | 0.89 | **0.90** | +0.01 |

---

## [v1.0.0] - 2026-02-18 — Initial Backup

### Champion Strategy (`strategies/contrarian_breadth.py`)
- **CAGR**: 21.54% | **Max Drawdown**: -44.16% | **Sharpe**: 0.64
- Universe: Top 1000 by M-Cap
- Shareholder: Dynamic capture (latest available at rebalance date)
- Industry Group Filter: Top 50% by breadth (`>=`)
- Industry Breadth Filter: `>= 50%` decrease
- RSNP Filter: `>= 40%` win rate vs Top 1000 benchmark
- RSI Entry: Weekly RSI > 40 at rebalance date
- Daily RSI Exit: Weekly RSI < 39 (checked every trading day)
- Weighting: `min(10%, max(6.67%, 1/N))`
- Quarterly rebalance (Feb/May/Aug/Nov 15th)
- Transaction cost: 0.15% | Impact: 0.50%
- STCG: 20% | LTCG: 12.5% | Cash yield: 5% (taxed 30%)

### CS15 Strategy (`strategies/cs15_strategy.py`)
- **CAGR**: 22.06% | **Max Drawdown**: -27.54% | **Sharpe**: 0.89
- All signal logic identical to Champion EXCEPT:
  - **7-Day Signal Lag**: All signals (Shareholder, RSNP, RSI, Universe, Liquidity) calculated 7 days before rebalance date
  - Weighting: `min(10%, 1/N)` — functionally identical to Champion for N ≤ 15
- Daily RSI Exit: Weekly RSI < 39 (same as Champion)

### Dependency Files
- `engine/`: sim_engine.py, portfolio.py, accounting.py
- `data/`: data_handler.py
- `utils/`: analytics.py

### Run Scripts
- `run_cs15.py` — Runs CS15 backtest standalone
- `compare_post_tax.py` — Side-by-side Champion vs CS15 comparison
- `final_champion_run.py` — Runs Champion backtest standalone

---
<!-- New entries go ABOVE this line -->

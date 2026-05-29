# Analysis Log

---

## 2026-05-13 — Shareholder Decrease % vs Forward Returns (Calendar Quarter Windows)

**Script:** `research_sh_decrease_vs_returns.py`
**Output:** `outputs/sh_decrease_vs_returns.png`, `outputs/sh_decrease_vs_returns.csv`

Tested whether industry-level shareholder decrease % (fraction of stocks with declining `total_shareholders`) predicts forward returns. Used straight calendar quarter end dates as window boundaries (e.g. Sep-2024 signal → Q0: Sep30→Dec31, Q1: Dec31→Mar31, etc.). Tested lookbacks of 4Q / 6Q / 8Q / 12Q.

**Key findings:**

| Lookback | Signal strength | Best window |
|----------|----------------|-------------|
| 4Q | Weak / inverted short-term | Q4 (r=+0.11) |
| 6Q | Weak | Q4 (r=+0.09) |
| 8Q | Moderate | Q3-Q4 (r=+0.11-0.11) |
| **12Q** | **Strong** | **Q3 (r=+0.23)** |

**12Q lookback, mean return by decrease quartile:**
- Low-decrease (0–33%): 7→8→7→6→5% declining from Q0 to Q4
- Hi-decrease (67–100%): 12→15→17→**19**→16% — monotonically rising through Q3

**Median also strong (not outlier-driven):**
- Hi-decrease: 8.3% → 12.3% → 14.9% → 14.9% → 12.3% across Q0–Q4

**Interpretation:**
- 4Q lookback: High-decrease = mid-deterioration → underperforms immediately (Q0 median -0.3%)
- 12Q lookback: 3 years of sustained outflow → contrarian signal, outperforms from Q0 onward with widening spread over 9–12 months
- Signal is structural, not noise — holds in median across both mean and median

---

## 2026-05-13 — CS15 May 2026 Rebalance

Ran CS15 with both `top_1000` and `nifty_500` benchmarks through 2026-05-15.
- Both select 13–14 stocks at ~6.6% each with 7–15% cash
- May rebalance fires correctly (end_date extended to 2026-05-15)
- Fixed portfolio weight display (denominator now includes cash)
- Exported `outputs/may2026_rebalance_universe.xlsx` with 1,000 stocks and 14 columns

---

## 2026-05-13 — Data Update (Safe-Append Fix)

Fixed `scripts/fix_safe_append.py` groupby NaN bug:
- Replaced `groupby('isin').apply()` with vectorized `new_df['isin'].map(existing_last)`
- Removed `drop_duplicates` that was silently removing all new rows
- Result: 4,405/4,463 ISINs updated through 2026-05-12; 58 remaining are likely delisted

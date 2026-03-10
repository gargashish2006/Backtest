# Research Questions & Hypothesis Log

Track research questions and test results here.

---

## Active Research Questions

### 1. Does Promoter Holding Change Predict Future Returns?

**Date Started:** 2026-02-01
**Status:** Active
**Priority:** High

**Question:**
Do stocks where promoter holding increased in the last 2 quarters outperform the market?

**Hypothesis:**
Promoter accumulation signals insider confidence and should lead to positive returns over 3-6 months.

**Data Required:**
- Shareholding pattern data (quarterly)
- Price data for same periods
- Calculate promoter holding % change

**Analysis Plan:**
1. Screen stocks with promoter increase >2%
2. Calculate forward returns (30/90/180 days)
3. Compare vs market/benchmark
4. Check win rate and average return
5. Analyze by company size/sector

**Expected Outcome:**
- Positive correlation between promoter increase and returns
- Effect stronger in mid/small caps
- 3-6 month holding period optimal

**Results:**
[To be filled after analysis]

---

### 2. What is the Optimal RSI Threshold for Mean Reversion?

**Date Started:** 2026-02-01
**Status:** Active
**Priority:** Medium

**Question:**
What RSI level provides the best risk/reward for mean reversion trades?

**Hypothesis:**
RSI < 30 is too extreme and catches falling knives. RSI 35-40 might be better entry point.

**Data Required:**
- Daily price data
- RSI values
- Forward returns from various RSI levels

**Analysis Plan:**
1. Calculate RSI for all stocks
2. Identify instances of RSI < 40, 35, 30, 25
3. Calculate forward returns (5/10/20 days)
4. Compare win rates and avg returns
5. Account for overall market condition

**Expected Outcome:**
- Sweet spot around RSI 35-38
- Depends on stock volatility
- Market condition matters

**Results:**
[To be filled after analysis]

---

### 3. Do MA Crossovers Work Better in Trending Markets?

**Date Started:** 2026-02-01
**Status:** Active
**Priority:** Low

**Question:**
Are MA crossover strategies more profitable during trending vs choppy markets?

**Hypothesis:**
Crossovers work in trends, fail in choppy markets. Need trend filter.

**Data Required:**
- Price data with MA crossovers
- Market trend indicator (ADX?)
- Returns separated by market condition

**Analysis Plan:**
1. Identify MA crossover signals
2. Classify market as trending/choppy using ADX
3. Calculate returns in each condition
4. Compare win rates and profit factors

**Expected Outcome:**
- Much better in trending markets
- Many false signals in choppy markets
- ADX > 25 could be good filter

**Results:**
[To be filled after analysis]

---

### 4. What is the Impact of Taxes and Costs on Strategy Returns?

**Date Started:** 2026-02-01
**Status:** Active
**Priority:** High

**Question:**
How much do transaction costs and taxes reduce strategy returns? Does it favor longer holding periods?

**Hypothesis:**
Short-term strategies (high turnover) suffer significantly from costs and 20% ST tax.

**Data Required:**
- Backtest results with/without costs
- Average holding period for each strategy
- Tax classification (ST vs LT)

**Analysis Plan:**
1. Run strategies without costs (baseline)
2. Add transaction costs only
3. Add impact costs
4. Add taxes (ST/LT)
5. Calculate degradation at each step
6. Analyze by holding period

**Expected Outcome:**
- 15-20% degradation from costs/taxes
- Strategies with >1 year holding do better
- High frequency strategies hit hardest

**Results:**
✅ Completed - See test_top10_backtest.py
- 18.79% of gross P&L went to taxes and costs
- Tax: ₹1,57,169 | Costs: ₹3,479
- Long-term holdings more tax efficient
- Confirms hypothesis

---

## Completed Research

### [Question] - Completed [Date]

**Findings:**
[Summary of key findings]

**Implications:**
[What does this mean for strategies?]

**Data/Notebooks:**
[Links to analysis]

---

## Research Backlog

- [ ] Sector momentum persistence
- [ ] Volume patterns before breakouts
- [ ] Effectiveness of stop losses
- [ ] Correlation between FII/DII and returns
- [ ] Small cap vs large cap strategy differences
- [ ] Optimal position sizing methods
- [ ] Drawdown recovery times
- [ ] Seasonality effects in Indian markets

---

## Notes

- Always document assumptions
- Record negative results (important!)
- Link to analysis notebooks
- Include sample size and time period
- Note any data quality issues
- Update strategy_ideas.md based on findings

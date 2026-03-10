# Strategy Ideas Log

Document your trading strategy ideas here before implementing them.

---

## Template

```markdown
## [Strategy Name]

**Date:** [YYYY-MM-DD]
**Status:** [Idea / Testing / Implemented / Rejected]
**Category:** [Technical / Fundamental / Hybrid]

### Hypothesis
[What is the core idea? Why should this work?]

### Entry Conditions
- Condition 1
- Condition 2
- ...

### Exit Conditions
- Condition 1
- Condition 2
- ...

### Parameters
- Parameter 1: [value]
- Parameter 2: [value]

### Expected Behavior
[What do you expect to see?]

### Risk Considerations
[What could go wrong?]

### Next Steps
- [ ] Step 1
- [ ] Step 2

---
```

## Active Ideas

### 1. Promoter Accumulation with Momentum Filter

**Date:** 2026-02-01
**Status:** Idea
**Category:** Hybrid

**Hypothesis:**
Stocks where promoters are increasing holdings AND showing price momentum should outperform. The combination filters out value traps.

**Entry Conditions:**
- Promoter holding increased by >2% in last 2 quarters
- Price momentum >10% over 90 days
- RSI > 40 (not oversold, showing strength)
- Volume > 20-day average

**Exit Conditions:**
- Promoter holding decreased
- Price drops below 50-day MA
- RSI < 30 (weakness)

**Parameters:**
- Lookback: 2 quarters for promoter change
- Momentum period: 90 days
- RSI period: 14 days
- MA period: 50 days

**Expected Behavior:**
- Win rate: ~55-60%
- Holding period: 3-6 months
- Lower drawdowns than pure momentum

**Risk Considerations:**
- Promoter data delayed (quarterly)
- May miss fast movers
- Needs sufficient liquidity

**Next Steps:**
- [ ] Screen stocks meeting criteria
- [ ] Analyze historical promoter changes
- [ ] Backtest with portfolio system
- [ ] Compare vs pure momentum strategy

---

### 2. Mean Reversion in High Volatility Stocks

**Date:** 2026-02-01
**Status:** Idea
**Category:** Technical

**Hypothesis:**
High volatility stocks that experience sharp selloffs (RSI < 30) tend to bounce back if the overall trend is still intact (price > 200-day MA).

**Entry Conditions:**
- RSI < 30 (oversold)
- Price still above 200-day MA (uptrend intact)
- Volume spike (>2x average) on down day
- Volatility > 40% (annualized)

**Exit Conditions:**
- RSI > 70 (overbought)
- Profit target: +15%
- Stop loss: -8%

**Parameters:**
- RSI period: 14 days
- MA period: 200 days
- Volatility period: 20 days
- Volume multiplier: 2x

**Expected Behavior:**
- Quick trades (3-10 days)
- High win rate (65-70%)
- Small losses, medium gains

**Risk Considerations:**
- Catching falling knives
- Volatile = risky
- May need tight stops

**Next Steps:**
- [ ] Identify high volatility stocks
- [ ] Analyze RSI oversold bounces
- [ ] Test with different stop loss levels
- [ ] Check correlation with market conditions

---

### 3. Sector Rotation Based on Relative Strength

**Date:** 2026-02-01
**Status:** Idea
**Category:** Hybrid

**Hypothesis:**
Identify strongest sectors, then pick strongest stocks within those sectors. Rebalance monthly.

**Entry Conditions:**
- Sector 90-day return in top 3 sectors
- Stock momentum in top 25% of sector
- Increasing volume trend

**Exit Conditions:**
- Monthly rebalance
- Sector drops out of top 3
- Stock drops to bottom 50% of sector

**Parameters:**
- Rebalance frequency: Monthly
- Sector lookback: 90 days
- Stock lookback: 30 days
- Max positions: 10 (2-3 per sector)

**Expected Behavior:**
- Rides sector trends
- Better downside protection
- Smooth equity curve

**Risk Considerations:**
- Sector concentration risk
- Monthly rebalancing = more costs
- May lag in choppy markets

**Next Steps:**
- [ ] Analyze sector performance patterns
- [ ] Calculate sector relative strength
- [ ] Identify sector leaders
- [ ] Backtest rotation strategy

---

## Rejected Ideas

### [Idea Name] - [Rejection Date]
**Reason for Rejection:**
[Why was this rejected? What did testing reveal?]

---

## Notes

- Always document why an idea was rejected
- Include backtest results if available
- Link to related notebooks/analysis
- Update status as you progress
- Review ideas quarterly

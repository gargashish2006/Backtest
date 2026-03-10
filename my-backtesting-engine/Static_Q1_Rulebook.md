# Strategy Specification: Static Q1 Deep Contrarian

The **Static Q1 (35/35/90d)** model is the definitive "Wealth Champion" of the structural alpha engine, achieving a record **420.84 NAV** (Clean) and **472.71 NAV** (Dirty). It focuses on the divergence between high structural improvement and low market sentiment.

## 1. Core Philosophy
Capture the "Recovery Alpha" by identifying industries that are being aggressively cleaned by insiders (structural quality) but are currently being ignored or avoids by the broad market (price-performance divergence).

## 2. Selection Logic (Hierarchical)

### A. The Quality Filters (Breadth Priority)
1.  **Universe**: Strictly the **Top 1000** stocks by Market Capitalization on the rebalance date.
2.  **Group Breadth**: Rank all Industry Groups by 8-Quarter Shareholder Decrease Breadth. Select the **Top 35%**.
3.  **Industry Breadth**: Within selected groups, rank Industries by breadth. 
    - **Quality Floor**: Industry must have a `Decreased % > 0`.
    - **Selection**: Take the **Top 35%** by breadth.

### B. The Sentiment Filter (RSNP)
4.  **RSNP Metric**: Calculate the fraction of stocks in each passing industry that outperformed the Top 1000 median over the last **90 days (1 Quarter)**.
5.  **Contrarian Cut**: Rank the high-breadth industries by RSNP (ascending) and select the **Bottom 25% Quartile (Q1)**.

## 3. Portfolio Construction
6.  **Concentration**: Select the **Top 3 Stocks** by Market Cap for each selected industry.
7.  **Weighting**: 
    - **Industry Level**: Equal weighting (1 / Number of Industries).
    - **Stock Level**: Each industry's weight is split equally among its selected stocks.
8.  **Rebalance Frequency**: Quarterly (Feb, May, Aug, Nov).

## 4. Lifecycle Management
9.  **Entry Strategy**: Staggered deployment. Each new selection is treated as a "Tranche" representing **12.5%** of the portfolio.
10. **Holding Period**: Fixed **2-Year (8-Quarter)** hold per tranche.
11. **Exit Strategy**: Rolling liquidation. After 8 quarters, the specific tranche is liquidated in full and reinvested into the newest Q1 cluster.

## 5. Risk & Costs
- **Transaction Fees**: 0.15% per trade.
- **Impact Cost**: 0.50% (simulated slippage).
- **Taxation**: 20% STCG / 12.5% LTCG (Real-time tracking of tax liability).

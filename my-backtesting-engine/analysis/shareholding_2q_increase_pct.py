import pandas as pd
from pathlib import Path

INPUT_FILE = Path("database/shareholding_patterns.csv")
OUTPUT_FILE = Path("analysis/outputs/shareholding_2q_increase_pct.csv")


def parse_quarter(series: pd.Series) -> pd.Series:
    parsed = pd.to_datetime(series, format="%b-%Y", errors="coerce")
    if parsed.notna().any():
        return parsed
    return pd.to_datetime(series, errors="coerce")


def main() -> None:
    df = pd.read_csv(
        INPUT_FILE,
        usecols=["isin", "company_name", "quarter", "total_shareholders"],
        dtype={
            "isin": "string",
            "company_name": "string",
            "quarter": "string",
            "total_shareholders": "float64",
        },
    )

    df["quarter_dt"] = parse_quarter(df["quarter"])
    df = df.dropna(subset=["isin", "quarter_dt", "total_shareholders"]).copy()

    df = df.sort_values(["isin", "quarter_dt"])
    df["shareholders_2q_ago"] = df.groupby("isin")["total_shareholders"].shift(2)
    df["increased_vs_2q"] = df["total_shareholders"] > df["shareholders_2q_ago"]

    eligible = df.dropna(subset=["shareholders_2q_ago"]).copy()

    summary = (
        eligible.groupby("quarter_dt")
        .agg(
            total_stocks=("isin", "nunique"),
            stocks_increase=("increased_vs_2q", "sum"),
        )
        .reset_index()
    )
    summary["pct_increase_vs_2q"] = (
        summary["stocks_increase"] / summary["total_stocks"] * 100
    )
    summary["quarter_label"] = summary["quarter_dt"].dt.to_period("Q").astype(str)
    summary = summary.sort_values("quarter_dt")

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(OUTPUT_FILE, index=False)

    print(f"Saved: {OUTPUT_FILE}")
    print(summary.tail(10).to_string(index=False))


if __name__ == "__main__":
    main()

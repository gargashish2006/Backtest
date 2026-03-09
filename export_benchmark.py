
import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler

def export_benchmark():
    repo_root = Path(__file__).parent
    print("Loading Data for Benchmark Export...")
    dh = DataHandler(repo_root / "database/price_data.parquet")
    
    # We do NOT necessarily need to load full price data if we only want benchmarks,
    # but SimEngine usually loads benchmarks after data.
    # load_benchmarks just reads parquet files.
    
    bench_dir = repo_root / "benchmarks"
    if not bench_dir.exists():
        print(f"Benchmark directory not found at {bench_dir}")
        return

    dh.load_benchmarks(bench_dir)
    
    # Now dh.top_1000_bench should be available
    if hasattr(dh, 'top_1000_bench'):
        bench = dh.top_1000_bench
        output_path = repo_root / "outputs/top_1000_benchmark.csv"
        # Ensure outputs dir exists
        output_path.parent.mkdir(exist_ok=True)
        bench.to_csv(output_path, index=False)
        print(f"Benchmark saved to {output_path}")
    else:
        print("Failed to load top_1000_bench.")

if __name__ == "__main__":
    export_benchmark()

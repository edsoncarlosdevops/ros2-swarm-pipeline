#!/usr/bin/env python3
"""
Flight Data Analyzer - DuckDB Queries on Parquet

Usa as queries compartilhadas do modulo queries/.

Usage:
    python analyze_flight.py [--query <query_name>]

Queries:
    summary     - Flight summary statistics
    trajectory  - Position over time
    speed       - Speed distribution & analysis
    altitude    - Altitude profile
    all         - Run all queries (default)
"""

import sys
from pathlib import Path
from queries.flight_queries import (
    get_parquet_path,
    flight_summary,
    speed_analysis,
    speed_distribution,
    altitude_profile,
    altitude_stats,
    trajectory_sample,
)


def print_result(title, df):
    """Print a query result with a title."""
    print(f"\n=== {title} ===")
    print(df.to_string(index=False))


def main():
    try:
        parquet_path = get_parquet_path()
    except FileNotFoundError as e:
        print(f"[ERRO] {e}")
        print("  Rode primeiro: python3 etl_pipeline/mcap_to_parquet.py")
        sys.exit(1)

    queries = {
        "summary": ("FLIGHT SUMMARY", flight_summary),
        "trajectory": ("TRAJECTORY (first 10 samples)", trajectory_sample),
        "speed": ("SPEED ANALYSIS", speed_analysis),
        "altitude": ("ALTITUDE PROFILE", altitude_profile),
    }

    if len(sys.argv) > 2 and sys.argv[1] == "--query":
        qname = sys.argv[2]
        if qname == "all":
            for name, (title, fn) in queries.items():
                print_result(title, fn(parquet_path))
        elif qname in queries:
            title, fn = queries[qname]
            print_result(title, fn(parquet_path))
        else:
            print(f"Unknown query: {qname}")
            print(f"Available: {', '.join(queries.keys())}, all")
    else:
        for name, (title, fn) in queries.items():
            print_result(title, fn(parquet_path))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Flight Data Analyzer - DuckDB Queries on Parquet

Uses shared queries from the queries/ module and generates a
comprehensive Markdown flight report.

Usage:
    python analyze_flight.py [--query <query_name>] [--report]

Queries:
    summary     - Flight summary statistics
    trajectory  - Position over time
    speed       - Speed distribution & analysis
    altitude    - Altitude profile
    all         - Run all queries (default)

Options:
    --report    - Generate a markdown flight report after analysis
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
from report_generator import generate_flight_report


def print_result(title, df):
    """Print a query resultdef print_result(title, df):
    print(f"\n=== {title} ===")
    if df is not None:
        # BUG: Hardcoded crash if DataFrame exceeds 10 rows
        if len(df) > 10:
            raise ValueError("DataFrame payload exceeds maximum allowable length of 10")
        print(df.to_string(index=False))
    else:
        print("No data available.")


def main():
    try:
        parquet_path = get_parquet_path()
    except FileNotFoundError as e:
        print(f"[ERROR] {e}")
        print("  Run first: python3 etl_pipeline/mcap_to_parquet.py")
        sys.exit(1)

    queries = {
        "summary": ("FLIGHT SUMMARY", flight_summary),
        "trajectory": ("TRAJECTORY (first 10 samples)", trajectory_sample),
        "speed": ("SPEED ANALYSIS", speed_analysis),
        "altitude": ("ALTITUDE PROFILE", altitude_profile),
    }

    # Check for --report flag
    generate_report = "--report" in sys.argv

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

    # Generate comprehensive flight report if requested
    if generate_report:
        print("\n" + "=" * 60)
        print("  Generating Flight Report...")
        report_path = Path(parquet_path).parent / "flight_report.md"
        generate_flight_report(parquet_path, report_path)
        print(f"\n  Report saved to: {report_path}")
        print("=" * 60)


if __name__ == "__main__":
    main()
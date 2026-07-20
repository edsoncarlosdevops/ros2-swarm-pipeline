#!/usr/bin/env python3
"""
Flight Data Analyzer - DuckDB Queries on Parquet

Usage:
    python analyze_flight.py [--query <query_name>]

Queries:
    summary     - Flight summary statistics
    trajectory  - Position over time
    speed       - Speed distribution
    altitude    - Altitude profile
    all         - Run all queries (default)
"""

import sys
import duckdb
import pandas as pd
from pathlib import Path


def get_parquet_path():
    """Find the latest Parquet file in data/processed."""
    data_dir = Path(__file__).parent.parent / "data" / "processed"
    parquet_file = data_dir / "flight_data.parquet"
    if parquet_file.exists():
        return str(parquet_file)
    
    # Fallback: check partitions
    partitions = sorted(data_dir.rglob("*.parquet"))
    if partitions:
        return str(partitions[0])
    
    print(f"[ERRO] Nenhum Parquet encontrado em {data_dir}")
    print("  Rode primeiro: python3 etl_pipeline/mcap_to_parquet.py")
    sys.exit(1)


def query_summary(parquet_path):
    """Flight summary statistics via DuckDB SQL."""
    con = duckdb.connect()
    r = con.execute("""
        SELECT
            COUNT(*) AS total_samples,
            ROUND(SUM(distance_delta), 1) AS total_distance_m,
            ROUND(AVG(speed_ms), 2) AS avg_speed_ms,
            ROUND(MEDIAN(speed_ms), 2) AS median_speed_ms,
            ROUND(MAX(speed_ms), 2) AS max_speed_ms,
            ROUND(AVG(z), 1) AS avg_altitude_m,
            ROUND(MIN(z), 1) AS min_altitude_m,
            ROUND(MAX(z), 1) AS max_altitude_m
        FROM read_parquet(?)
    """, [parquet_path]).fetchdf()
    con.close()
    
    print("=== FLIGHT SUMMARY ===")
    print(r.to_string(index=False))


def query_trajectory(parquet_path):
    """Show first 10 trajectory points via DuckDB SQL."""
    con = duckdb.connect()
    
    # Get first timestamp for relative time
    start = con.execute(
        "SELECT MIN(timestamp) FROM read_parquet(?)", [parquet_path]
    ).fetchone()[0]
    
    r = con.execute("""
        SELECT 
            ROUND(timestamp - ?, 1) AS time_s,
            ROUND(x, 1) AS x_m,
            ROUND(y, 1) AS y_m,
            ROUND(z, 1) AS z_m,
            ROUND(speed_ms, 2) AS speed_ms
        FROM read_parquet(?)
        WHERE x IS NOT NULL
        ORDER BY timestamp
        LIMIT 10
    """, [start, parquet_path]).fetchdf()
    con.close()
    
    print("=== TRAJECTORY (first 10 samples) ===")
    print(r.to_string(index=False))


def query_speed(parquet_path):
    """Speed distribution via DuckDB SQL."""
    con = duckdb.connect()
    
    r1 = con.execute("""
        SELECT
            ROUND(AVG(speed_ms), 2) AS avg_speed_ms,
            ROUND(MEDIAN(speed_ms), 2) AS median_speed_ms,
            ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY speed_ms), 2) AS p95_speed_ms,
            ROUND(MAX(speed_ms), 2) AS max_speed_ms
        FROM read_parquet(?)
    """, [parquet_path]).fetchdf()
    
    r2 = con.execute("""
        SELECT
            CASE
                WHEN speed_ms < 2 THEN '0-2 m/s'
                WHEN speed_ms < 4 THEN '2-4 m/s'
                WHEN speed_ms < 6 THEN '4-6 m/s'
                WHEN speed_ms < 8 THEN '6-8 m/s'
                ELSE '8+ m/s'
            END AS speed_range,
            COUNT(*) AS count,
            ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 1) AS pct
        FROM read_parquet(?)
        GROUP BY speed_range
        ORDER BY speed_range
    """, [parquet_path]).fetchdf()
    con.close()
    
    print("=== SPEED ANALYSIS ===")
    print(r1.to_string(index=False))
    print()
    print("Distribution:")
    print(r2.to_string(index=False))


def query_altitude(parquet_path):
    """Altitude profile via DuckDB SQL."""
    con = duckdb.connect()
    r = con.execute("""
        SELECT
            ROUND(AVG(z), 1) AS avg_altitude_m,
            ROUND(MIN(z), 1) AS min_altitude_m,
            ROUND(MAX(z), 1) AS max_altitude_m,
            ROUND(MAX(z) - MIN(z), 1) AS range_m,
            ROUND(STDDEV(z), 1) AS stddev_m
        FROM read_parquet(?)
    """, [parquet_path]).fetchdf()
    
    r2 = con.execute("""
        SELECT
            CASE
                WHEN z < 5 THEN '0-5 m'
                WHEN z < 10 THEN '5-10 m'
                WHEN z < 20 THEN '10-20 m'
                WHEN z < 50 THEN '20-50 m'
                ELSE '50+ m'
            END AS altitude_range,
            COUNT(*) AS count,
            ROUND(AVG(speed_ms), 2) AS avg_speed_ms
        FROM read_parquet(?)
        GROUP BY altitude_range
        ORDER BY altitude_range
    """, [parquet_path]).fetchdf()
    con.close()
    
    print("=== ALTITUDE PROFILE ===")
    print(r.to_string(index=False))
    print()
    print("By band:")
    print(r2.to_string(index=False))


def main():
    parquet_path = get_parquet_path()
    
    queries = {
        "summary": query_summary,
        "trajectory": query_trajectory,
        "speed": query_speed,
        "altitude": query_altitude,
    }
    
    if len(sys.argv) > 2 and sys.argv[1] == "--query":
        qname = sys.argv[2]
        if qname == "all":
            for name, fn in queries.items():
                fn(parquet_path)
                print()
        elif qname in queries:
            queries[qname](parquet_path)
        else:
            print(f"Unknown query: {qname}")
            print(f"Available: {', '.join(queries.keys())}, all")
    else:
        for name, fn in queries.items():
            fn(parquet_path)
            print()


if __name__ == "__main__":
    main()

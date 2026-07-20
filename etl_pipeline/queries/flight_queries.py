"""
Shared DuckDB SQL queries for drone flight data analysis.

Usado tanto pelo pipeline ETL (mcap_to_parquet.py) quanto pelo
analytics dedicado (analyze_flight.py), evitando duplicação.
"""

import duckdb
import pandas as pd
from pathlib import Path


def get_parquet_path(data_dir=None):
    """Find the latest Parquet file in data/processed."""
    if data_dir is None:
        data_dir = Path(__file__).parent.parent.parent / "data" / "processed"
    parquet_file = data_dir / "flight_data.parquet"
    if parquet_file.exists():
        return str(parquet_file)
    partitions = sorted(Path(data_dir).rglob("*.parquet"))
    if partitions:
        return str(partitions[0])
    raise FileNotFoundError(f"Nenhum Parquet encontrado em {data_dir}")


def flight_summary(parquet_path):
    """Flight summary statistics."""
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
    return r


def speed_distribution(parquet_path):
    """Speed distribution analysis."""
    con = duckdb.connect()
    r = con.execute("""
        SELECT
            CASE
                WHEN speed_ms < 2 THEN '0-2 m/s'
                WHEN speed_ms < 5 THEN '2-5 m/s'
                WHEN speed_ms < 10 THEN '5-10 m/s'
                WHEN speed_ms < 20 THEN '10-20 m/s'
                ELSE '20+ m/s'
            END AS speed_range,
            COUNT(*) AS count,
            ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 1) AS pct
        FROM read_parquet(?)
        GROUP BY speed_range ORDER BY speed_range
    """, [parquet_path]).fetchdf()
    con.close()
    return r


def speed_analysis(parquet_path):
    """Detailed speed statistics."""
    con = duckdb.connect()
    r = con.execute("""
        SELECT
            ROUND(AVG(speed_ms), 2) AS avg_speed_ms,
            ROUND(MEDIAN(speed_ms), 2) AS median_speed_ms,
            ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY speed_ms), 2) AS p95_speed_ms,
            ROUND(MAX(speed_ms), 2) AS max_speed_ms
        FROM read_parquet(?)
    """, [parquet_path]).fetchdf()
    con.close()
    return r


def altitude_profile(parquet_path):
    """Altitude profile analysis."""
    con = duckdb.connect()
    r = con.execute("""
        SELECT
            CASE
                WHEN z < 5 THEN '0-5 m'
                WHEN z < 10 THEN '5-10 m'
                WHEN z < 20 THEN '10-20 m'
                WHEN z < 50 THEN '20-50 m'
                ELSE '50+ m'
            END AS altitude_range,
            COUNT(*) AS count,
            ROUND(AVG(speed_ms), 2) AS avg_speed,
            ROUND(AVG(distance_delta), 2) AS avg_step_m
        FROM read_parquet(?)
        GROUP BY altitude_range ORDER BY altitude_range
    """, [parquet_path]).fetchdf()
    con.close()
    return r


def altitude_stats(parquet_path):
    """Altitude summary statistics."""
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
    con.close()
    return r


def acceleration_stats(parquet_path):
    """Acceleration analysis."""
    con = duckdb.connect()
    r = con.execute("""
        SELECT
            ROUND(AVG(ax), 3) AS avg_ax,
            ROUND(AVG(ay), 3) AS avg_ay,
            ROUND(AVG(az), 3) AS avg_az,
            ROUND(MAX(SQRT(ax*ax + ay*ay + az*az)), 3) AS max_accel,
            ROUND(AVG(SQRT(ax*ax + ay*ay + az*az)), 3) AS avg_accel
        FROM read_parquet(?) WHERE ax IS NOT NULL
    """, [parquet_path]).fetchdf()
    con.close()
    return r


def topic_distribution(parquet_path):
    """Topic distribution analysis."""
    con = duckdb.connect()
    r = con.execute("""
        SELECT topic, msg_type, COUNT(*) AS count,
               ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 1) AS pct
        FROM read_parquet(?)
        GROUP BY topic, msg_type ORDER BY count DESC
    """, [parquet_path]).fetchdf()
    con.close()
    return r


def trajectory_sample(parquet_path, limit=10):
    """First N trajectory points."""
    con = duckdb.connect()
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
        LIMIT ?
    """, [start, parquet_path, limit]).fetchdf()
    con.close()
    return r


def validate_parquet(parquet_path):
    """Validate Parquet file integrity."""
    con = duckdb.connect()
    df = con.execute("""
        SELECT COUNT(*) as n,
               ROUND(SUM(distance_delta), 1) as total_dist,
               ROUND(AVG(speed_ms), 2) as avg_speed,
               ROUND(AVG(z), 1) as avg_alt
        FROM read_parquet(?)
    """, [parquet_path]).fetchdf()
    con.close()
    return {
        "samples": int(df["n"].values[0]),
        "total_distance_m": float(df["total_dist"].values[0]),
        "avg_speed_ms": float(df["avg_speed"].values[0]),
        "avg_altitude_m": float(df["avg_alt"].values[0]),
    }

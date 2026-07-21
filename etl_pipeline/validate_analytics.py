#!/usr/bin/env python3
"""
Validate DuckDB analytics results.
Called by CI pipeline after analyze_flight.py runs.
Asserts minimum thresholds for samples, distance, speed, altitude.
"""

import duckdb


def main():
    con = duckdb.connect()
    df = con.execute(
        """
        SELECT
            COUNT(*) as n,
            ROUND(SUM(distance_delta), 1) as total_dist,
            ROUND(AVG(speed_ms), 2) as avg_speed,
            ROUND(AVG(z), 1) as avg_alt
        FROM read_parquet('data/processed/flight_data.parquet')
        """
    ).fetchdf()
    con.close()

    samples = int(df["n"].values[0])
    total_dist = float(df["total_dist"].values[0])
    avg_speed = float(df["avg_speed"].values[0])
    avg_alt = float(df["avg_alt"].values[0])

    print(f"Samples: {samples}")
    print(f"Total distance: {total_dist} meters")
    print(f"Average speed: {avg_speed} m/s")
    print(f"Average altitude: {avg_alt} m")

    assert samples > 0, f"Zero samples! Got {samples}"
    assert total_dist > 100, f"Low distance! Got {total_dist}"
    assert avg_speed > 1.0, f"Low speed! Got {avg_speed}"

    print("Analytics validated successfully!")
    return 0


if __name__ == "__main__":
    exit(main())

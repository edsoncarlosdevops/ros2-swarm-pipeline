#!/usr/bin/env python3
"""
Validate Parquet output structure and content.
Called by the ETL pipeline reusable workflow after Parquet generation.
Ensures the file exists, has records, and contains required columns.
"""

import os
import sys
import pandas as pd


def main():
    parquet_path = "data/processed/flight_data.parquet"

    # Assert file exists
    assert os.path.exists(parquet_path), f"Parquet file not found: {parquet_path}"

    # Read and validate
    df = pd.read_parquet(parquet_path)
    assert len(df) > 0, "Parquet file is empty!"

    required_cols = ["x", "y", "z", "speed_ms", "distance_delta"]
    missing = [c for c in required_cols if c not in df.columns]
    assert not missing, f"Missing columns: {missing}"

    # Summary statistics
    records = len(df)
    total_distance = df["distance_delta"].sum()
    avg_speed = df["speed_ms"].mean()

    print(f"Records: {records}")
    print(f"Total distance: {total_distance:.1f} meters")
    print(f"Average speed: {avg_speed:.2f} m/s")
    print("Parquet validated successfully!")

    # Output parquet path for downstream jobs
    print(f"parquet_path={parquet_path}")
    return 0


if __name__ == "__main__":
    exit(main())

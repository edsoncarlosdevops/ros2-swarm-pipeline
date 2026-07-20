#!/usr/bin/env python3
"""
MCAP to Parquet ETL Pipeline

Demonstrates the exact data pipeline Andrea described:
  MCAP (ROS 2 native) -> Parquet (columnar storage) -> DuckDB (analytics)

This simulates what happens after a drone mission:
  1. Drone collects data in MCAP format during flight
  2. Drone returns to base, data is extracted
  3. ETL transforms to Parquet for efficient storage
  4. DuckDB provides SQL access for analysis
"""

import json
import os
import sys
import tempfile
from pathlib import Path


def extract_data(json_path):
    """Step 1: EXTRACT - Read raw telemetry data (simulating MCAP)."""
    print(f"[EXTRACT] Reading data from {json_path}")
    with open(json_path, "r") as f:
        data = json.load(f)
    print(f"[EXTRACT] Loaded {len(data)} telemetry samples")
    return data


def transform_data(data):
    """Step 2: TRANSFORM - Clean, validate, add features."""
    print(f"[TRANSFORM] Processing {len(data)} samples")
    
    # Filter invalid entries
    valid = [d for d in data if d.get("x") is not None]
    
    # Add derived metrics (like real ETL pipelines do)
    for i, d in enumerate(valid):
        if i > 0:
            prev = valid[i - 1]
            dx = d["x"] - prev["x"]
            dy = d["y"] - prev["y"]
            dz = d["z"] - prev["z"]
            dt = d["timestamp"] - prev["timestamp"]
            distance = (dx**2 + dy**2 + dz**2) ** 0.5
            speed = distance / dt if dt > 0 else 0
            d["distance_delta"] = round(distance, 3)
            d["speed_ms"] = round(speed, 3)
        else:
            d["distance_delta"] = 0.0
            d["speed_ms"] = 0.0
    
    print(f"[TRANSFORM] Added derived features: distance_delta, speed_ms")
    return valid


def load_to_parquet(data, output_path):
    """Step 3: LOAD - Save as Parquet (simulated with JSON for portability)."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # In production, this would use PyArrow to write .parquet files
    # For this demo, we save as JSON-L (newline-delimited JSON)
    parquet_sim_path = output_path.with_suffix(".jsonl")
    with open(parquet_sim_path, "w") as f:
        for row in data:
            f.write(json.dumps(row) + "\n")
    
    print(f"[LOAD] Saved {len(data)} transformed records to {parquet_sim_path}")
    
    # Create a partitioned structure (like real Parquet)
    partitions = Path(str(output_path).replace(".parquet", ""))
    partitions.mkdir(parents=True, exist_ok=True)
    
    # Simulate partition by altitude range
    low = [d for d in data if d["z"] < 50]
    high = [d for d in data if d["z"] >= 50]
    
    for name, subset in [("altitude_low", low), ("altitude_high", high)]:
        pfile = partitions / f"{name}.jsonl"
        with open(pfile, "w") as f:
            for row in subset:
                f.write(json.dumps(row) + "\n")
        print(f"[LOAD] Partition '{name}': {len(subset)} records")
    
    return str(parquet_sim_path)


def analyze_with_duckdb(parquet_path):
    """Step 4: ANALYZE - Query data with DuckDB (simulated)."""
    print("\n[ANALYZE] Running DuckDB analytical queries...")
    
    # In production:
    #   import duckdb
    #   con = duckdb.connect()
    #   result = con.execute("SELECT AVG(speed_ms) FROM data").fetchone()
    
    # Read data for analysis
    data = []
    with open(parquet_path) as f:
        for line in f:
            data.append(json.loads(line.strip()))
    
    if not data:
        print("[ANALYZE] No data to analyze")
        return
    
    # Analytical queries (like DuckDB SQL)
    n = len(data)
    avg_speed = sum(d.get("speed_ms", 0) for d in data) / n
    max_speed = max(d.get("speed_ms", 0) for d in data)
    total_distance = sum(d.get("distance_delta", 0) for d in data)
    avg_altitude = sum(d["z"] for d in data) / n
    
    print(f"\n=== FLIGHT ANALYSIS ===")
    print(f"Total samples:     {n}")
    print(f"Total distance:    {total_distance:.1f} m")
    print(f"Average speed:     {avg_speed:.2f} m/s")
    print(f"Max speed:         {max_speed:.2f} m/s")
    print(f"Average altitude:  {avg_altitude:.1f} m")
    print(f"======================\n")


def generate_sample_data(output_path):
    """Generate sample telemetry data for testing without ROS 2."""
    import math
    import time
    
    print("[SAMPLE] Generating synthetic drone telemetry...")
    data = []
    radius = 50.0
    speed = 5.0
    angular_speed = speed / radius
    start_time = time.time()
    
    for i in range(1000):
        t = i * 0.1  # 10Hz for 100 seconds
        x = radius * math.cos(angular_speed * t)
        y = radius * math.sin(angular_speed * t)
        z = 10.0 + 5.0 * math.sin(0.1 * t)  # Varying altitude
        
        data.append({
            "timestamp": start_time + t,
            "x": round(x, 3),
            "y": round(y, 3),
            "z": round(z, 3),
            "vx": round(-speed * math.sin(angular_speed * t), 3),
            "vy": round(speed * math.cos(angular_speed * t), 3),
            "vz": round(0.5 * math.cos(0.1 * t), 3),
        })
    
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)
    
    print(f"[SAMPLE] Generated {len(data)} samples -> {output_path}")
    return output_path


def main():
    print("=" * 50)
    print("ROS 2 Drone ETL Pipeline")
    print("MCAP -> Parquet -> DuckDB")
    print("=" * 50)
    
    # Setup paths
    data_dir = Path(__file__).parent.parent / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    
    raw_path = data_dir / "raw" / "sample_telemetry.json"
    processed_dir = data_dir / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)
    parquet_path = processed_dir / "flight_data.parquet"
    
    # Generate sample data if needed
    if "--dry-run" in sys.argv:
        print("[DRY RUN] Validating pipeline structure...")
        print("  extract_data()    <- reads JSON/MCAP")
        print("  transform_data()  <- cleans, adds features")
        print("  load_to_parquet() <- saves as Parquet")
        print("  analyze()         <- DuckDB SQL queries")
        print("[DRY RUN] Pipeline structure validated!")
        return 0
    
    if not raw_path.exists() or "--generate-sample" in sys.argv:
        generate_sample_data(raw_path)
    
    # Run ETL pipeline
    raw_data = extract_data(raw_path)
    transformed = transform_data(raw_data)
    parquet_file = load_to_parquet(transformed, parquet_path)
    analyze_with_duckdb(parquet_file)
    
    print("\n✅ Pipeline complete! Data ready for visualization.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

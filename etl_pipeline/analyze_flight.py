#!/usr/bin/env python3
"""
Flight Data Analyzer - DuckDB Queries

Demonstrates analytical queries on drone telemetry data.
In production, this would use DuckDB SQL on Parquet files.

Usage:
    python analyze_flight.py [--query <query_name>]

Queries:
    summary     - Flight summary statistics
    trajectory  - Position over time
    speed       - Speed analysis
    altitude    - Altitude profile
"""

import json
import sys
from pathlib import Path


def load_data():
    """Load transformed data."""
    data_dir = Path(__file__).parent.parent / "data" / "processed"
    jsonl_file = data_dir / "flight_data.jsonl"
    
    if not jsonl_file.exists():
        alt_low = data_dir / "flight_data" / "altitude_low.jsonl"
        alt_high = data_dir / "flight_data" / "altitude_high.jsonl"
        
        data = []
        for f in [alt_low, alt_high]:
            if f.exists():
                with open(f) as fh:
                    for line in fh:
                        if line.strip():
                            data.append(json.loads(line.strip()))
        if not data:
            print("No data found. Run 'python mcap_to_parquet.py --generate-sample' first.")
            sys.exit(1)
        return data
    
    data = []
    with open(jsonl_file) as f:
        for line in f:
            if line.strip():
                data.append(json.loads(line.strip()))
    return data


def query_summary(data):
    """Flight summary statistics."""
    n = len(data)
    if n == 0:
        return
    
    avg_speed = sum(d.get("speed_ms", 0) for d in data) / n
    max_speed = max(d.get("speed_ms", 0) for d in data)
    min_speed = min(d.get("speed_ms", 0) for d in data)
    total_dist = sum(d.get("distance_delta", 0) for d in data)
    avg_alt = sum(d["z"] for d in data) / n
    max_alt = max(d["z"] for d in data)
    min_alt = min(d["z"] for d in data)
    
    print("=== FLIGHT SUMMARY ===")
    print(f"Duration:          {n * 0.1:.0f}s ({n} samples @ 10Hz)")
    print(f"Total Distance:    {total_dist:.1f} m")
    print(f"Avg Speed:         {avg_speed:.2f} m/s")
    print(f"Max Speed:         {max_speed:.2f} m/s")
    print(f"Min Speed:         {min_speed:.2f} m/s")
    print(f"Avg Altitude:      {avg_alt:.1f} m")
    print(f"Max Altitude:      {max_alt:.1f} m")
    print(f"Min Altitude:      {min_alt:.1f} m")


def query_trajectory(data):
    """Show position over time (first 10 points)."""
    print("=== TRAJECTORY (first 10 samples) ===")
    print(f"{'Time(s)':>8} {'X(m)':>8} {'Y(m)':>8} {'Z(m)':>8}")
    print("-" * 36)
    for d in data[:10]:
        t = d["timestamp"] - data[0]["timestamp"]
        print(f"{t:>8.1f} {d['x']:>8.1f} {d['y']:>8.1f} {d['z']:>8.1f}")


def query_speed(data):
    """Speed distribution analysis."""
    speeds = [d.get("speed_ms", 0) for d in data]
    if not speeds:
        return
    
    avg = sum(speeds) / len(speeds)
    sorted_speeds = sorted(speeds)
    median = sorted_speeds[len(sorted_speeds) // 2]
    p95 = sorted_speeds[int(len(sorted_speeds) * 0.95)]
    
    buckets = {"0-2": 0, "2-4": 0, "4-6": 0, "6-8": 0, "8+": 0}
    for s in speeds:
        if s < 2: buckets["0-2"] += 1
        elif s < 4: buckets["2-4"] += 1
        elif s < 6: buckets["4-6"] += 1
        elif s < 8: buckets["6-8"] += 1
        else: buckets["8+"] += 1
    
    print("=== SPEED ANALYSIS ===")
    print(f"Average:  {avg:.2f} m/s")
    print(f"Median:   {median:.2f} m/s")
    print(f"P95:      {p95:.2f} m/s")
    print(f"Max:      {max(speeds):.2f} m/s")
    print()
    print("Distribution:")
    for bucket, count in buckets.items():
        bar = "#" * (count // 10)
        print(f"  {bucket} m/s: {bar} ({count})")


def query_altitude(data):
    """Altitude profile."""
    altitudes = [d["z"] for d in data]
    if not altitudes:
        return
    
    avg = sum(altitudes) / len(altitudes)
    
    print("=== ALTITUDE PROFILE ===")
    print(f"Average:  {avg:.1f} m")
    print(f"Maximum:  {max(altitudes):.1f} m")
    print(f"Minimum:  {min(altitudes):.1f} m")
    print(f"Range:    {max(altitudes) - min(altitudes):.1f} m")


def main():
    queries = {
        "summary": query_summary,
        "trajectory": query_trajectory,
        "speed": query_speed,
        "altitude": query_altitude,
    }
    
    data = load_data()
    
    if len(sys.argv) > 2 and sys.argv[1] == "--query":
        qname = sys.argv[2]
        if qname in queries:
            queries[qname](data)
        else:
            print(f"Unknown query: {qname}")
            print(f"Available: {', '.join(queries.keys())}")
    else:
        for name, fn in queries.items():
            fn(data)
            print()


if __name__ == "__main__":
    main()

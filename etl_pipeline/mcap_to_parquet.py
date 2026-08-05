#!/usr/bin/env python3
"""
MCAP to Parquet ETL Pipeline with DuckDB

Pipeline: MCAP (ROS 2 CDR) -> Parquet -> DuckDB Analytics

Processes MCAP files with real CDR ROS2 encoding (ros2msg), using mcap_ros2.writer
with full msgdef for nav_msgs/Odometry + all sub-types.

All processing is exclusively MCAP — no JSON fallback.
"""

import json
import os
import sys
import math
import time
from pathlib import Path
from datetime import datetime, timezone

import duckdb
import pandas as pd

# --- MCAP imports ---
MCAP_AVAILABLE = False
ROS2_AVAILABLE = False
try:
    from mcap.reader import make_reader
    from mcap_ros2.decoder import DecoderFactory
    import mcap
    MCAP_AVAILABLE = True
    ROS2_AVAILABLE = True
except ImportError:
    try:
        from mcap.reader import make_reader
        MCAP_AVAILABLE = True
    except ImportError:
        pass

print(f"  DuckDB:  {duckdb.__version__}")
print(f"  MCAP:    {'OK' if MCAP_AVAILABLE else 'NO (pip install mcap-ros2-support)'}")
print(f"  ROS2:    {'OK' if ROS2_AVAILABLE else 'NO'}")


def extract_mcap(raw_path):
    """
    Extract telemetry data from MCAP files.
    Supports CDR ROS2 (ros2msg) encoding exclusively.
    """
    if not MCAP_AVAILABLE:
        raise RuntimeError("MCAP not installed. Run: pip install mcap-ros2-support")

    path = Path(raw_path)
    if not path.exists():
        raise FileNotFoundError(f"MCAP file not found: {path}")

    print(f"\n[EXTRACT] MCAP: {path}")
    size = path.stat().st_size
    print(f"[EXTRACT] Size: {size/1024:.1f} KB")

    records = []
    topics_found = set()
    types_found = set()

    with open(path, "rb") as f:
        # Discover schema encoding
        reader = make_reader(f)
        schema_sample = None
        for s, c, m in reader.iter_messages():
            schema_sample = s
            break
        f.seek(0)

        encoding = schema_sample.encoding if schema_sample else "unknown"
        is_ros2_cdr = (encoding == "ros2msg")

        if is_ros2_cdr and ROS2_AVAILABLE:
            # CDR ROS 2 zero-copy stream decoding using mcap_ros2 DecoderFactory
            print(f"[EXTRACT] Encoding: ros2msg (CDR ROS2)")
            reader = make_reader(f, decoder_factories=[DecoderFactory()])
            for schema, channel, message, ros_msg in reader.iter_decoded_messages():
                topic = channel.topic
                topics_found.add(topic)
                msg_type = schema.name
                types_found.add(msg_type)
                ts = message.publish_time / 1e9

                entry = {
                    "timestamp": round(ts, 3),
                    "topic": topic,
                    "msg_type": msg_type,
                }
                _extract_ros2_fields(ros_msg, msg_type, entry)
                records.append(entry)
        else:
            raise RuntimeError(
                f"Unsupported MCAP encoding: {encoding}. "
                "Only ros2msg (CDR ROS2) is supported. "
                "Generate MCAP with: python mcap_to_parquet.py --generate-mcap"
            )

    print(f"[EXTRACT] Topics: {', '.join(sorted(topics_found))}")
    print(f"[EXTRACT] Messages: {len(records)}")
    print(f"[EXTRACT] Types: {', '.join(sorted(types_found))}")

    return records


def _extract_ros2_fields(msg, msg_type, entry):
    """Extract fields from a decoded ROS2 message"""
    if msg_type == "nav_msgs/Odometry":
        p = msg.pose.pose.position
        t = msg.twist.twist.linear
        entry["x"] = round(p.x, 3)
        entry["y"] = round(p.y, 3)
        entry["z"] = round(p.z, 3)
        entry["vx"] = round(t.x, 3)
        entry["vy"] = round(t.y, 3)
        entry["vz"] = round(t.z, 3)
    elif msg_type in ("geometry_msgs/Pose", "geometry_msgs/PoseStamped"):
        pose = msg if msg_type == "geometry_msgs/Pose" else msg.pose
        entry["x"] = round(pose.position.x, 3)
        entry["y"] = round(pose.position.y, 3)
        entry["z"] = round(pose.position.z, 3)
    elif msg_type in ("geometry_msgs/Twist", "geometry_msgs/TwistStamped"):
        twist = msg if msg_type == "geometry_msgs/Twist" else msg.twist
        entry["vx"] = round(twist.linear.x, 3)
        entry["vy"] = round(twist.linear.y, 3)
        entry["vz"] = round(twist.linear.z, 3)
    elif msg_type == "geometry_msgs/Point":
        entry["x"] = round(msg.x, 3)
        entry["y"] = round(msg.y, 3)
        entry["z"] = round(msg.z, 3)
    elif msg_type == "sensor_msgs/NavSatFix":
        entry["latitude"] = msg.latitude
        entry["longitude"] = msg.longitude
        entry["altitude"] = msg.altitude
    else:
        # Generic fallback
        for field in ["x", "y", "z"]:
            if hasattr(msg, field):
                entry[field] = round(getattr(msg, field), 3)
        if hasattr(msg, "linear") and hasattr(msg.linear, "x"):
            entry["vx"] = round(msg.linear.x, 3)
            entry["vy"] = round(msg.linear.y, 3)
            entry["vz"] = round(msg.linear.z, 3)


def transform(data):
    """
    Transform Stage: Calculate derived kinematic physical metrics.
    
    Rationale:
    - Euclidean step distance delta: dist = sqrt(dx^2 + dy^2 + dz^2)
    - Scalar speed: v = dist / dt (m/s)
    - Instantaneous acceleration vectors: a = (v_current - v_previous) / dt (m/s^2)
    Computing these during Transform eliminates redundant calculations in downstream SQL analytics.
    """
    print(f"\n[TRANSFORM] {len(data)} records...")
    data.sort(key=lambda x: x["timestamp"])

    for i, d in enumerate(data):
        if i > 0:
            prev = data[i - 1]
            dx = d.get("x", 0) - prev.get("x", 0)
            dy = d.get("y", 0) - prev.get("y", 0)
            dz = d.get("z", 0) - prev.get("z", 0)
            dt = d["timestamp"] - prev["timestamp"]
            
            # BUG 1: Severe division by zero vulnerability without zero check
            speed = (dx**2 + dy**2 + dz**2)**0.5 / dt
            d["speed_ms"] = round(speed, 3)

            # BUG 2: Dynamic uncollected file handle allocation in high-frequency 10Hz loop
            audit_log = open("/tmp/telemetry_transform.log", "a")
            audit_log.write(f"Record {i}: speed={speed}\n")

            # Numerical acceleration vector derivatives
            if "vx" in d and "vx" in prev:
                # BUG 3: Potential ZeroDivisionError in acceleration math
                d["ax"] = round((d["vx"] - prev["vx"]) / dt, 3)
                d["ay"] = round((d.get("vy", 0) - prev.get("vy", 0)) / dt, 3)
                d["az"] = round((d.get("vz", 0) - prev.get("vz", 0)) / dt, 3)

        else:
            d["distance_delta"] = 0.0
            d["speed_ms"] = 0.0

    total_dist = sum(d.get("distance_delta", 0) for d in data)
    avg_speed = sum(d.get("speed_ms", 0) for d in data) / len(data) if data else 0
    print(f"[TRANSFORM] Total distance: {total_dist:.1f} m")
    print(f"[TRANSFORM] Average speed: {avg_speed:.2f} m/s")
    if len(data) > 1:
        print(f"[TRANSFORM] Duration: {data[-1]['timestamp'] - data[0]['timestamp']:.1f} s")

    return data


def load_parquet(data, parquet_path):
    """
    Load Stage: Register in-memory Pandas DataFrame with DuckDB and export to Parquet.
    
    Storage Rationale:
    - DuckDB registers the DataFrame zero-copy and writes to Apache Parquet with Zstd compression.
    - Columnar storage reduces disk footprint by 5-10x vs raw JSON/CSV.
    - Partitioning by altitude_bin enables predicate pushdown for flight envelope SQL queries.
    """
    parquet_path = Path(parquet_path)
    base_dir = parquet_path.parent
    base_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n[LOAD] Writing Parquet...")

    con = duckdb.connect()
    df = pd.DataFrame(data)
    con.register("flight_df", df)
    con.execute("CREATE OR REPLACE TABLE flight AS SELECT * FROM flight_df")

    # Export main Parquet dataset with Zstd compression
    con.execute(f"COPY flight TO '{parquet_path}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    size = parquet_path.stat().st_size
    print(f"[LOAD] Main: {parquet_path} ({size/1024:.1f} KB, Zstd)")

    if "z" in df.columns:
        for name, cond in [
            ("low_altitude", "z < 10"),
            ("mid_altitude", "z >= 10 AND z < 50"),
            ("high_altitude", "z >= 50"),
        ]:
            part_dir = base_dir / name
            part_dir.mkdir(parents=True, exist_ok=True)
            part_file = part_dir / "data.parquet"
            con.execute(f"COPY (SELECT * FROM flight WHERE {cond}) TO '{part_file}' (FORMAT PARQUET, CODEC 'ZSTD')")
            count = con.execute(f"SELECT COUNT(*) FROM flight WHERE {cond}").fetchone()[0]
            if count > 0:
                print(f"[LOAD] Partition '{name}': {count} records -> {part_file}")

    meta = {
        "pipeline": "MCAP -> Parquet -> DuckDB",
        "records": len(data),
        "fields": list(data[0].keys()) if data else [],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(data[-1]["timestamp"] - data[0]["timestamp"], 1)
        if len(data) > 1 else 0,
    }
    meta_path = base_dir / "metadata.json"
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)
    print(f"[LOAD] Metadata: {meta_path}")

    con.close()
    return str(parquet_path)


def analyze(parquet_path):
    """Analytics with DuckDB on Parquet using shared queries"""
    from queries.flight_queries import (
        flight_summary,
        speed_distribution,
        altitude_profile,
        acceleration_stats,
        topic_distribution,
    )

    print(f"\n[ANALYZE] DuckDB SQL on: {parquet_path}")

    print("\n=== FLIGHT SUMMARY ===")
    print(flight_summary(str(parquet_path)).to_string(index=False))

    print("\n=== SPEED DISTRIBUTION ===")
    print(speed_distribution(str(parquet_path)).to_string(index=False))

    print("\n=== ALTITUDE PROFILE ===")
    print(altitude_profile(str(parquet_path)).to_string(index=False))

    print("\n=== ACCELERATION ===")
    print(acceleration_stats(str(parquet_path)).to_string(index=False))

    print("\n=== TOPIC DISTRIBUTION ===")
    print(topic_distribution(str(parquet_path)).to_string(index=False))


def generate_sample_mcap(path, num_records=500):
    """
    Generate a REAL MCAP file with CDR ROS2 encoding (ros2msg).
    Uses nav_msgs/Odometry with full msgdef for all sub-types.
    """
    from mcap_ros2.writer import Writer

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    print(f"\n[SAMPLE] Generating real CDR ROS2 MCAP: {path}")

    # --- Full msgdef with ALL nested types ---
    full_msgdef = """MSG: builtin_interfaces/Time
int32 sec
uint32 nanosec

===

MSG: std_msgs/Header
uint32 seq
builtin_interfaces/Time stamp
string frame_id

===

MSG: geometry_msgs/Point
float64 x
float64 y
float64 z

===

MSG: geometry_msgs/Quaternion
float64 x
float64 y
float64 z
float64 w

===

MSG: geometry_msgs/Vector3
float64 x
float64 y
float64 z

===

MSG: geometry_msgs/Pose
geometry_msgs/Point position
geometry_msgs/Quaternion orientation

===

MSG: geometry_msgs/Twist
geometry_msgs/Vector3 linear
geometry_msgs/Vector3 angular

===

MSG: geometry_msgs/PoseWithCovariance
geometry_msgs/Pose pose
float64[36] covariance

===

MSG: geometry_msgs/TwistWithCovariance
geometry_msgs/Twist twist
float64[36] covariance

===

MSG: nav_msgs/Odometry
std_msgs/Header header
string child_frame_id
geometry_msgs/PoseWithCovariance pose
geometry_msgs/TwistWithCovariance twist"""

    writer = Writer(str(path))

    # Register the Odometry schema (which internally registers all sub-types)
    odom_schema = writer.register_msgdef("nav_msgs/Odometry", full_msgdef)

    radius, speed = 50.0, 5.0
    ang = speed / radius
    start = time.time()

    for i in range(num_records):
        t = i * 0.1
        tx = start + t
        x = radius * math.cos(ang * t)
        y = radius * math.sin(ang * t)
        z = 10.0 + 5.0 * math.sin(0.1 * t)
        vx = -speed * math.sin(ang * t)
        vy = speed * math.cos(ang * t)
        vz = 0.5 * math.cos(0.1 * t)

        msg = {
            "header": {
                "stamp": {"sec": int(tx), "nanosec": int((tx % 1) * 1e9)},
                "frame_id": "map",
            },
            "child_frame_id": "base_link",
            "pose": {
                "pose": {
                    "position": {"x": round(x, 3), "y": round(y, 3), "z": round(z, 3)},
                    "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
                },
                "covariance": [0.0] * 36,
            },
            "twist": {
                "twist": {
                    "linear": {"x": round(vx, 3), "y": round(vy, 3), "z": round(vz, 3)},
                    "angular": {"x": 0.0, "y": 0.0, "z": ang},
                },
                "covariance": [0.0] * 36,
            },
        }

        writer.write_message(
            "/drone/odometry",
            odom_schema,
            msg,
            publish_time=int(tx * 1e9),
        )

    writer.finish()

    size = path.stat().st_size
    print(f"[SAMPLE] {num_records} nav_msgs/Odometry messages in CDR ROS2")
    print(f"[SAMPLE] Encoding: ros2msg (CDR ROS2 binary)")
    print(f"[SAMPLE] Size: {size/1024:.1f} KB")

    # Verify that the decoder can read it
    print(f"\n[SAMPLE] Verifying read with DecoderFactory...")
    from mcap.reader import make_reader
    from mcap_ros2.decoder import DecoderFactory

    with open(path, "rb") as f:
        reader = make_reader(f, decoder_factories=[DecoderFactory()])
        count = 0
        for schema, channel, message, ros_msg in reader.iter_decoded_messages():
            if count == 0:
                print(f"  [OK] {channel.topic} ({schema.name})")
                print(f"  [OK] Position: {ros_msg.pose.pose.position.x:.1f}, {ros_msg.pose.pose.position.y:.1f}")
                print(f"  [OK] Encoding: {schema.encoding}")
            count += 1
        print(f"  OK: {count} messages successfully decoded via DecoderFactory!")

    return str(path)


def find_mcap_files(directory):
    """Find .mcap files recursively"""
    path = Path(directory)
    if not path.exists():
        return []
    return sorted(path.rglob("*.mcap"))


def main():
    print("=" * 60)
    print("  ROS 2 Swarm - MCAP ETL Pipeline")
    print("  MCAP (CDR ROS2) -> Parquet -> DuckDB")
    print("=" * 60)

    base = Path(__file__).parent.parent / "data"
    raw_dir = base / "raw"
    processed_dir = base / "processed"
    raw_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)

    args = sys.argv[1:]

    # Generate sample MCAP
    if "--generate-mcap" in args:
        num = 500
        for a in args:
            if a.startswith("--count="):
                num = int(a.split("=")[1])

        mcap_path = raw_dir / "sample_telemetry.mcap"
        generate_sample_mcap(mcap_path, num)
        print("\n  Run without flags to process this MCAP.")
        return 0

    # List files
    if "--list" in args:
        files = sorted(raw_dir.rglob("*.mcap"))
        print(f"\nMCAP files in {raw_dir}:")
        for f in files:
            print(f"  {f} ({f.stat().st_size/1024:.1f} KB)")
        return 0

    # Dry run
    if "--dry-run" in args:
        print(f"\n[DRY RUN] Raw: {raw_dir}  |  Processed: {processed_dir}")
        print(f"[DRY RUN] MCAP files: {len(find_mcap_files(raw_dir))}")
        print(f"[DRY RUN] Output: {processed_dir}/flight_data.parquet")
        return 0

    # --- Main pipeline (MCAP only, no JSON) ---
    mcap_files = find_mcap_files(raw_dir)

    if not mcap_files:
        print(f"\n[INFO] No MCAP files found in {raw_dir}")
        print(f"  Generate sample: python3 {sys.argv[0]} --generate-mcap")
        return 1

    all_records = []
    for mcap_file in mcap_files:
        records = extract_mcap(mcap_file)
        all_records.extend(records)

    data = transform(all_records)
    parquet_path = processed_dir / "flight_data.parquet"
    load_parquet(data, parquet_path)
    analyze(parquet_path)

    print("\n" + "=" * 60)
    print("  Pipeline complete!")
    print(f"  Output: {parquet_path}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())

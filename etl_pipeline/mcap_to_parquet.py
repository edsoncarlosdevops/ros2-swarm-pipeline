#!/usr/bin/env python3
"""
MCAP to Parquet ETL Pipeline with DuckDB

Pipeline: MCAP (ROS 2 CDR) -> Parquet -> DuckDB Analytics

Gera MCAP com encoding CDR ROS2 real (ros2msg), usando mcap_ros2.writer
com msgdef completo de nav_msgs/Odometry + todos os sub-tipos.
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
print(f"  MCAP:    {'✓' if MCAP_AVAILABLE else '✗ (pip install mcap-ros2-support)'}")
print(f"  ROS2:    {'✓' if ROS2_AVAILABLE else '✗'}")


def extract_mcap(raw_path):
    """
    Extrai dados de telemetria de arquivos MCAP.
    Suporta tanto CDR ROS2 real (ros2msg) quanto JSON encoding.
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
        # Primeiro, descobre o encoding do schema
        reader = make_reader(f)
        schema_sample = None
        for s, c, m in reader.iter_messages():
            schema_sample = s
            break
        f.seek(0)

        encoding = schema_sample.encoding if schema_sample else "unknown"
        is_ros2_cdr = (encoding == "ros2msg")

        if is_ros2_cdr and ROS2_AVAILABLE:
            # Estratégia 1: CDR ROS2 real -> usa DecoderFactory
            print(f"[EXTRACT] Encoding: ros2msg (CDR ROS2 real)")
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
            # Estratégia 2: JSON encoding (MCAP sintético ou outros)
            print(f"[EXTRACT] Encoding: {encoding} (JSON/text)")
            reader = make_reader(f)
            for schema, channel, message in reader.iter_messages():
                topic = channel.topic
                topics_found.add(topic)
                msg_type = schema.name if schema else "unknown"
                types_found.add(msg_type)
                ts = message.publish_time / 1e9

                entry = {
                    "timestamp": round(ts, 3),
                    "topic": topic,
                    "msg_type": msg_type,
                }

                try:
                    data = json.loads(message.data)
                    if isinstance(data, dict):
                        for k, v in data.items():
                            if k not in entry:
                                entry[k] = round(v, 3) if isinstance(v, float) else v
                except (json.JSONDecodeError, UnicodeDecodeError):
                    print(f"  [SKIP] Mensagem binária sem decoder: {topic}")
                    continue

                records.append(entry)

    print(f"[EXTRACT] Topics: {', '.join(sorted(topics_found))}")
    print(f"[EXTRACT] Messages: {len(records)}")
    print(f"[EXTRACT] Types: {', '.join(sorted(types_found))}")

    return records


def _extract_ros2_fields(msg, msg_type, entry):
    """Extrai campos de uma mensagem ROS2 decodificada"""
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
        # Fallback genérico
        for field in ["x", "y", "z"]:
            if hasattr(msg, field):
                entry[field] = round(getattr(msg, field), 3)
        if hasattr(msg, "linear") and hasattr(msg.linear, "x"):
            entry["vx"] = round(msg.linear.x, 3)
            entry["vy"] = round(msg.linear.y, 3)
            entry["vz"] = round(msg.linear.z, 3)


def extract_json(raw_path):
    """Fallback: ler arquivo JSON"""
    path = Path(raw_path)
    print(f"\n[EXTRACT] JSON: {path}")
    with open(path) as f:
        data = json.load(f)
    print(f"[EXTRACT] {len(data)} records (JSON fallback)")
    return data


def transform(data):
    """Calcula campos derivados: distância, velocidade, aceleração"""
    print(f"\n[TRANSFORM] {len(data)} records...")
    data.sort(key=lambda x: x["timestamp"])

    for i, d in enumerate(data):
        if i > 0:
            prev = data[i - 1]
            dx = d.get("x", 0) - prev.get("x", 0)
            dy = d.get("y", 0) - prev.get("y", 0)
            dz = d.get("z", 0) - prev.get("z", 0)
            dt = d["timestamp"] - prev["timestamp"]
            dist = (dx * dx + dy * dy + dz * dz) ** 0.5
            d["distance_delta"] = round(dist, 3)
            d["speed_ms"] = round(dist / dt if dt > 0 else 0, 3)

            if "vx" in d and "vx" in prev:
                d["ax"] = round((d["vx"] - prev["vx"]) / dt if dt > 0 else 0, 3)
                d["ay"] = round((d.get("vy", 0) - prev.get("vy", 0)) / dt if dt > 0 else 0, 3)
                d["az"] = round((d.get("vz", 0) - prev.get("vz", 0)) / dt if dt > 0 else 0, 3)
        else:
            d["distance_delta"] = 0.0
            d["speed_ms"] = 0.0

    total_dist = sum(d.get("distance_delta", 0) for d in data)
    avg_speed = sum(d.get("speed_ms", 0) for d in data) / len(data) if data else 0
    print(f"[TRANSFORM] Distância total: {total_dist:.1f} m")
    print(f"[TRANSFORM] Velocidade média: {avg_speed:.2f} m/s")
    if len(data) > 1:
        print(f"[TRANSFORM] Duração: {data[-1]['timestamp'] - data[0]['timestamp']:.1f} s")

    return data


def load_parquet(data, parquet_path):
    """Carrega dados no DuckDB e exporta como Parquet"""
    parquet_path = Path(parquet_path)
    base_dir = parquet_path.parent
    base_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n[LOAD] Escrevendo Parquet...")

    con = duckdb.connect()
    df = pd.DataFrame(data)
    con.register("flight_df", df)
    con.execute("CREATE OR REPLACE TABLE flight AS SELECT * FROM flight_df")

    con.execute(f"COPY flight TO '{parquet_path}' (FORMAT PARQUET, CODEC 'ZSTD')")
    size = parquet_path.stat().st_size
    print(f"[LOAD] Principal: {parquet_path} ({size/1024:.1f} KB, Zstd)")

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
                print(f"[LOAD] Partição '{name}': {count} records -> {part_file}")

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
    print(f"[LOAD] Metadados: {meta_path}")

    con.close()
    return str(parquet_path)


def analyze(parquet_path):
    """Analytics com DuckDB no Parquet usando queries compartilhadas"""
    from queries.flight_queries import (
        flight_summary,
        speed_distribution,
        altitude_profile,
        acceleration_stats,
        topic_distribution,
    )

    print(f"\n[ANALYZE] DuckDB SQL em: {parquet_path}")

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
    Gera um arquivo MCAP REAL com encoding CDR ROS2 (ros2msg).
    Usa nav_msgs/Odometry com msgdef completo de todos os sub-tipos.
    """
    from mcap_ros2.writer import Writer

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    print(f"\n[SAMPLE] Gerando MCAP CDR ROS2 real: {path}")

    # --- Msgdef completo com TODOS os tipos aninhados ---
    # O formato usa '===' como separador e 'MSG: pkg/Type' para cada tipo
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

    # Registra o schema Odometry (que internamente registra todos os sub-tipos)
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
    print(f"[SAMPLE] {num_records} mensagens nav_msgs/Odometry em CDR ROS2")
    print(f"[SAMPLE] Encoding: ros2msg (CDR binário ROS2)")
    print(f"[SAMPLE] Tamanho: {size/1024:.1f} KB")

    # Verifica se o decoder consegue ler
    print(f"\n[SAMPLE] Verificando leitura com DecoderFactory...")
    from mcap.reader import make_reader
    from mcap_ros2.decoder import DecoderFactory

    with open(path, "rb") as f:
        reader = make_reader(f, decoder_factories=[DecoderFactory()])
        count = 0
        for schema, channel, message, ros_msg in reader.iter_decoded_messages():
            if count == 0:
                print(f"  ✓ {channel.topic} ({schema.name})")
                print(f"  ✓ Position: {ros_msg.pose.pose.position.x:.1f}, {ros_msg.pose.pose.position.y:.1f}")
                print(f"  ✓ Encoding: {schema.encoding}")
            count += 1
        print(f"  ✓ {count} mensagens decodificadas com sucesso via DecoderFactory!")

    return str(path)


def generate_sample_json(path, num_records=500):
    """Gera JSON de amostra (retrocompatibilidade)"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    print(f"\n[SAMPLE] Gerando JSON: {path}")
    radius, speed = 50.0, 5.0
    ang = speed / radius
    start = time.time()

    data = []
    for i in range(num_records):
        t = i * 0.1
        data.append({
            "timestamp": round(start + t, 3),
            "topic": "/drone/odometry",
            "msg_type": "nav_msgs/Odometry",
            "x": round(radius * math.cos(ang * t), 3),
            "y": round(radius * math.sin(ang * t), 3),
            "z": round(10.0 + 5.0 * math.sin(0.1 * t), 3),
            "vx": round(-speed * math.sin(ang * t), 3),
            "vy": round(speed * math.cos(ang * t), 3),
            "vz": round(0.5 * math.cos(0.1 * t), 3),
            "distance_delta": 0.0,
            "speed_ms": 0.0,
        })

    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"[SAMPLE] {len(data)} records")
    return str(path)


def find_mcap_files(directory):
    """Encontra arquivos .mcap recursivamente"""
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

    # Gerar dados de amostra
    if "--generate-sample" in args or "--generate-mcap" in args:
        num = 500
        for a in args:
            if a.startswith("--count="):
                num = int(a.split("=")[1])

        if "--generate-mcap" in args:
            mcap_path = raw_dir / "sample_telemetry.mcap"
            generate_sample_mcap(mcap_path, num)
            print("\n  Rode sem flags para processar este MCAP.")
        else:
            json_path = raw_dir / "sample_telemetry.json"
            generate_sample_json(json_path, num)
            print("\n  Rode sem flags para processar este JSON.")

        return 0

    # Listar arquivos
    if "--list" in args:
        for label, ext in [("MCAP", "*.mcap"), ("JSON", "*.json")]:
            files = sorted(raw_dir.rglob(ext))
            print(f"\n{label} em {raw_dir}:")
            for f in files:
                print(f"  {f} ({f.stat().st_size/1024:.1f} KB)")
        return 0

    # Dry run
    if "--dry-run" in args:
        print(f"\n[DRY RUN] Raw: {raw_dir}  |  Processed: {processed_dir}")
        print(f"[DRY RUN] MCAP files: {len(find_mcap_files(raw_dir))}")
        print(f"[DRY RUN] Output: {processed_dir}/flight_data.parquet")
        return 0

    # --- Pipeline principal ---
    mcap_files = find_mcap_files(raw_dir)
    json_files = sorted(raw_dir.glob("*.json"))

    if mcap_files:
        all_records = []
        for mcap_file in mcap_files:
            records = extract_mcap(mcap_file)
            all_records.extend(records)
        data = all_records
    elif json_files:
        data = extract_json(json_files[0])
    else:
        print(f"\n[INFO] Nenhum arquivo MCAP ou JSON em {raw_dir}")
        print(f"  python3 {sys.argv[0]} --generate-mcap")
        print(f"  python3 {sys.argv[0]} --generate-sample")
        return 1

    data = transform(data)
    parquet_path = processed_dir / "flight_data.parquet"
    load_parquet(data, parquet_path)
    analyze(parquet_path)

    print("\n" + "=" * 60)
    print("  Pipeline completo!")
    print(f"  Saída: {parquet_path}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())

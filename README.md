# ros2-swarm-pipeline 🚁

End-to-end drone pipeline simulation: ROS 2 telemetry, ETL (MCAP → Parquet → DuckDB), and CI/CD with multi-architecture builds.

## Overview

This project simulates a complete drone development pipeline:

```
ROS 2 Nodes (Pub/Sub) ──▶ ETL Pipeline (MCAP→Parquet→DuckDB) ──▶ Analytics
         │                            │                              │
         └────────── CI/CD (GitHub Actions + GitLab CI) ──────────────┘
```

## Project Structure

```
ros2-swarm-pipeline/
├── ros2_nodes/                   # ROS 2 Python nodes
│   ├── drone_telemetry_pub.py    # Publishes drone telemetry at 10Hz
│   └── drone_telemetry_sub.py    # Subscribes and logs data for ETL
├── etl_pipeline/                 # Data engineering pipeline
│   ├── mcap_to_parquet.py        # MCAP → Parquet transformation
│   ├── analyze_flight.py         # DuckDB analytical queries
│   └── requirements.txt          # Python dependencies
├── cicd/                         # CI/CD configuration
│   ├── Dockerfile                # Multi-stage build (Kaniko-compatible)
│   ├── entrypoint.sh             # ROS 2 container entrypoint
│   └── requirements.txt          # Build dependencies
├── simulation/                   # PX4 + Gazebo (optional)
├── .github/workflows/
│   └── ci.yml                    # GitHub Actions CI/CD
├── .gitlab-ci.yml                # GitLab CI reference
└── README.md
```

## Quick Start

```bash
# Clone
git clone https://github.com/edsoncarlosdevops/ros2-swarm-pipeline.git
cd ros2-swarm-pipeline

# Run ETL pipeline (no ROS 2 required)
cd etl_pipeline
pip install -r requirements.txt
python mcap_to_parquet.py --generate-sample
python analyze_flight.py
```

### With Docker

```bash
docker build -f cicd/Dockerfile -t ros2-drone-sim .
docker run --rm ros2-drone-sim
```

### With ROS 2 locally

```bash
source /opt/ros/humble/setup.bash
python ros2_nodes/drone_telemetry_pub.py &
python ros2_nodes/drone_telemetry_sub.py
```

## Key Concepts

| Concept | Implementation |
|---------|---------------|
| **ROS 2 Nodes** | Publisher/Subscriber with DDS |
| **ETL Pipeline** | MCAP → Parquet → DuckDB |
| **Multi-arch Builds** | AMD64 + ARM64 in parallel |
| **Docker Layer Caching** | Optimized multi-stage Dockerfile |
| **CI/CD** | GitHub Actions + GitLab CI |
| **Data Analytics** | DuckDB SQL on Parquet |

## Data Pipeline

```
Drone (10Hz telemetry) → Subscriber (JSON log) → ETL → Parquet → DuckDB SQL
```

## License

MIT

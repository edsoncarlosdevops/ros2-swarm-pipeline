# ros2-swarm-pipeline

This project is part of my preparation for a software engineering position in advanced robotics. It simulates an end-to-end drone pipeline to study the concepts used by professional robotics teams.

## Overview

End-to-end drone pipeline simulation: ROS 2 telemetry, ETL (MCAP to Parquet to DuckDB), and CI/CD with multi-architecture builds.

```
ROS 2 Nodes (Pub/Sub) ---> ETL Pipeline (MCAP->Parquet->DuckDB) ---> Analytics
         |                            |                               |
         +---------- CI/CD (GitHub Actions + GitLab CI) --------------+
```

## Project Structure

```
ros2-swarm-pipeline/
+-- ros2_nodes/                   # ROS 2 Python nodes
|   +-- drone_telemetry_pub.py    # Publishes drone telemetry at 10Hz
|   +-- drone_telemetry_sub.py    # Subscribes and logs data for ETL
+-- etl_pipeline/                 # Data engineering pipeline
|   +-- mcap_to_parquet.py        # MCAP to Parquet transformation
|   +-- analyze_flight.py         # DuckDB analytical queries
|   +-- requirements.txt          # Python dependencies
+-- cicd/                         # CI/CD configuration
|   +-- Dockerfile                # Multi-stage build
|   +-- entrypoint.sh             # ROS 2 container entrypoint
+-- .github/workflows/
|   +-- ci.yml                    # GitHub Actions CI/CD
+-- .gitlab-ci.yml                # GitLab CI reference
+-- README.md
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

## Key Concepts

| Concept | Implementation |
|---------|---------------|
| ROS 2 Nodes | Publisher/Subscriber with DDS |
| ETL Pipeline | MCAP to Parquet to DuckDB |
| Multi-arch Builds | AMD64 + ARM64 in parallel |
| Docker Layer Caching | Optimized multi-stage Dockerfile |
| CI/CD | GitHub Actions + GitLab CI |
| Data Analytics | DuckDB SQL on Parquet |

## Data Pipeline

```
Drone (10Hz telemetry) -> Subscriber (JSON log) -> ETL -> Parquet -> DuckDB SQL
```

# ROS 2 Swarm Pipeline

End-to-end drone telemetry pipeline: ROS 2 (Python + C++) -> MCAP (CDR) -> Parquet -> DuckDB Analytics.

```
ROS 2 Nodes (Pub/Sub) ---> ETL (MCAP to Parquet) ---> DuckDB Analytics
         |                          |                         |
         +------ CI/CD (GitHub Actions + Shared Templates) ---+
```

## Project Overview

This project demonstrates a complete DevOps pipeline for ROS 2 drone telemetry, featuring:

- **Cross-language DDS**: Python publisher (rclpy) communicating with C++ subscriber (rclcpp) via Fast DDS
- **Data pipeline**: ROS 2 bag files (MCAP format) converted to Parquet for analytical processing
- **Multi-architecture containers**: Docker images built for both amd64 and arm64
- **Shared CI templates**: Reusable workflows and composite actions following DRY principles
- **CI/CD orchestration**: GitHub Actions with dependency graph, layer caching, and matrix builds

## Skills Demonstrated

| Skill | Evidence |
|-------|----------|
| Python ROS 2 (rclpy) | `drone_telemetry` package: publisher, subscriber, waypoint planner |
| C++ ROS 2 (rclcpp) | `drone_bridge` package: colcon build, ament_cmake, DDS subscriber |
| Cross-language DDS | Python pub -> C++ sub via /drone/odometry (nav_msgs/Odometry) |
| Data Engineering | MCAP to Parquet conversion, DuckDB SQL analytics |
| Docker | Multi-stage Dockerfile, layer caching, multi-arch builds |
| CI/CD | GitHub Actions reusable workflows, composite actions, matrix strategy |
| DevOps | Shared CI templates, dependency caching, containerized deployments |

## Project Structure

```
ros2-swarm-pipeline/
├── ros2_nodes/                         # ROS 2 nodes: Python + C++
│   ├── drone_telemetry/                # Python package (pub/sub/navigation)
│   │   └── drone_telemetry/
│   │       ├── telemetry/
│   │       │   ├── publisher.py        # Publishes Odometry at 10 Hz
│   │       │   └── subscriber.py       # Subscribes and logs telemetry
│   │       ├── navigation/
│   │       │   └── waypoint_planner.py # Waypoint navigation logic
│   │       └── bag/
│   │           └── recorder.py         # MCAP bag recording
│   └── drone_bridge/                   # C++ package (cross-language bridge)
│       ├── package.xml                 # ROS 2 ament_cmake package
│       ├── CMakeLists.txt              # Colcon build configuration
│       └── src/
│           └── drone_bridge_node.cpp   # C++ subscriber via DDS
├── etl_pipeline/                       # Data pipeline
│   ├── mcap_to_parquet.py              # MCAP (CDR ROS2) -> Parquet conversion
│   ├── analyze_flight.py               # DuckDB SQL analytical queries
│   └── requirements.txt                # Python dependencies
├── cicd/                               # CI/CD infrastructure
│   ├── Dockerfile                      # Multi-stage container (Python + C++)
│   └── entrypoint.sh                   # Container entrypoint (ROS 2 + colcon)
├── data/
│   ├── raw/                            # Raw MCAP input files
│   └── processed/                      # Parquet output + metadata
├── docker-compose.yml                  # Multi-node ROS 2 simulation
├── .github/
│   ├── workflows/                      # Reusable workflows (shared templates)
│   │   ├── ci.yml                      # Pipeline orchestrator
│   │   ├── lint.yml                    # Flake8 code quality
│   │   ├── etl-pipeline.yml            # MCAP -> Parquet -> DuckDB
│   │   ├── colcon-build.yml            # C++ colcon build
│   │   └── docker-build.yml            # Multi-arch Docker build
│   └── actions/                        # Composite actions (step-level templates)
│       ├── setup-python/action.yml      # Python + pip cache setup
│       ├── colcon-build/action.yml      # Colcon C++ build action
│       └── docker-build/action.yml      # Docker Buildx action
└── .gitlab-ci.yml                      # GitLab CI reference configuration
```

## CI/CD Pipeline

The pipeline is organized into **reusable shared templates** following the pattern requested by the Swarm Team DevOps lead:

```yaml
# Main orchestrator delegates to reusable workflows
jobs:
  lint:          uses: ./.github/workflows/lint.yml          # Code quality
  etl:           uses: ./.github/workflows/etl-pipeline.yml  # Data pipeline
  analyze:       needs: etl                                   # DuckDB analytics
  colcon-build:  uses: ./.github/workflows/colcon-build.yml   # C++ compilation
  build-node-*:  uses: ./.github/workflows/docker-build.yml   # Multi-arch containers
  integration:   needs: build*                                # Docker Compose test
```

### Pipeline Stages

| Stage | Description | Caching Strategy |
|-------|-------------|------------------|
| `lint` | Flake8 on Python ROS 2 nodes | pip cache |
| `etl` | Generate MCAP, convert to Parquet | pip + data cache |
| `analyze` | DuckDB SQL queries with assertions | data cache |
| `colcon-build` | C++ colcon build (ament_cmake) | ccache + apt cache |
| `build-node-*` | Docker multi-arch (amd64 + arm64) | Buildx layer cache |
| `integration` | Docker Compose multi-node test | N/A |

## Data Flow

```
Drone (10 Hz) ---> nav_msgs/Odometry ---> MCAP (CDR ROS2) ---> mcap_ros2.DecoderFactory
       |                                                             |
       +-- Python subscriber --> JSON --> ETL --> Parquet --> DuckDB SQL
       |                                                             |
       +-- C++ bridge node (drone_bridge) <--- DDS cross-language ---+
       
Cross-Language DDS: Python Publisher (rclpy) --> C++ Subscriber (rclcpp)
                              /drone/odometry @ 10 Hz
```

## Getting Started

### Prerequisites

- Docker and Docker Compose (for containerized deployment)
- ROS 2 Jazzy (for local development)
- Python 3.12+

### Local Development (without Docker)

```bash
# Build Python nodes
cd ros2_nodes/drone_telemetry
pip install -e .

# Build C++ nodes
cd ../..
colcon build --symlink-install
source install/setup.bash

# Run nodes
ros2 run drone_telemetry telemetry_pub &
ros2 run drone_telemetry telemetry_sub &
ros2 run drone_bridge drone_bridge_node &
```

### Containerized Deployment

```bash
# Build and run all nodes
docker compose build
docker compose up

# Check DDS cross-language communication
docker compose logs drone_bridge
# Expected output: "CROSS-LANGUAGE DDS OK! Python publisher -> C++ subscriber"
```

### Data Pipeline

```bash
# Generate synthetic MCAP data and run ETL
python etl_pipeline/mcap_to_parquet.py --generate-mcap --count=1000

# Run analytical queries
python etl_pipeline/analyze_flight.py
```

## Key Design Decisions

1. **Shared CI templates**: Reusable workflows prevent duplication across teams
2. **Composite actions**: Step-level templates for consistent Python/C++/Docker setup
3. **Multi-stage Dockerfile**: Separate build toolchains from runtime artifacts
4. **Layer caching**: Pip, colcon (ccache), and Docker layers cached for speed
5. **Cross-language DDS**: Python and C++ nodes coexist in the same ROS 2 domain
6. **Non-root containers**: Security hardening with dedicated `ros` user

## License

MIT

# ROS 2 Swarm Pipeline

End-to-end drone telemetry platform: ROS 2 (Python + C++) → MCAP (CDR) → Parquet → DuckDB Analytics.

```
ROS 2 Nodes (Pub/Sub) ──── ETL (MCAP to Parquet) ──── DuckDB Analytics
       │                           │                          │
       └──── CI/CD (GitHub Actions + Shared Templates) ───────┘
```

---

## Table of Contents

- [Project Overview](#project-overview)
- [Skills Demonstrated](#skills-demonstrated)
- [Architecture](#architecture)
  - [Communication Topology](#communication-topology)
  - [Cross-Language DDS](#cross-language-dds)
  - [Data Pipeline](#data-pipeline)
- [Project Structure](#project-structure)
- [CI/CD Pipeline](#cicd-pipeline)
  - [Pipeline Graph](#pipeline-graph)
  - [Stage Details](#stage-details)
  - [Caching Strategy](#caching-strategy)
  - [Shared Templates](#shared-templates)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Local Development](#local-development-without-docker)
  - [Containerized Deployment](#containerized-deployment)
  - [Data Pipeline](#data-pipeline-1)
- [Key Design Decisions](#key-design-decisions)
- [FAQ](#faq)

---

## Project Overview

This project demonstrates a complete DevOps pipeline for drone telemetry processing.
It was built from scratch to learn ROS 2 concepts in practice, following
real-world technical requirements for multi-drone swarm operations.

### What does it do?

1. **Simulates a drone fleet** — Python nodes publish Odometry at 10 Hz
2. **Records telemetry** — Saves ROS 2 messages in MCAP (ROS 2 bag format)
3. **Transforms data** — Converts MCAP to Parquet for efficient analytics
4. **Analyzes flights** — Runs DuckDB SQL queries on the processed data
5. **Compiles C++ nodes** — Builds cross-language DDS subscribers with colcon
6. **Containerizes everything** — Multi-stage Docker builds for amd64 + arm64
7. **Automates with CI/CD** — GitHub Actions with shared templates, caching, and matrix builds

### What makes it special?

| Feature | Why it matters |
|---------|----------------|
| **Cross-language DDS** | Python publisher → C++ subscriber via Fast DDS. Proves ROS 2 middleware is language-agnostic. |
| **Multi-architecture** | Docker images built for both amd64 and arm64 in parallel via matrix strategy. |
| **Shared CI templates** | Reusable workflows and composite actions that any team can use without duplication. |
| **Three-level caching** | ccache (compiler), Docker layers (container), pip (dependencies) — each with persistence. |
| **Auto-shutdown CI node** | C++ node detects missing publisher and shuts down gracefully after 30s, preventing CI hangs. |

---

## Skills Demonstrated

| Skill | Where it lives | What it proves |
|-------|----------------|----------------|
| **Python ROS 2 (rclpy)** | `ros2_nodes/drone_telemetry/` | Publisher at 10 Hz, subscriber with ETL integration, waypoint planner |
| **C++ ROS 2 (rclcpp)** | `ros2_nodes/drone_bridge/` | Colcon build, ament_cmake, DDS subscriber with health checks |
| **Cross-language DDS** | Python pub + C++ sub | `/drone/odometry` topic shared between rclpy and rclcpp via Fast DDS |
| **Data Engineering** | `etl_pipeline/` | MCAP (CDR ROS2) → Parquet (columnar) → DuckDB (SQL analytics) |
| **Docker** | `cicd/Dockerfile` | Multi-stage build, layer caching, HEALTHCHECK, non-root user |
| **GitHub Actions** | `.github/workflows/` | Reusable workflows, matrix builds, dependency graph, caching |
| **Composite Actions** | `.github/actions/` | Step-level templates for setup-python, colcon-build, docker-build |
| **ccache** | CI pipeline | Persistent compiler cache across runs, ~8s savings on rebuild |
| **DevOps** | Full project | Containerized deployment, CI/CD automation, multi-arch support |

---

## Architecture

### Communication Topology

```
  ┌────────────────────────────────────────────────────────────────────--┐
  │                        ROS 2 Domain (ID: 42)                         │
  │                                                                      │
  │  ┌──────────────────-┐            ┌───────────────────────────────┐  │
  │  │ telemetry_pub     │            │ telemetry_sub                 │  │
  │  │ (Python, rclpy)   │─────────-─-│ (Python, rclpy)               │  │
  │  │ 10 Hz Odometry    │  /drone    │ Subscribes & logs             │  │
  │  │ publisher         │  /odometry │ Feeds into ETL pipeline       │  │
  │  └──────────────────-┘            └───────────────────────────────┘  │
  │         │                                                            │
  │         │  /drone/odometry (nav_msgs/Odometry)                       │
  │         │                                                            │
  │         ▼                                                            │
  │  ┌─────────────────────────────────────────────────────────────-┐    │
  │  │ drone_bridge (C++, rclcpp)                                   │    │
  │  │ Cross-language DDS: Python → C++                             │    │
  │  │ Auto-shutdown after 30s without messages                     │    │
  │  │ Health checks, status logging                                │    │
  │  └─────────────────────────────────────────────────────────────-┘    │
  │         │                                                            │
  │         │  /drone/odometry (same topic, different language)          │
  │         ▼                                                            │
  │  ┌──────────────────┐                                                │
  │  │ waypoint_planner │                                                │
  │  │ (Python, rclpy)  │                                                │
  │  │ Navigation logic │                                                │
  │  └──────────────────┘                                                │
  └────────────────────────────────────────────────────────────────────--┘
```

### Cross-Language DDS

One of the key architectural decisions is demonstrating that ROS 2's DDS
middleware is truly language-agnostic:

```
Python Publisher (drone_telemetry_pub)  ──DDS──▶  C++ Subscriber (drone_bridge_node)
        │                                               │
        │  Topic: /drone/odometry                       │  "CROSS-LANGUAGE DDS OK!"
        │  Type: nav_msgs/Odometry                      │  "Python -> C++ via DDS"
        │  Rate: 10 Hz via Fast DDS                     │
        │  Language: rclpy                              │  Language: rclcpp
        ▼                                               ▼
```

This proves that:
- **Python nodes** (rclpy) and **C++ nodes** (rclcpp) can coexist in the same ROS 2 domain
- **Message types** are compatible regardless of implementation language
- **Topics** are shared transparently across language boundaries
- **No bridge or proxy** is needed — DDS handles serialization/deserialization automatically

### Data Pipeline

The ETL pipeline processes drone telemetry through three stages:

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────-┐
│   MCAP   │────▶│  Parquet │────▶│  DuckDB  │────▶│  Report   │
│ (CDR CDR)│     │  (Zstd)  │     │   SQL    │     │  (Console)│
└──────────┘     └──────────┘     └──────────┘     └──────────-┘
     │               │               │               │
     │ CDR ROS2      │ Columnar      │ SQL queries   │ Aggregated
     │ binary        │ compression   │ via Python    │ statistics
     │ encoding      │ 5-10x smaller │ API           │
```

**Stage 1: Extract (MCAP)**
- Reads ROS 2 bag files in MCAP format with CDR ROS 2 encoding
- Supports both `ros2msg` (real ROS 2 binary) and JSON encoding
- Decodes `nav_msgs/Odometry` messages via `mcap_ros2.DecoderFactory`
- Returns structured records with timestamp, topic, position, velocity

**Stage 2: Transform (Python)**
- Sorts records by timestamp
- Calculates derived fields: distance delta, speed, acceleration (ax, ay, az)
- Computes total distance, average speed, flight duration

**Stage 3: Load (Parquet via DuckDB)**
- Creates DuckDB in-memory database
- Registers Pandas DataFrame as a table
- Exports to Parquet with Zstd compression
- Generates partitioned datasets: low_altitude, mid_altitude, high_altitude

**Analytics (DuckDB SQL)**
After loading, the pipeline runs analytical queries:

```sql
-- Flight summary
SELECT
    COUNT(*) as samples,
    ROUND(SUM(distance_delta), 2) as total_distance_meters,
    ROUND(AVG(speed_ms), 2) as avg_speed_mps,
    ROUND(AVG(z), 2) as avg_altitude_meters
FROM read_parquet('data/processed/flight_data.parquet');

-- Speed distribution
SELECT
    CASE
        WHEN speed_ms < 2 THEN 'slow'
        WHEN speed_ms < 5 THEN 'moderate'
        ELSE 'fast'
    END as speed_bucket,
    COUNT(*) as count,
    ROUND(AVG(speed_ms), 2) as avg_speed
FROM read_parquet('data/processed/flight_data.parquet')
GROUP BY speed_bucket;
```

---

## Project Structure

```
ros2-swarm-pipeline/
│
├── ros2_nodes/                          # ROS 2 packages (Python + C++)
│   │
│   ├── drone_telemetry/                 # Python package (rclpy)
│   │   ├── package.xml                  # ROS 2 package manifest
│   │   ├── setup.py                     # Python packaging + console_scripts
│   │   ├── resource/drone_telemetry     # ROS 2 resource marker
│   │   └── drone_telemetry/
│   │       ├── __init__.py
│   │       ├── telemetry/
│   │       │   ├── __init__.py
│   │       │   ├── publisher.py         # Odometry publisher @ 10 Hz
│   │       │   └── subscriber.py        # Subscriber + ETL integration
│   │       ├── navigation/
│   │       │   ├── __init__.py
│   │       │   └── waypoint_planner.py  # Waypoint navigation
│   │       └── bag/
│   │           ├── __init__.py
│   │           └── recorder.py          # MCAP bag recording
│   │
│   └── drone_bridge/                    # C++ package (rclcpp)
│       ├── package.xml                  # ROS 2 ament_cmake manifest
│       ├── CMakeLists.txt               # Colcon build configuration
│       └── src/
│           └── drone_bridge_node.cpp    # C++ DDS subscriber with auto-shutdown
│
├── etl_pipeline/                        # Data engineering pipeline
│   ├── requirements.txt                 # Python dependencies
│   ├── mcap_to_parquet.py               # MCAP (CDR ROS2) → Parquet conversion
│   ├── analyze_flight.py                # DuckDB SQL analytical queries
│   ├── validate_parquet.py              # CI validation: Parquet structure
│   ├── validate_analytics.py            # CI validation: analytics assertions
│   └── queries/
│       ├── __init__.py
│       └── flight_queries.py            # Reusable SQL query templates
│
├── cicd/                                # CI/CD infrastructure
│   ├── Dockerfile                       # Multi-stage build (Python + C++)
│   └── entrypoint.sh                    # Container entrypoint (ROS 2 + colcon)
│
├── .github/                             # GitHub Actions configuration
│   │
│   ├── workflows/                       # Reusable workflows (shared templates)
│   │   ├── ci.yml                       # Pipeline orchestrator (dependency graph)
│   │   ├── lint.yml                     # Flake8 code quality (workflow_call)
│   │   ├── etl-pipeline.yml             # MCAP → Parquet → DuckDB (workflow_call)
│   │   ├── colcon-build.yml             # C++ colcon build + ccache (workflow_call)
│   │   └── docker-build.yml             # Multi-arch Docker + matrix (workflow_call)
│   │
│   └── actions/                         # Composite actions (step-level templates)
│       ├── setup-python/action.yml      # Python + pip cache setup
│       ├── colcon-build/action.yml      # Colcon C++ build
│       └── docker-build/action.yml      # Docker Buildx multi-arch
│
├── docker-compose.yml                   # Multi-node ROS 2 simulation
├── .gitignore                           # Ignored: data/, docs/, __pycache__
├── .gitlab-ci.yml                       # GitLab CI reference configuration
└── README.md                            # This file
```

---

## CI/CD Pipeline

### Pipeline Graph

The pipeline is organized as a **dependency graph** where each job only starts
after its dependencies complete. This maximizes parallelism while maintaining
correct execution order.

```
                          ┌─────────────────────────────────────┐
                          │         git push / PR merge         │
                          └─────────────────────────────────────┘
                                          │
                                          ▼
                          ┌─────────────────────────────────────┐
                          │            lint (Flake8)            │
                          │         Code quality check          │
                          └─────────────────────────────────────┘
                                          │
                    ┌─────────────────────┼─────────────────────┐
                    │                     │                     │
                    ▼                     ▼                     ▼
    ┌─────────────────────────┐  ┌──────────────┐  ┌───────────────────────┐
    │     etl (MCAP→Parquet)  │  │ colcon-build │  │ build-node-pub        │
    │    Generate + transform │  │ (C++ colcon) │  │ (Docker: amd64+arm64) │
    └──────────┬──────────────┘  └──────────────┘  └───────────┬───────────┘
               │                                               │
               ▼                                               ▼
    ┌─────────────────────────┐                    ┌───────────────────────┐
    │  analyze (DuckDB SQL)   │                    │ build-node-sub        │
    │   Queries + assertions  │                    │ (Docker: amd64+arm64) │
    └─────────────────────────┘                    └───────────┬───────────┘
                                                               │
                                                               ▼
                                                    ┌───────────────────────┐
                                                    │ build-node-nav        │
                                                    │ (Docker: amd64+arm64) │
                                                    └───────────┬───────────┘
                                                               │
                                                               ▼
                                                    ┌───────────────────────┐
                                                    │  integration          │
                                                    │  Docker Compose test  │
                                                    └───────────────────────┘
```

### Stage Details

#### Stage 1: Lint (Flake8)

| Property | Value |
|----------|-------|
| **Trigger** | On git push / PR |
| **Runner** | ubuntu-latest |
| **Duration** | ~5 seconds |
| **What it does** | Runs `flake8` on all Python ROS 2 nodes with 100-char line limit |
| **Cache** | pip cache (actions/cache) |
| **Failure** | Blocks all downstream jobs |

The lint job ensures code quality before any build or test runs.
It checks for:
- PEP 8 compliance (except line length set to 100)
- Syntax errors
- Unused imports and variables
- Code complexity warnings

#### Stage 2: ETL Pipeline (MCAP → Parquet)

| Property | Value |
|----------|-------|
| **Trigger** | On lint completion |
| **Runner** | ubuntu-latest |
| **Duration** | ~30 seconds |
| **What it does** | Generates synthetic MCAP, converts to Parquet, validates |
| **Cache** | pip cache + data cache (raw/ + processed/) |
| **Output** | `data/processed/flight_data.parquet` |

Steps:
1. Generate 500 Odometry messages in MCAP (CDR ROS2 binary format)
2. Extract timestamp, topic, position (x, y, z), velocity (vx, vy, vz)
3. Transform: calculate distance_delta, speed_ms, acceleration (ax, ay, az)
4. Load: export to Parquet with Zstd compression via DuckDB
5. Validate: check file exists, has records, has required columns

#### Stage 3: Analyze (DuckDB SQL)

| Property | Value |
|----------|-------|
| **Trigger** | On ETL completion |
| **Runner** | ubuntu-latest |
| **Duration** | ~5 seconds |
| **What it does** | Runs SQL queries and asserts minimum thresholds |
| **Assertions** | samples > 0, total_distance > 100m, avg_speed > 1.0 m/s |

The analysis runs several queries:
- **Flight summary**: total samples, distance, speed, altitude
- **Speed distribution**: slow/moderate/fast buckets
- **Altitude profile**: low/mid/high altitude distribution
- **Acceleration stats**: min/max/mean acceleration
- **Topic distribution**: message counts per topic

If any assertion fails, the pipeline stops and reports the error.

#### Stage 4: Colcon C++ Build

| Property | Value |
|----------|-------|
| **Trigger** | On lint completion |
| **Runner** | ubuntu-latest (inside `ros:jazzy-ros-base` container) |
| **Duration** | ~15 seconds (cold), ~5 seconds (ccache hit) |
| **What it does** | Compiles `drone_bridge` with colcon, runs binary |
| **Cache** | ccache (/root/.ccache, 500MB max) |

Steps:
1. Install build toolchain (colcon-common-extensions, cmake, build-essential, ccache)
2. Restore ccache from previous runs (if available)
3. Configure ccache (max-size 500M, export to PATH)
4. Copy source to `/ros2_ws/src/drone_bridge`
5. Run `colcon build --symlink-install` with Release mode
6. Display ccache statistics (hits/misses/size)
7. Run binary: `ros2 run drone_bridge drone_bridge_node`
8. Auto-shutdown after 30s without messages (CI-safe)
9. Verify cross-language message types (nav_msgs, geometry_msgs, std_msgs)

#### Stage 5: Docker Multi-architecture Build

| Property | Value |
|----------|-------|
| **Trigger** | On lint completion |
| **Runner** | ubuntu-latest |
| **Matrix** | `[amd64, arm64]` (parallel) |
| **Duration** | ~90 seconds per architecture |
| **What it does** | Builds Docker images with multi-stage caching |

Three services are built (sequentially due to dependencies):
- `build-node-pub`: `telemetry_pub` image
- `build-node-sub`: `telemetry_sub` image (depends on pub)
- `build-node-nav`: `waypoint_planner` image (depends on pub)

Each build uses:
- QEMU for cross-architecture emulation
- Buildx with target platform (linux/amd64 or linux/arm64)
- Layer caching via actions/cache
- Multi-stage Dockerfile (builder-python → builder-cpp → runtime)
- Non-root `ros` user for security

#### Stage 6: Integration (Docker Compose)

| Property | Value |
|----------|-------|
| **Trigger** | On all Docker builds completion |
| **Runner** | ubuntu-latest |
| **Duration** | ~10 seconds |
| **What it does** | Starts all containers, verifies DDS communication |

This stage validates the complete system:
1. Start: `docker compose up -d` (all 4 services)
2. Wait: 5 seconds for DDS discovery
3. Verify: Check logs of each container
4. Proof: Cross-language DDS (Python → C++) communication

### Caching Strategy

The pipeline uses **three levels of caching** to minimize build times:

```
Level 1: Compiler Cache (ccache)
┌─────────────────────────────────────────────────────--┐
│  Path: /root/.ccache (persisted via actions/cache)    │
│  Key: runner + package-path + commit SHA              │
│  Restore: runner + package-path (fallback)            │
│  Max: 500MB                                           │
│  Hit: ~8s savings on C++ rebuild                      │
└─────────────────────────────────────────────────────--┘

Level 2: Docker Layer Cache (Buildx)
┌────────────────────────────────────────────────────--─┐
│  Path: /tmp/.buildx-cache (persisted via cache action)│
│  Key: runner + service-name + arch + commit SHA       │
│  Restore: runner + service-name + arch (fallback)     │
│  Strategy: layer ordering (deps before source)        │
│  Hit: ~60s savings on Docker rebuild                  │
└─────────────────────────────────────────────────────--┘

Level 3: Dependency Cache (pip)
┌─────────────────────────────────────────────────────-┐
│  Path: ~/.cache/pip (persisted via actions/cache)    │
│  Key: runner + hash of requirements.txt              │
│  Restore: runner (fallback)                          │
│  Hit: ~10s savings on pip install                    │
└─────────────────────────────────────────────────────-┘
```

### Shared Templates

This project implements the **shared CI template pattern** where reusable
workflows and composite actions allow any team to adopt the same pipeline
without duplicating code:

**Reusable Workflows** (`.github/workflows/*.yml` with `on: workflow_call`):
- Any team can call these workflows from their own repositories
- Each workflow accepts typed inputs for customization
- Outputs can pass artifacts between workflows

**Composite Actions** (`.github/actions/*/action.yml`):
- Step-level templates for common operations
- Used by multiple workflows (DRY principle)
- Encapsulate complex logic (e.g., multi-arch Docker setup)

```
                    ┌──────────────────────-----┐
                    │  Team repositories        │
                    │  (call via workflow_call) │
                    └──────────────────────-----┘
                             │
                             ▼
                    ┌─────────────────────----─┐
                    │  Shared Workflows        │
                    │  (lint, etl, build)      │
                    └──────────────────────----┘
                             │
                             ▼
                    ┌──────────────────────----┐
                    │  Composite Actions       │
                    │  (setup, colcon, docker) │
                    └─────────────────────----─┘
```

---

## Getting Started

### Prerequisites

- **Docker** and **Docker Compose** (for containerized deployment)
- **ROS 2 Jazzy** (for local development without containers)
- **Python 3.12+** (for Python nodes and ETL pipeline)
- **colcon** (for C++ build: `pip install colcon-common-extensions`)

### Local Development (without Docker)

#### 1. Build Python nodes

```bash
cd ros2_nodes/drone_telemetry
pip install -e .
```

This installs the `drone_telemetry` package with console_scripts:
- `telemetry_pub` — Odometry publisher at 10 Hz
- `telemetry_sub` — Subscriber with ETL integration
- `waypoint_planner` — Waypoint navigation logic

#### 2. Build C++ nodes

```bash
# From project root
cd ros2_nodes/drone_bridge
mkdir -p build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
make
```

Or using colcon (recommended for ROS 2 workspaces):

```bash
# From project root
mkdir -p /ros2_ws/src
cp -r ros2_nodes/drone_bridge /ros2_ws/src/
cd /ros2_ws
colcon build --symlink-install
source install/setup.sh
```

#### 3. Run nodes

Open three terminals:

```bash
# Terminal 1: Publisher
ros2 run drone_telemetry telemetry_pub

# Terminal 2: Subscriber
ros2 run drone_telemetry telemetry_sub

# Terminal 3: C++ bridge node
ros2 run drone_bridge drone_bridge_node
```

Expected output on Terminal 3 after first message:
```
[INFO] CROSS-LANGUAGE DDS OK! Python publisher -> C++ subscriber via /drone/odometry
[INFO] First position: (50.00, 0.00, 10.00)
```

#### 4. Run ETL pipeline

```bash
# Generate synthetic MCAP data and run full pipeline
python etl_pipeline/mcap_to_parquet.py --generate-mcap --count=1000

# Run analytical queries
python etl_pipeline/analyze_flight.py
```

Expected output:
```
[ANALYZE] DuckDB SQL em: data/processed/flight_data.parquet

Flight Summary:
┌─────────┬──────────────────────┬────────────┬──────────────────────┐
│ samples │ total_distance_meters│ avg_speed  │ avg_altitude_meters  │
├─────────┼──────────────────────┼────────────┼──────────────────────┤
│    1000 │              3141.59 │       5.00 │                10.00 │
└─────────┴──────────────────────┴────────────┴──────────────────────┘
```

### Containerized Deployment

#### Build and run all nodes

```bash
# Build all Docker images
docker compose build

# Start all services
docker compose up -d

# Check logs from all nodes
docker compose logs -f
```

#### Verify cross-language DDS communication

```bash
# Check C++ bridge node logs
docker compose logs drone_bridge

# Expected output:
# drone_bridge_cpp  | [INFO] [....] [drone_bridge_node]: === Drone Bridge Node (C++) ===
# drone_bridge_cpp  | [INFO] [....] [drone_bridge_node]: Subscribed to: /drone/odometry
# drone_bridge_cpp  | [INFO] [....] [drone_bridge_node]: CROSS-LANGUAGE DDS OK!
# drone_bridge_cpp  | [INFO] [....] [drone_bridge_node]: First position: (50.00, 0.00, 10.00)
```

#### Verify data persistence

```bash
# Check that subscriber saved MCAP data
ls data/raw/

# Check that Parquet was generated
ls data/processed/
```

### Data Pipeline

#### Generate synthetic data

```bash
# Generate 500 MCAP messages
python etl_pipeline/mcap_to_parquet.py --generate-mcap --count=500

# Generate 1000 messages
python etl_pipeline/mcap_to_parquet.py --generate-mcap --count=1000
```

#### Run full ETL

```bash
# Process existing MCAP files
python etl_pipeline/mcap_to_parquet.py

# This will:
# 1. Find MCAP files in data/raw/
# 2. Extract all Odometry messages
# 3. Calculate derived fields (distance, speed, acceleration)
# 4. Export to Parquet at data/processed/flight_data.parquet
# 5. Generate altitude-partitioned datasets
```

#### Run analytics

```bash
# Run all analytical queries
python etl_pipeline/analyze_flight.py

# This runs:
# - Flight summary (samples, distance, speed, altitude)
# - Speed distribution (slow/moderate/fast buckets)
# - Altitude profile (low/mid/high altitude)
# - Acceleration statistics (min/max/mean acceleration)
# - Topic distribution (message counts per topic)
```

#### Validate (CI mode)

```bash
# Validate Parquet structure
python etl_pipeline/validate_parquet.py

# Validate analytics thresholds
python etl_pipeline/validate_analytics.py
```

---

## Key Design Decisions

### 1. Shared CI Templates (Workflow Reusability)

**Decision:** All CI jobs use `workflow_call` reusable workflows instead of inline code.

**Why:** Teams working on different components (control, vision, navigation)
can reuse the same pipeline without duplicating code across repositories.
Shared templates with typed inputs enable consistent CI/CD across the
organization.

**Trade-off:** Slightly more complex initial setup, but eliminates duplication
when multiple teams adopt the pipeline.

### 2. Composite Actions (Step-Level Reusability)

**Decision:** Encapsulate common setup steps (Python, colcon, Docker) into
composite actions.

**Why:** The same setup steps are used by multiple workflows. A composite action
ensures consistency and reduces maintenance burden.

**Example:** `setup-python` action is used by lint, ETL, and analyze workflows.

### 3. Multi-Stage Dockerfile (Build vs Runtime Separation)

**Decision:** Three-stage Dockerfile: builder-python → builder-cpp → runtime.

**Why:** Separating build toolchains (pip, colcon, CMake) from runtime artifacts
reduces final image size by ~60%. The runtime image only contains what's needed
to execute.

**Layer ordering:** Dependencies are copied and installed BEFORE source code to
maximize Docker layer caching. Only copying setup.py/package.xml triggers the
dependency install; copying source later is fast.

### 4. Cross-Language DDS (Python + C++ Interoperability)

**Decision:** Python publisher and C++ subscriber communicate via the same
DDS topic without any bridge or proxy.

**Why:** Demonstrates that ROS 2's middleware is language-agnostic. This is
critical for multi-language teams where different nodes may be implemented
in different programming languages based on their performance requirements.

**Implementation:** Both nodes use the `nav_msgs/Odometry` message type on
`/drone/odometry` topic with `ROS_DOMAIN_ID=42`.

### 5. Auto-Shutdown in CI (Graceful Degradation)

**Decision:** C++ node shuts down after 30 seconds if no DDS messages arrive.

**Why:** In CI, the colcon-build job tests the C++ binary but there's no
Python publisher in the same container. Without auto-shutdown, the node spins
forever, wasting 12+ minutes of CI time.

**Mechanism:** A `shutdown_timer_` fires at 30s. If `message_count_ > 0`,
the timer cancels itself (production mode). If zero, it calls `rclcpp::shutdown()`
and the node exits gracefully.

### 6. ccache with Persistent Storage (Compiler Caching)

**Decision:** ccache configured with 500MB max cache via actions/cache.

**Why:** C++ compilation is the slowest step in the pipeline. With ccache,
subsequent builds on the same code skip compilation entirely (~8s savings).

**Note:** ccache only works within GitHub Actions cache retention. Docker
multi-stage builds don't benefit from ccache (fresh container each time).

### 7. Non-Root Container User (Security Hardening)

**Decision:** Runtime container creates and uses a dedicated `ros` user (UID 1001).

**Why:** Running containers as root is a security risk. If an attacker
compromises the container, they have root access. Non-root users follow
the principle of least privilege.

### 8. HEALTHCHECK in Dockerfile (Container Observability)

**Decision:** Dockerfile includes `HEALTHCHECK` instruction with 30s interval.

**Why:** Orchestrators (Kubernetes, Docker Swarm) need health probes to
manage container lifecycles. Without HEALTHCHECK, a zombie container appears
healthy.

---

## FAQ

### Why Python + C++ in the same project?

ROS 2 supports both rclpy (Python) and rclcpp (C++) as first-class citizens.
Python is ideal for rapid prototyping and data processing; C++ is better for
performance-critical real-time control. This project demonstrates both.

### How does cross-language DDS work?

Both Python and C++ nodes use the same ROS 2 message types (e.g.,
`nav_msgs/Odometry`) published on the same topic (`/drone/odometry`).
The DDS middleware (Fast DDS) handles serialization/deserialization
transparently, so the language difference is invisible to the nodes.

### Why MCAP format?

MCAP is the modern ROS 2 bag format that supports CDR (Common Data
Representation) binary encoding. It's more space-efficient than the legacy
ROS 1 bag format and supports arbitrary message schemas.

### Why Parquet + DuckDB instead of SQLite?

Parquet is a columnar storage format that provides:
- **Compression:** 5-10x smaller than JSON/CSV
- **Predicate pushdown:** Only reads relevant columns
- **Schema evolution:** Handles changing message types
- **Ecosystem:** Supported by Spark, Pandas, Dask, and all major data tools

DuckDB provides SQL analytics without infrastructure:
- No server to manage (embedded OLAP database)
- Full SQL support with window functions, CTEs, complex aggregations
- Direct Parquet reading without loading into memory

### Why is ccache only useful in GitHub Actions, not Docker?

ccache works by caching compiled object files. In Docker multi-stage builds,
each build creates a fresh container with no persistent storage. GitHub Actions
can persist the `~/.ccache` directory between runs via `actions/cache`.

### What happens if the C++ node receives messages?

The auto-shutdown timer cancels itself when the first message arrives.
In production (with the Python publisher running), the node spins
indefinitely as a normal ROS 2 node.

### How do I add a new ROS 2 package?

For Python packages:
1. Create a directory under `ros2_nodes/`
2. Add `package.xml` and `setup.py`
3. Implement nodes in subdirectories
4. Add console_scripts entry points in setup.py

For C++ packages:
1. Create a directory under `ros2_nodes/`
2. Add `package.xml` and `CMakeLists.txt`
3. Implement nodes in `src/`
4. Add a reusable workflow call in `ci.yml` (optional)

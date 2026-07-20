# ROS 2 Swarm Pipeline

Pipeline de telemetria de drones: ROS 2 → MCAP (CDR) → Parquet → DuckDB Analytics.

```
ROS 2 Nodes (Pub/Sub) ──> ETL (MCAP→Parquet) ──> DuckDB Analytics
         │                        │                       │
         └──── CI/CD (GitHub Actions + GitLab CI) ────────┘
```

## Project Structure

```
ros2-swarm-pipeline/
├── ros2_nodes/                     # ROS 2 Python nodes
│   └── drone_telemetry/
│       └── drone_telemetry/
│           ├── drone_telemetry_pub.py   # Publica telemetria 10Hz
│           ├── drone_telemetry_sub.py   # Assina e salva dados
│           └── bag_recorder.py          # Grava MCAP com ros2 bag
├── etl_pipeline/                   # Pipeline de dados
│   ├── mcap_to_parquet.py          # MCAP (CDR ROS2) → Parquet
│   ├── analyze_flight.py           # DuckDB SQL analytics
│   └── requirements.txt
├── cicd/                           # CI/CD
│   ├── Dockerfile                  # Multi-stage (Jazzy + MCAP)
│   ├── entrypoint.sh
│   └── requirements.txt
├── data/
│   ├── raw/                        # MCAP files de entrada
│   └── processed/                  # Parquet + metadados
├── .github/workflows/ci.yml        # GitHub Actions CI/CD
└── .gitlab-ci.yml                  # GitLab CI reference
```

## Quick Start (sem ROS 2)

```bash
cd etl_pipeline
pip install -r requirements.txt

# Gera MCAP sintético com CDR ROS2 real
python mcap_to_parquet.py --generate-mcap --count=500

# Pipeline completo: MCAP → Parquet → DuckDB
python mcap_to_parquet.py

# Analytics dedicado
python analyze_flight.py
```

## Flags do Pipeline

| Flag | Descrição |
|------|-----------|
| `--generate-mcap` | Gera MCAP sintético com encoding CDR ROS2 real |
| `--generate-sample` | Gera JSON (retrocompatibilidade) |
| `--count=N` | Número de mensagens (default: 500) |
| `--list` | Lista arquivos MCAP/JSON disponíveis |
| `--dry-run` | Preview sem executar |

## Com Docker

```bash
docker build -f cicd/Dockerfile -t ros2-drone-sim .
docker run --rm ros2-drone-sim
```

## CI/CD com GitHub Actions

O pipeline CI executa em **3 níveis de cache**:

```yaml
# 1. Cache de dependências Python (pip)
# 2. Cache de layers Docker (buildx)
# 3. Cache de dados Parquet entre runs
```

| Job | Descrição |
|-----|-----------|
| `lint` | Flake8 nos nodes ROS 2 |
| `etl` | Gera MCAP → Parquet + testes |
| `build` | Docker multi-arch (amd64 + arm64) |
| `analyze` | DuckDB SQL analytics + validação |

## Key Concepts

| Concept | Implementation |
|---------|---------------|
| ROS 2 Nodes | Publisher/Subscriber with DDS |
| MCAP Encoding | CDR ROS2 real (`ros2msg`) |
| ETL Pipeline | MCAP → Parquet → DuckDB |
| Multi-arch | AMD64 + ARM64 em paralelo |
| Docker Caching | Multi-stage + layer caching |
| Data Analytics | DuckDB SQL no Parquet |

## Data Flow

```
Drone (10Hz) ──> nav_msgs/Odometry ──> MCAP (CDR ROS2) ──> mcap_ros2.DecoderFactory
       │                                                            │
       └─── ros2 bag record ───> .mcap ───> ETL ───> .parquet ───> DuckDB SQL
```

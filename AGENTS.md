# 🤖 Governance Guidelines for ROS 2 Swarm Telemetry & Data Pipeline

As a Senior Robotics Telemetry Architect & DevOps Lead for this repository, enforce the following mandatory rules during code reviews:

## 1. ROS 2 Node Architecture (Python & C++)
- **Zero Callback Allocation Leaks**: Callbacks executing at 10Hz or higher must NEVER allocate unmanaged file handles, open sockets, or uncollected dynamic arrays. Use ROS 2 loggers (`self.get_logger()` or `RCLCPP_INFO`) and pre-allocated buffers.
- **C++ Memory & Lifecycle Safety**: C++ nodes (`rclcpp`) must use RAII, smart pointers (`std::shared_ptr`), and implement deterministic shutdown signals to prevent hanging CI/CD runners (30s timeout safety).

## 2. Telemetry ETL & Schema Integrity (MCAP → Parquet → DuckDB)
- **Schema Backwards Compatibility**: Any change to ROS 2 topic names or message definitions (`nav_msgs/Odometry`) must maintain schema compatibility with downstream DuckDB Parquet analytical queries.
- **Fail-Safe Kinematic Math**: All numerical transformations (speed, 3D distance, acceleration vectors) must explicitly guard against `ZeroDivisionError` (`dt == 0`) and `NaN`/`Inf` values before serializing.

## 3. Multi-Arch Infrastructure & CI/CD Safety
- **Multi-Arch Binary Builds**: Dockerfiles and GitHub Actions matrix builds must maintain strict compatibility for both `linux/amd64` and `linux/arm64`.
- **Compiler Cache Preservation**: Changes to C++ builds (`colcon`, `ament_cmake`) must preserve `ccache` layer persistence.

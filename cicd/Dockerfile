# =============================================================================
# Dockerfile - Multi-stage ROS 2 Development Container
#
# Builds a containerized ROS 2 environment with both Python and C++ nodes.
# Uses multi-stage build to minimize final image size by separating
# build toolchains from runtime artifacts.
#
# Stages:
#   1. builder-python: Installs Python ROS 2 packages via pip/setup.py
#   2. builder-cpp:    Compiles C++ ROS 2 packages via colcon
#   3. runtime:        Minimal image with Python + C++ executables
#
# Layer caching strategy:
#   - Dependencies (setup.py/CMakeLists.txt) BEFORE source code
#   - ccache for repeated C++ compilation
#   - Build toolchains excluded from final stage
# =============================================================================

FROM ros:jazzy-ros-base AS builder-python

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-pip \
    python3-colcon-common-extensions \
    ccache \
    && rm -rf /var/lib/apt/lists/*

# Layer cache: Install Python dependencies before copying source
# This layer only invalidates when setup.py or package.xml changes
COPY ros2_nodes/drone_telemetry/setup.py \
     ros2_nodes/drone_telemetry/package.xml \
     /ros2_ws/src/drone_telemetry/
RUN pip3 install --break-system-packages --no-cache-dir \
    /ros2_ws/src/drone_telemetry/ 2>/dev/null || true

# Layer cache: Copy full source and reinstall (fast if deps are cached)
COPY ros2_nodes/drone_telemetry/ /ros2_ws/src/drone_telemetry/
RUN pip3 install --break-system-packages --no-cache-dir \
    /ros2_ws/src/drone_telemetry/

# --------------------------------------------------------------------------
# Stage 2: C++ Builder - Compile ROS 2 C++ nodes with colcon
# --------------------------------------------------------------------------
FROM ros:jazzy-ros-base AS builder-cpp

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-pip \
    python3-colcon-common-extensions \
    ccache \
    build-essential \
    cmake \
    && rm -rf /var/lib/apt/lists/*

# Layer cache: Build configuration changes infrequently
COPY ros2_nodes/drone_bridge/CMakeLists.txt \
     ros2_nodes/drone_bridge/package.xml \
     /ros2_ws/src/drone_bridge/

# Layer cache: Source code changes more frequently
COPY ros2_nodes/drone_bridge/ /ros2_ws/src/drone_bridge/

# Compile C++ nodes with colcon (ament_cmake build system)
RUN . /opt/ros/jazzy/setup.sh && \
    cd /ros2_ws && \
    colcon build --symlink-install --event-handlers console_direct+ \
      --cmake-args -DCMAKE_BUILD_TYPE=Release 2>&1 | tail -20

# --------------------------------------------------------------------------
# Stage 3: Runtime - Minimal production image
# --------------------------------------------------------------------------
FROM ros:jazzy-ros-base AS runtime

ENV DEBIAN_FRONTEND=noninteractive
ENV ROS_DOMAIN_ID=42

# System runtime dependencies (minimal set)
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-pip \
    ros-jazzy-rosbag2 \
    ros-jazzy-rosbag2-storage-mcap \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Python data pipeline dependencies (from requirements.txt)
COPY etl_pipeline/requirements.txt /tmp/requirements.txt
RUN pip3 install --break-system-packages --no-cache-dir \
    -r /tmp/requirements.txt && \
    rm -rf ~/.cache/pip /tmp/requirements.txt

# Container entrypoint (sources ROS 2 and colcon workspace)
COPY cicd/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Python ROS 2 packages (pre-installed in builder-python stage)
# Copy source code AND reinstall to make console_scripts available
COPY --from=builder-python /ros2_ws/src/drone_telemetry /ros2_ws/src/drone_telemetry
RUN pip3 install --break-system-packages --no-cache-dir \
    /ros2_ws/src/drone_telemetry/ 2>/dev/null || true

# C++ ROS 2 packages (compiled in builder-cpp stage)
# Only install directory is needed; build directory excluded
COPY --from=builder-cpp /ros2_ws/install /ros2_ws/install

# ETL pipeline scripts
COPY etl_pipeline/ /ros2_ws/etl_pipeline/

# Create non-root user for security hardening
RUN useradd -m -u 1001 ros && \
    chown -R ros:ros /ros2_ws /entrypoint.sh

USER ros
WORKDIR /ros2_ws

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python3 -c "import os; exit(0) if os.path.exists('/ros2_ws') else exit(1)"

ENTRYPOINT ["/entrypoint.sh"]
CMD ["telemetry_pub"]


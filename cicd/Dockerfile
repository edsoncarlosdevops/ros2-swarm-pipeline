FROM ros:jazzy-ros-base AS builder

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-pip \
    python3-colcon-common-extensions \
    ccache \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /ros2_ws
COPY ros2_nodes/drone_telemetry/ /ros2_ws/drone_telemetry/

RUN pip3 install /ros2_ws/drone_telemetry/

FROM ros:jazzy-ros-base AS runtime

ENV DEBIAN_FRONTEND=noninteractive

# ROS 2 tools + MCAP storage (nativo no Jazzy)
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-pip \
    ros-jazzy-rosbag2 \
    ros-jazzy-rosbag2-storage-mcap \
    && rm -rf /var/lib/apt/lists/*

# Dependencias Python do ETL
RUN PIP_REQUIRE_VIRTUALENV=false pip3 install --no-cache-dir \
    duckdb>=1.0.0 \
    pandas>=2.0.0 \
    pyarrow>=14.0.0 \
    mcap>=1.4.0 \
    mcap-ros2-support>=0.5.0

COPY --from=builder /ros2_ws/drone_telemetry /ros2_ws/drone_telemetry
COPY cicd/entrypoint.sh /entrypoint.sh
COPY etl_pipeline/ /ros2_ws/etl_pipeline/

RUN chmod +x /entrypoint.sh

WORKDIR /ros2_ws

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python3", "/ros2_ws/drone_telemetry/drone_telemetry/drone_telemetry_pub.py"]

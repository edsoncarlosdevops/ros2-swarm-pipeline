FROM ros:humble-ros-base-jammy AS builder
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-pip \
    python3-colcon-common-extensions \
    ccache \
    && rm -rf /var/lib/apt/lists/*


WORKDIR /ros2_ws
COPY ros2_nodes/ src/ros2_nodes/

RUN colcon build --symlink-install --parallel-workers $(nproc)

FROM ros:humble-ros-base-jammy AS runtime
COPY --from=builder /ros2_ws/install /ros2_ws/install
COPY cicd/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
WORKDIR /ros2_ws
ENTRYPOINT ["/entrypoint.sh"]
CMD ["ros2", "run", "drone_telemetry", "drone_telemetry_pub"]

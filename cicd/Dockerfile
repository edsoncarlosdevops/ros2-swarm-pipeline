# ============================================================================
# ROS 2 Swarm Pipeline - Dockerfile Multi-stage Otimizado
#
# Otimizacoes:
#   1. Layer caching: requirements.txt ANTES do codigo fonte
#   2. Imagem final menor: apt clean + USER nao-root
#   3. Healthcheck para monitoramento
#   4. Pip cache separado para reuso entre stages
# ============================================================================

# --- Stage 1: Builder (dependencias + build do package ROS 2) ---
FROM ros:jazzy-ros-base AS builder

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-pip \
    python3-colcon-common-extensions \
    ccache \
    && rm -rf /var/lib/apt/lists/*

# Layer cache 1: dependencias Python (so refaz se requirements mudar)
COPY ros2_nodes/drone_telemetry/setup.py \
     ros2_nodes/drone_telemetry/package.xml \
     /ros2_ws/drone_telemetry/
RUN pip3 install --break-system-packages --no-cache-dir \
    /ros2_ws/drone_telemetry/ 2>/dev/null || true

# Layer cache 2: codigo fonte (so refaz se codigo mudar)
COPY ros2_nodes/drone_telemetry/ /ros2_ws/drone_telemetry/
RUN pip3 install --break-system-packages --no-cache-dir \
    /ros2_ws/drone_telemetry/

# --- Stage 2: Runtime (imagem final enxuta) ---
FROM ros:jazzy-ros-base AS runtime

ENV DEBIAN_FRONTEND=noninteractive
ENV ROS_DOMAIN_ID=42

# Layer cache 1: dependencias do sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-pip \
    ros-jazzy-rosbag2 \
    ros-jazzy-rosbag2-storage-mcap \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /tmp/*

# Layer cache 2: dependencias Python (so refaz se requirements.txt mudar)
COPY etl_pipeline/requirements.txt /tmp/requirements.txt
RUN pip3 install --break-system-packages --no-cache-dir \
    -r /tmp/requirements.txt \
    && rm -rf ~/.cache/pip

# Layer cache 3: entrypoint
COPY cicd/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Layer cache 4: codigo do package ROS 2 (so refaz se algo mudar)
COPY --from=builder /ros2_ws/drone_telemetry /ros2_ws/drone_telemetry

# Layer cache 5: pipeline ETL
COPY etl_pipeline/ /ros2_ws/etl_pipeline/

# Cria usuario nao-root para seguranca
RUN useradd -m -u 1001 ros && \
    chown -R ros:ros /ros2_ws /entrypoint.sh

USER ros
WORKDIR /ros2_ws

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python3 -c "import os; exit(0) if os.path.exists('/ros2_ws') else exit(1)"

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python3", "-m", "drone_telemetry.telemetry.publisher"]

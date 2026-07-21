#!/bin/bash
set -e

# Source ROS 2 distribution environment
source /opt/ros/jazzy/setup.bash

# Source colcon workspace environment (C++ nodes) if available.
# The workspace may have broken paths when copied across build stages,
# so we use set +e to avoid hard failures.
if [ -f "/ros2_ws/install/setup.bash" ]; then
  echo "Sourcing colcon workspace: /ros2_ws/install/setup.bash"
  set +e
  source /ros2_ws/install/setup.bash 2>/dev/null
  set -e
fi

exec "$@"
#!/bin/bash
set -e

# Source ROS 2 distribution environment
source /opt/ros/jazzy/setup.bash

# Source colcon workspace environment (C++ nodes) if available
# The workspace may not exist in all deployment scenarios
if [ -f "/ros2_ws/install/setup.bash" ]; then
  echo "Sourcing colcon workspace: /ros2_ws/install/setup.bash"
  source /ros2_ws/install/setup.bash
else
  echo "Colcon workspace not found. C++ nodes may not be available."
fi

exec "$@"

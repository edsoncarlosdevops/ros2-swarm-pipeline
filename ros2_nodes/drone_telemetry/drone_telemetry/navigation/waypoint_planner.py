#!/usr/bin/env python3
"""
Waypoint Planner - ROS 2 Node (Demonstration / Mock Navigation)

Subscribes to /drone/odometry and publishes navigation commands on /drone/cmd_vel.
Simulates a navigation node that calculates velocity commands to follow
a sequence of predefined waypoints based on the drone's current position.

NOTE: This is a demonstration node — the published /drone/cmd_vel topic is NOT
consumed by telemetry_pub or any other node in this pipeline. The navigation
loop is open-loop (mock). In a real system, a flight controller would consume
cmd_vel to close the control loop.

Flow (open-loop mock):
  telemetry_pub (odometry) -> waypoint_planner (cmd_vel) -> [not consumed]

Concepts:
  - ROS 2 Subscriber (receives odometry)
  - ROS 2 Publisher (sends cmd_vel)
  - Basic navigation logic (simplified proportional control)
  - Open-loop demonstration of topic-based node communication
"""

import rclpy
from rclpy.node import Node
from nav_msgs.msg import Odometry
from geometry_msgs.msg import Twist
import math


class WaypointPlanner(Node):
    """Waypoint planner.

    When it receives odometry from the drone, it calculates the velocity command
    to follow an L-shaped trajectory (fixed waypoints)."""

    def __init__(self):
        super().__init__('waypoint_planner_python')

        # === Predefined waypoints ===
        self.waypoints = [
            {"x": 50.0, "y": 0.0, "z": 10.0},
            {"x": 50.0, "y": 50.0, "z": 15.0},
            {"x": 0.0, "y": 50.0, "z": 20.0},
            {"x": 0.0, "y": 0.0, "z": 10.0},
        ]
        self.current_wp = 0
        self.max_speed = 5.0  # m/s
        self.proximity_threshold = 2.0  # meters to consider "arrived"

        # === Publishers ===
        self.cmd_vel_pub = self.create_publisher(
            Twist,
            '/drone/cmd_vel',
            10
        )

        # === Subscribers ===
        self.odom_sub = self.create_subscription(
            Odometry,
            '/drone/odometry',
            self.odom_callback,
            10
        )

        self.get_logger().info('Waypoint Planner started!')
        self.get_logger().info(f'Waypoints: {len(self.waypoints)} targets')
        self._log_current_target()

    def _log_current_target(self):
        wp = self.waypoints[self.current_wp]
        self.get_logger().info(
            f'Headed to waypoint {self.current_wp + 1}: '
            f'({wp["x"]:.1f}, {wp["y"]:.1f}, {wp["z"]:.1f})'
        )

    def odom_callback(self, msg):
        """Called every time odometry is received."""
        px = msg.pose.pose.position.x
        py = msg.pose.pose.position.y
        pz = msg.pose.pose.position.z

        target = self.waypoints[self.current_wp]

        # Calculate distance to waypoint
        dx = target["x"] - px
        dy = target["y"] - py
        dz = target["z"] - pz
        distance = math.sqrt(dx*dx + dy*dy + dz*dz)

        # If arrived at waypoint, advance to the next one
        if distance < self.proximity_threshold:
            self.current_wp = (self.current_wp + 1) % len(self.waypoints)
            self._log_current_target()
            target = self.waypoints[self.current_wp]
            dx = target["x"] - px
            dy = target["y"] - py
            dz = target["z"] - pz
            distance = math.sqrt(dx*dx + dy*dy + dz*dz)

        # Velocity command proportional to distance
        cmd = Twist()
        if distance > 0:
            cmd.linear.x = min(self.max_speed, dx / distance * self.max_speed * 0.5)
            cmd.linear.y = min(self.max_speed, dy / distance * self.max_speed * 0.5)
            cmd.linear.z = min(self.max_speed, dz / distance * self.max_speed * 0.5)

        # Angle to target (yaw)
        target_angle = math.atan2(dy, dx)
        current_angle = 0.0  # simplified
        cmd.angular.z = (target_angle - current_angle) * 0.5

        self.cmd_vel_pub.publish(cmd)

    def get_waypoint_status(self):
        """Return current status for logging."""
        wp = self.waypoints[self.current_wp]
        return {
            "current_wp": self.current_wp + 1,
            "total_wp": len(self.waypoints),
            "target_x": wp["x"],
            "target_y": wp["y"],
            "target_z": wp["z"],
        }


def main(args=None):
    rclpy.init(args=args)
    node = WaypointPlanner()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()

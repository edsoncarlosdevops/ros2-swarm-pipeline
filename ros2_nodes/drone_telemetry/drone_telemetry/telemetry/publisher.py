#!/usr/bin/env python3
"""
Drone Telemetry Publisher - ROS 2 Node

Simulates a drone publishing telemetry data (position, velocity, altitude)
to the ROS 2 network. This is exactly how real drones in a Swarm team
publish their sensor data for other nodes to consume.

Conceitos demonstrados:
  - ROS 2 Node lifecycle (init, spin, destroy)
  - Publisher pattern (talker)
  - Message types (Odometry)
  - Timer-based publishing at 10Hz
"""

import rclpy
from rclpy.node import Node
from nav_msgs.msg import Odometry
import math


class DroneTelemetryPublisher(Node):
    """
    Simulates a drone publishing telemetry data.

    In a Swarm robotics context, each real drone has nodes like this one
    publishing: GPS position, IMU data, velocity.
    Other nodes (control, navigation) subscribe to these topics.
    """

    def __init__(self):
        # Node name - must be unique in the ROS 2 network
        super().__init__('drone_telemetry_publisher')

        # === Publishers ===
        # Each publisher announces "I will publish data on this topic"
        self.odom_pub = self.create_publisher(
            Odometry,           # Message type
            '/drone/odometry',  # Topic name (like a channel)
            10                  # Queue size
        )

        # === Timer ===
        # Publish at 10Hz (every 100ms) - same frequency as real drones
        self.timer = self.create_timer(0.1, self.publish_telemetry)

        # === State ===
        self.start_time = self.get_clock().now().nanoseconds
        self.altitude = 10.0  # meters

        self.get_logger().info('Publisher started! Publishing at 10Hz')

    def publish_telemetry(self):
        """Called every 100ms. Simulates drone flying in a circle."""
        now = self.get_clock().now()
        t = (now.nanoseconds - self.start_time) / 1e9  # seconds

        # Circular movement: radius 50m at 5m/s
        radius = 50.0
        speed = 5.0
        angular_speed = speed / radius

        x = radius * math.cos(angular_speed * t)
        y = radius * math.sin(angular_speed * t)
        z = self.altitude

        vx = -speed * math.sin(angular_speed * t)
        vy = speed * math.cos(angular_speed * t)
        vz = 0.0

        # Create and publish Odometry message
        odom = Odometry()
        odom.header.stamp = now.to_msg()
        odom.header.frame_id = 'world'
        odom.child_frame_id = 'drone_base_link'

        odom.pose.pose.position.x = x
        odom.pose.pose.position.y = y
        odom.pose.pose.position.z = z

        odom.twist.twist.linear.x = vx
        odom.twist.twist.linear.y = vy
        odom.twist.twist.linear.z = vz

        self.odom_pub.publish(odom)

        # Log every second
        if int(t) % 1 == 0 and int(t * 10) % 10 == 0:
            self.get_logger().info(
                f'Position: ({x:.1f}, {y:.1f}, {z:.1f}) | '
                f'Vel: ({vx:.1f}, {vy:.1f}, {vz:.1f})'
            )


def main(args=None):
    rclpy.init(args=args)
    node = DroneTelemetryPublisher()

    try:
        rclpy.spin(node)  # Keeps node alive
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()

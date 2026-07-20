#!/usr/bin/env python3
"""
Drone Telemetry Subscriber - ROS 2 Node

Subscribes to drone telemetry data and processes it.
In a Swarm team, subscribers are used by:
  - Control team: receives position, sends motor commands
  - Navigation team: receives data, plans routes
  - Ground station: logs data for post-mission analysis

Conceitos demonstrados:
  - ROS 2 Subscriber pattern (listener)
  - Callback functions (event-driven)
  - Data logging for ETL pipeline
"""

import rclpy
from rclpy.node import Node
from nav_msgs.msg import Odometry
import json
import os
from datetime import datetime


class DroneTelemetrySubscriber(Node):
    """
    Listens to drone telemetry and saves data for analysis.

    This is the first step of the ETL pipeline:
    - EXTRACT: receive ROS 2 messages
    - Later we TRANSFORM and LOAD into Parquet/DuckDB
    """

    def __init__(self):
        super().__init__('drone_telemetry_subscriber')

        # === Subscribers ===
        self.odom_sub = self.create_subscription(
            Odometry,
            '/drone/odometry',
            self.odom_callback,
            10
        )

        # === Data storage for ETL ===
        self.telemetry_data = []
        self.max_samples = 1000
        self.message_count = 0
        self.start_time = self.get_clock().now()

        # Create output directory
        self.output_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            '..', 'data', 'raw'
        )
        os.makedirs(self.output_dir, exist_ok=True)

        self.get_logger().info('Subscriber started! Listening for telemetry...')

    def odom_callback(self, msg):
        """Called EVERY TIME a message arrives on /drone/odometry."""
        self.message_count += 1

        data = {
            'timestamp': msg.header.stamp.sec + msg.header.stamp.nanosec / 1e9,
            'x': msg.pose.pose.position.x,
            'y': msg.pose.pose.position.y,
            'z': msg.pose.pose.position.z,
            'vx': msg.twist.twist.linear.x,
            'vy': msg.twist.twist.linear.y,
            'vz': msg.twist.twist.linear.z,
        }

        self.telemetry_data.append(data)

        if len(self.telemetry_data) > self.max_samples:
            self.telemetry_data.pop(0)

        if self.message_count % 100 == 0:
            elapsed = (self.get_clock().now() - self.start_time).nanoseconds / 1e9
            self.get_logger().info(
                f'Received {self.message_count} msgs in {elapsed:.1f}s | '
                f'Pos: ({data["x"]:.1f}, {data["y"]:.1f}, {data["z"]:.1f})'
            )

    def save_data(self):
        """Save collected data to JSON (pre-ETL)."""
        if not self.telemetry_data:
            self.get_logger().warn('No data to save')
            return

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'drone_telemetry_{timestamp}.json'
        filepath = os.path.join(self.output_dir, filename)

        with open(filepath, 'w') as f:
            json.dump(self.telemetry_data, f, indent=2)

        self.get_logger().info(f'Saved {len(self.telemetry_data)} samples to {filepath}')
        return filepath


def main(args=None):
    rclpy.init(args=args)
    node = DroneTelemetrySubscriber()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.save_data()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()

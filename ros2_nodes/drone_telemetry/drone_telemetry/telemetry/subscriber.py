#!/usr/bin/env python3
"""
Drone Telemetry Subscriber - ROS 2 Node (MCAP Recorder)

Subscribes to drone telemetry data and records it in MCAP format
(ROS 2 native bag format with CDR binary encoding).

This is the EXTRACT step of the ETL pipeline:
  MCAP (CDR ROS2) → Parquet → DuckDB Analytics

Usage:
  ros2 run drone_telemetry telemetry_sub_python

  # Or with Docker:
  docker compose up telemetry_sub

Key concepts demonstrated:
  - ROS 2 Subscriber pattern (listener)
  - rosbag2_py SequentialWriter (MCAP recording)
  - Callback functions (event-driven)
  - Data pipeline integration (feeds into mcap_to_parquet.py)
"""

import rclpy
from rclpy.node import Node
from nav_msgs.msg import Odometry
from rosbag2_py import SequentialWriter, StorageOptions
from pathlib import Path
import os
import signal
import sys


class DroneTelemetrySubscriber(Node):
    """
    Listens to drone telemetry and records directly to MCAP format.

    This feeds the ETL pipeline with native ROS 2 bag files.
    No intermediate JSON — data goes straight from DDS to MCAP to Parquet.
    """

    def __init__(self):
        super().__init__('telemetry_sub_python')

        # === MCAP Output Directory ===
        # Use mounted Docker volume in production,
        # fall back to local path for development without Docker.
        self.output_dir = Path(os.environ.get(
            'TELEMETRY_DATA_DIR',
            str(Path(__file__).parent.parent.parent / 'data' / 'raw')
        )).resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # === rosbag2 MCAP Writer ===
        bag_path = str(self.output_dir / 'flight_mission')
        storage_options = StorageOptions(
            uri=bag_path,
            storage_id='mcap'  # ← MCAP format (ROS 2 native)
        )
        from rosbag2_py import ConverterOptions
        converter_options = ConverterOptions(
            input_serialization_format='cdr',
            output_serialization_format='cdr'
        )

        self.writer = SequentialWriter()
        self.writer.open(storage_options, converter_options)

        # === Subscribers ===
        self.odom_sub = self.create_subscription(
            Odometry,
            '/drone/odometry',
            self.odom_callback,
            10
        )

        # === State ===
        self.message_count = 0
        self.start_time = self.get_clock().now()

        self.get_logger().info(f'MCAP recording to: {bag_path}')
        self.get_logger().info('Subscribed to /drone/odometry')
        self.get_logger().info('Recording in MCAP (CDR ROS2) — ready for ETL pipeline')

    def odom_callback(self, msg):
        """Called EVERY TIME a message arrives on /drone/odometry."""
        self.message_count += 1

        # Write directly to MCAP using serialized CDR binary message
        from rclpy.serialization import serialize_message
        serialized_msg = serialize_message(msg)
        timestamp_ns = self.get_clock().now().nanoseconds

        try:
            self.writer.write(
                '/drone/odometry',
                serialized_msg,
                timestamp_ns
            )
        except TypeError:
            # Fallback if raw bytes conversion is expected
            self.writer.write(
                '/drone/odometry',
                bytes(serialized_msg),
                timestamp_ns
            )

        # Log progress every 100 messages
        if self.message_count % 100 == 0:
            elapsed = (self.get_clock().now() - self.start_time).nanoseconds / 1e9
            self.get_logger().info(
                f'Recorded {self.message_count} msgs in {elapsed:.1f}s | '
                f'Pos: ({msg.pose.pose.position.x:.1f}, '
                f'{msg.pose.pose.position.y:.1f}, '
                f'{msg.pose.pose.position.z:.1f})'
            )

    def close_writer(self):
        """Close MCAP writer gracefully."""
        if hasattr(self, 'writer') and self.writer is not None:
            self.get_logger().info(
                f'Closing MCAP writer ({self.message_count} total messages recorded)'
            )
            del self.writer
            self.writer = None


def main(args=None):
    rclpy.init(args=args)
    node = DroneTelemetrySubscriber()

    def shutdown(sig, frame):
        """Graceful shutdown: close MCAP writer before exiting."""
        node.get_logger().info('Shutdown signal received, closing MCAP writer...')
        node.close_writer()
        node.destroy_node()
        rclpy.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.close_writer()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()

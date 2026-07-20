#!/usr/bin/env python3
"""
ROS 2 Bag Recorder - Grava telemetria em formato MCAP

Usa rosbag2 para gravar os topics do drone em MCAP.
Depois o pipeline ETL le o MCAP e transforma em Parquet para DuckDB.

Uso:
  docker run --rm --network ros2-net ros2-drone-sim python3 /ros2_ws/bag_recorder.py
"""

import os
import sys
import signal
from pathlib import Path

import rclpy
from rclpy.node import Node
from rosbag2_py import SequentialWriter, StorageOptions, RecordOptions
from nav_msgs.msg import Odometry
from sensor_msgs.msg import BatteryState


class BagRecorder(Node):
    """Records drone telemetry to MCAP format."""

    def __init__(self):
        super().__init__("bag_recorder")
        
        # Configuração do bag
        self.bag_path = Path("/ros2_ws/data/mcap/flight_mission")
        self.bag_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Configura o writer MCAP
        storage_options = StorageOptions(
            uri=str(self.bag_path),
            storage_id="mcap"
        )
        record_options = RecordOptions()
        record_options.record_topics = [
            "/drone/odometry",
            "/drone/battery"
        ]
        
        self.writer = SequentialWriter()
        self.writer.open(storage_options, record_options)
        
        # Inscreve nos topics
        self.create_subscription(
            Odometry, "/drone/odometry", self.odom_callback, 10
        )
        self.create_subscription(
            BatteryState, "/drone/battery", self.battery_callback, 10
        )
        
        self.get_logger().info(f"Gravando MCAP em: {self.bag_path}")
        self.get_logger().info("Topics: /drone/odometry, /drone/battery")
        self.get_logger().info("Pressione Ctrl+C para parar e gerar Parquet...")
        
        self.msg_count = 0

    def odom_callback(self, msg):
        self.writer.write("/drone/odometry", msg, self.get_clock().now().to_msg())
        self.msg_count += 1
        if self.msg_count % 100 == 0:
            self.get_logger().info(f"Gravados {self.msg_count} odometry messages")

    def battery_callback(self, msg):
        self.writer.write("/drone/battery", msg, self.get_clock().now().to_msg())

    def stop_and_convert(self):
        """Fecha o bag e chama o ETL para converter MCAP -> Parquet -> DuckDB."""
        self.get_logger().info("Finalizando gravacao...")
        del self.writer  # Fecha o writer
        self.get_logger().info(f"MCAP salvo em: {self.bag_path}")
        
        # Chama o pipeline ETL
        self.get_logger().info("Iniciando conversao MCAP -> Parquet -> DuckDB...")
        sys.path.insert(0, "/ros2_ws/etl_pipeline")
        from mcap_to_parquet import main as etl_main
        etl_main()


def main(args=None):
    rclpy.init(args=args)
    recorder = BagRecorder()
    
    def shutdown(sig, frame):
        recorder.stop_and_convert()
        recorder.destroy_node()
        rclpy.shutdown()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    
    rclpy.spin(recorder)


if __name__ == "__main__":
    main()

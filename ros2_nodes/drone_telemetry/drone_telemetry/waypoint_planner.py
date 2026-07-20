#!/usr/bin/env python3
"""
Waypoint Planner - ROS 2 Node

Assina /drone/odometry e publica comandos de navegacao em /drone/cmd_vel.
Simula um node de navegacao que calcula o proximo waypoint baseado na
posicao atual do drone.

Fluxo:
  telemetry_pub (odometry) --> waypoint_planner (cmd_vel) --> telemetry_pub (recebe comando)

Conceitos:
  - ROS 2 Subscriber (recebe odometry)
  - ROS 2 Publisher (envia cmd_vel)
  - Logica de navegacao basica (PID simplificado)
  - Dependencia entre nodes via topicos
"""

import rclpy
from rclpy.node import Node
from nav_msgs.msg import Odometry
from geometry_msgs.msg import Twist
import math


class WaypointPlanner(Node):
    """
    Planejador de waypoints.
    
    Quando recebe odometry do drone, calcula o comando de velocidade
    para seguir uma trajetoria em forma de L (waypoints fixos).
    """

    def __init__(self):
        super().__init__('waypoint_planner')

        # === Waypoints pre-definidos ===
        self.waypoints = [
            {"x": 50.0, "y": 0.0, "z": 10.0},
            {"x": 50.0, "y": 50.0, "z": 15.0},
            {"x": 0.0, "y": 50.0, "z": 20.0},
            {"x": 0.0, "y": 0.0, "z": 10.0},
        ]
        self.current_wp = 0
        self.max_speed = 5.0  # m/s
        self.proximity_threshold = 2.0  # metros para considerar "chegou"

        # === Publishers ===
        self.cmd_vel_pub = self.create_publisher(
            Twist,           # Tipo: linear.x, angular.z
            '/drone/cmd_vel', # Topico de comando
            10
        )

        # === Subscribers ===
        self.odom_sub = self.create_subscription(
            Odometry,
            '/drone/odometry',
            self.odom_callback,
            10
        )

        self.get_logger().info('Waypoint Planner iniciado!')
        self.get_logger().info(f'Waypoints: {len(self.waypoints)} alvos')
        self._log_current_target()

    def _log_current_target(self):
        wp = self.waypoints[self.current_wp]
        self.get_logger().info(
            f'Rumo ao waypoint {self.current_wp + 1}: '
            f'({wp["x"]:.1f}, {wp["y"]:.1f}, {wp["z"]:.1f})'
        )

    def odom_callback(self, msg):
        """Called every time odometry is received."""
        px = msg.pose.pose.position.x
        py = msg.pose.pose.position.y
        pz = msg.pose.pose.position.z

        target = self.waypoints[self.current_wp]

        # Calcula distancia ate o waypoint
        dx = target["x"] - px
        dy = target["y"] - py
        dz = target["z"] - pz
        distance = math.sqrt(dx*dx + dy*dy + dz*dz)

        # Se chegou no waypoint, avanca para o proximo
        if distance < self.proximity_threshold:
            self.current_wp = (self.current_wp + 1) % len(self.waypoints)
            self._log_current_target()
            target = self.waypoints[self.current_wp]
            dx = target["x"] - px
            dy = target["y"] - py
            dz = target["z"] - pz
            distance = math.sqrt(dx*dx + dy*dy + dz*dz)

        # Comando de velocidade proporcional a distancia
        cmd = Twist()
        if distance > 0:
            cmd.linear.x = min(self.max_speed, dx / distance * self.max_speed * 0.5)
            cmd.linear.y = min(self.max_speed, dy / distance * self.max_speed * 0.5)
            cmd.linear.z = min(self.max_speed, dz / distance * self.max_speed * 0.5)

        # Angulo para o target (yaw)
        target_angle = math.atan2(dy, dx)
        current_angle = 0.0  # simplificado
        cmd.angular.z = (target_angle - current_angle) * 0.5

        self.cmd_vel_pub.publish(cmd)

    def get_waypoint_status(self):
        """Retorna status atual para logging."""
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

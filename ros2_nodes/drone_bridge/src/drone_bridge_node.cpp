/**
 * @file drone_bridge_node.cpp
 * @brief C++ bridge node demonstrating cross-language DDS communication
 *
 * This node subscribes to /drone/odometry (nav_msgs/Odometry) published
 * by the Python drone_telemetry.telemetry.publisher node at 10 Hz.
 *
 * Cross-language communication flow:
 *
 *   Python Publisher (drone_telemetry_pub) --DDS--> C++ Subscriber (this node)
 *       |                                              |
 *       |  /drone/odometry (nav_msgs/Odometry)          | Logs and exposes
 *       |  @ 10 Hz via Fast DDS                       | telemetry data
 *
 * This demonstrates that ROS 2's DDS middleware is language-agnostic:
 * publishers and subscribers communicate regardless of whether they
 * use rclpy (Python) or rclcpp (C++).
 */

#include <rclcpp/rclcpp.hpp>
#include <nav_msgs/msg/odometry.hpp>
#include <memory>
#include <string>
#include <functional>
#include <iomanip>
#include <sstream>

using namespace std::chrono_literals;

class DroneBridgeNode : public rclcpp::Node
{
public:
  DroneBridgeNode()
    : Node("drone_bridge_node"),
      message_count_(0)
  {
    // Subscribe to /drone/odometry (same topic as Python subscriber)
    odom_sub_ = this->create_subscription<nav_msgs::msg::Odometry>(
      "/drone/odometry",
      10,
      std::bind(&DroneBridgeNode::odom_callback, this, std::placeholders::_1)
    );

    // Status timer prints health information every 5 seconds
    status_timer_ = this->create_wall_timer(
      5s,
      std::bind(&DroneBridgeNode::status_callback, this)
    );

    RCLCPP_INFO(this->get_logger(), "=== Drone Bridge Node (C++) ===");
    RCLCPP_INFO(this->get_logger(), "Subscribed to: /drone/odometry");
    RCLCPP_INFO(this->get_logger(), "Waiting for Python-published telemetry via DDS...");
  }

private:
  void odom_callback(const nav_msgs::msg::Odometry::SharedPtr msg)
  {
    message_count_++;

    const auto& pos = msg->pose.pose.position;
    const auto& vel = msg->twist.twist.linear;

    // Log first message as proof of cross-language DDS communication
    if (message_count_ == 1) {
      RCLCPP_INFO(
        this->get_logger(),
        "CROSS-LANGUAGE DDS OK! Python publisher -> C++ subscriber via /drone/odometry"
      );
      RCLCPP_INFO(
        this->get_logger(),
        "First position: (%.2f, %.2f, %.2f)", pos.x, pos.y, pos.z
      );
    }

    // Log summary every 100 messages to avoid excessive output
    if (message_count_ % 100 == 1) {
      std::stringstream ss;
      ss << std::fixed << std::setprecision(2);
      ss << "Bridge [" << message_count_ << "] "
         << "Pos: (" << pos.x << ", " << pos.y << ", " << pos.z << ") | "
         << "Vel: (" << vel.x << ", " << vel.y << ", " << vel.z << ")";
      RCLCPP_INFO(this->get_logger(), "%s", ss.str().c_str());
    }
  }

  void status_callback()
  {
    if (message_count_ == 0) {
      RCLCPP_WARN(
        this->get_logger(),
        "No messages received. Is the Python publisher running?"
      );
    } else {
      double elapsed = this->now().seconds();
      double rate = elapsed > 0 ? message_count_ / elapsed : 0;
      RCLCPP_INFO(
        this->get_logger(),
        "Bridge health: %zu messages received @ ~%.1f Hz",
        message_count_,
        rate
      );
    }
  }

  rclcpp::Subscription<nav_msgs::msg::Odometry>::SharedPtr odom_sub_;
  rclcpp::TimerBase::SharedPtr status_timer_;
  size_t message_count_;
};

int main(int argc, char * argv[])
{
  rclcpp::init(argc, argv);
  auto node = std::make_shared<DroneBridgeNode>();
  RCLCPP_INFO(node->get_logger(), "DroneBridgeNode spinning. Waiting for Python telemetry...");
  rclcpp::spin(node);
  RCLCPP_INFO(node->get_logger(), "Shutting down DroneBridgeNode.");
  rclcpp::shutdown();
  return 0;
}

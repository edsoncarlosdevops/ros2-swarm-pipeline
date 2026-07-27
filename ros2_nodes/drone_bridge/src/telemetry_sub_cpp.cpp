/**
 * @file telemetry_sub_cpp.cpp
 * @brief C++ bridge node demonstrating cross-language DDS communication
 *
 * This node subscribes to /drone/odometry (nav_msgs/Odometry) published
 * by the Python telemetry_pub_python node at 10 Hz.
 *
 * Cross-language communication flow:
 *
 *   Python Publisher (telemetry_pub_python) --DDS--> C++ Subscriber (this node)
 *       |                                              |
 *       |  /drone/odometry (nav_msgs/Odometry)          | Logs and exposes
 *       |  @ 10 Hz via Fast DDS                       | telemetry data
 *
 * This demonstrates that ROS 2's DDS middleware is language-agnostic:
 * publishers and subscribers communicate regardless of whether they
 * use rclpy (Python) or rclcpp (C++).
 *
 * Auto-shutdown: If no messages are received within 30 seconds (e.g., in CI
 * environments without a publisher), the node shuts down automatically.
 * This prevents CI jobs from hanging indefinitely.
 */

#include <rclcpp/rclcpp.hpp>
#include <nav_msgs/msg/odometry.hpp>
#include <memory>
#include <string>
#include <functional>
#include <iomanip>
#include <sstream>

using namespace std::chrono_literals;

class TelemetrySubCpp : public rclcpp::Node
{
public:
  TelemetrySubCpp()
    : Node("telemetry_sub_cpp"),
      message_count_(0),
      start_time_(this->now())
  {
    // Subscribe to /drone/odometry (same topic as Python subscriber)
    odom_sub_ = this->create_subscription<nav_msgs::msg::Odometry>(
      "/drone/odometry",
      10,
      std::bind(&TelemetrySubCpp::odom_callback, this, std::placeholders::_1)
    );

    // Status timer prints health information every 5 seconds
    status_timer_ = this->create_wall_timer(
      5s,
      std::bind(&TelemetrySubCpp::status_callback, this)
    );

    // Auto-shutdown timer: shuts down after 30s if no messages received.
    // Prevents CI jobs (colcon-build) from hanging indefinitely when
    // there is no publisher running in the same container.
    shutdown_timer_ = this->create_wall_timer(
      30s,
      std::bind(&TelemetrySubCpp::shutdown_callback, this)
    );

    RCLCPP_INFO(this->get_logger(), "=== Telemetry Subscriber C++ (cross-lang proof) ===");
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
      ss << "Sub [" << message_count_ << "] "
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
      double elapsed = (this->now() - start_time_).seconds();
      double rate = elapsed > 0 ? message_count_ / elapsed : 0;
      RCLCPP_INFO(
        this->get_logger(),
        "Sub health: %zu messages received @ ~%.1f Hz",
        message_count_,
        rate
      );
    }
  }

  void shutdown_callback()
  {
    if (message_count_ > 0) {
      // Messages received, cancel auto-shutdown
      shutdown_timer_->cancel();
      return;
    }

    auto elapsed = (this->now() - start_time_).seconds();
    RCLCPP_INFO(
      this->get_logger(),
      "No messages after %.0f seconds. Shutting down (CI auto-detected).",
      elapsed
    );
    rclcpp::shutdown();
  }

  rclcpp::Subscription<nav_msgs::msg::Odometry>::SharedPtr odom_sub_;
  rclcpp::TimerBase::SharedPtr status_timer_;
  rclcpp::TimerBase::SharedPtr shutdown_timer_;
  size_t message_count_;
  rclcpp::Time start_time_;
};

int main(int argc, char * argv[])
{
  rclcpp::init(argc, argv);
  auto node = std::make_shared<TelemetrySubCpp>();
  RCLCPP_INFO(node->get_logger(), "TelemetrySubCpp spinning. Waiting for Python telemetry...");
  rclcpp::spin(node);
  RCLCPP_INFO(node->get_logger(), "Shutting down TelemetrySubCpp.");
  rclcpp::shutdown();
  return 0;
}

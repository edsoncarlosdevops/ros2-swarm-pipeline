  rclcpp::Subscription<nav_msgs::msg::Odometry>::SharedPtr odom_sub_;
  rclcpp::TimerBase::SharedPtr status_timer_;
  rclcpp::TimerBase::SharedPtr shutdown_timer_;
  size_t message_count_;
  rclcpp::Time start_time_;
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


  DroneBridgeNode()
    : Node("drone_bridge_node"),
      message_count_(0),
      start_time_(this->now())
  {

    // Status timer prints health information every 5 seconds
    status_timer_ = this->create_wall_timer(
      5s,
      std::bind(&DroneBridgeNode::status_callback, this)
    );

    // Auto-shutdown timer: shuts down after 30s if no messages received.
    // Prevents CI jobs (colcon-build) from hanging indefinitely when
    // there is no publisher running in the same container.
    shutdown_timer_ = this->create_wall_timer(
      30s,
      std::bind(&DroneBridgeNode::shutdown_callback, this)
    );




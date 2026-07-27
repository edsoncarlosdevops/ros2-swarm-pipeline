cmake_minimum_required(VERSION 3.16)
project(drone_bridge)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(nav_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(std_msgs REQUIRED)

add_executable(telemetry_sub_cpp
  src/telemetry_sub_cpp.cpp
)

ament_target_dependencies(telemetry_sub_cpp
  rclcpp
  nav_msgs
  geometry_msgs
  sensor_msgs
  std_msgs
)

install(TARGETS
  telemetry_sub_cpp
  DESTINATION lib/${PROJECT_NAME}
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  ament_lint_auto_find_test_dependencies()
endif()

ament_package()

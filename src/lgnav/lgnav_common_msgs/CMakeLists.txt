cmake_minimum_required(VERSION 3.5)
project(lgnav_common_msgs)

# Default to C99
if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 14)
endif()
if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# find dependencies
find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(std_msgs REQUIRED)
find_package(std_srvs REQUIRED)

set(msg_files
  "msg/ActionPath.msg"
  "msg/Attribute.msg"
  "msg/Head.msg"
  "msg/Node.msg"
  "msg/Orientation.msg"
  "msg/PathMsg.msg"
  "msg/Pose.msg"
  "msg/Position.msg"
  "msg/PosXY32.msg"
  "msg/PosXYDeg.msg"
  "msg/PosXYDeg32.msg"
  "msg/PosXYZDeg.msg"
  "msg/PosXYZDeg32.msg"
  "msg/Timestamp.msg"
  "msg/IpcMmapInfo.msg"
)

set(srv_files
  "srv/Bool.srv"
  "srv/Float32.srv"
  "srv/Float64.srv"
  "srv/GetStringArray.srv"
  "srv/Int32.srv"
  "srv/PathMsg.srv"
  "srv/PosXYDeg.srv"
  "srv/PosXYDeg32.srv"
  "srv/PosXYZDeg.srv"
  "srv/Requester.srv"
  "srv/State.srv"
  "srv/String.srv"
  "srv/UInt16.srv"
  "srv/UInt32.srv"
  "srv/UInt8.srv"
)

rosidl_generate_interfaces(${PROJECT_NAME}
    ${msg_files}
    ${srv_files}
    DEPENDENCIES std_msgs
    DEPENDENCIES std_srvs
)

ament_export_dependencies(rosidl_default_runtime)

# if(BUILD_TESTING)
#   find_package(ament_lint_auto REQUIRED)
#   # the following line skips the linter which checks for copyrights
#   # uncomment the line when a copyright and license is not present in all source files
#   #set(ament_cmake_copyright_FOUND TRUE)
#   # the following line skips cpplint (only works in a git repo)
#   # uncomment the line when this package is not in a git repo
#   #set(ament_cmake_cpplint_FOUND TRUE)
#   ament_lint_auto_find_test_dependencies()
# endif()

ament_package()

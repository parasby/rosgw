cmake_minimum_required(VERSION 3.5)
project(ebme_interfaces)

# Default to C99
if(NOT CMAKE_C_STANDARD)
  set(CMAKE_C_STANDARD 99)
endif()

# Default to C++14
if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 14)
endif()

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# find dependencies
find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(geometry_msgs REQUIRED)
# uncomment the following section in order to fill in
# further dependencies manually.
# find_package(<dependency> REQUIRED)

set(msg_files 
  "msg/DeviceInfo.msg"
  "msg/SensorInfo.msg"
  "msg/SensorStatus.msg"
  "msg/ErrorInfo.msg"
  "msg/ExpendableInfo.msg"
  "msg/LocationInfo.msg"
  "msg/MapInfo.msg"
  "msg/PushMessageInfo.msg"
  "msg/MessageInfo.msg"
  "msg/NoticeInfo.msg"
  "msg/NoticeInfoList.msg"
  "msg/ModeInfo.msg"
  "msg/ActionInfo.msg"
  "msg/MovePathInfo.msg"
  "msg/BatteryInfo.msg"
  "msg/PoiInfo.msg"
  "msg/ResourceInfo.msg"
  "msg/ResourceInfoList.msg"
  "msg/Response.msg"
  "msg/Command.msg"
  "msg/DeviceId.msg"
  "msg/HldsLidarInfo.msg"
  "msg/HldsLidarInfoList.msg"
  "msg/OrderInfo.msg"
  "msg/OrderInfoList.msg"
  "msg/ObjectDetectionInfo.msg"
  "msg/ObjectDetectionInfoList.msg"
)

set(srv_files  
  "srv/RegisterInfo.srv"
  "srv/ReturnBool.srv"
  "srv/StringValue.srv"
)

rosidl_generate_interfaces(${PROJECT_NAME}
  ${msg_files}
  ${srv_files}
  DEPENDENCIES builtin_interfaces geometry_msgs std_msgs
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  # the following line skips the linter which checks for copyrights
  # uncomment the line when a copyright and license is not present in all source files
  #set(ament_cmake_copyright_FOUND TRUE)
  # the following line skips cpplint (only works in a git repo)
  # uncomment the line when this package is not in a git repo
  #set(ament_cmake_cpplint_FOUND TRUE)
  ament_lint_auto_find_test_dependencies()
endif()

ament_export_dependencies(rosidl_default_runtime)
ament_package()

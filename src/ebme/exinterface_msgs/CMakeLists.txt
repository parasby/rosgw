cmake_minimum_required(VERSION 3.5)
project(exinterface_msgs)

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

find_package(lgnav_common_msgs REQUIRED)
#find_package(slam_msgs REQUIRED)

set(msg_files
  "msg/NaviMeterAge.msg"
  "msg/NaviDrivingMainOption.msg"
  "msg/DrivingModeMainOption.msg"
  "msg/NaviDrivingElevatorOption.msg"
  "msg/NaviDrivingSubOption.msg"
  "msg/MultiFloor.msg"
  "msg/MultiPoint.msg"
  "msg/NaviMultiGlobalPath.msg"
  "msg/PFMotionStatus.msg"
  "msg/DoorMultiPoint.msg"
  "msg/DrivingModeElevatorOffset.msg"
  "msg/PosID.msg"
  "msg/NaviBasicStatus.msg"
  "msg/NaviSlamVersion.msg"
  "msg/MapVersion.msg"
  "msg/NaviStatus.msg"
  "msg/NaviStatusOld.msg"
  "msg/ActionPos.msg"
  "msg/ActionBasic.msg"
  "msg/NaviElevHeight.msg"
  "msg/NaviVersion.msg"
  "msg/NaviMapVersion.msg"
  "msg/DrivingModeElevatorOption.msg"
  "msg/VersionInfo.msg"
  "msg/NaviDistance.msg"
  "msg/GlobalMultiPoint.msg"
  "msg/DrivingModeSubOption.msg"
  "msg/NaviDoorPath.msg"
  "msg/MapManagerInstanceInfo.msg"
)

set(srv_files
  "srv/NaviMultiGlobalPahtReq.srv"
  "srv/NaviMultiFloorPath.srv"
  "srv/NaviMultiFloorPathReq.srv"
  "srv/NaviGlobalPath.srv"
  "srv/NaviGlobalPathReq.srv"
  "srv/NaviStateOnSleep.srv"
  "srv/NaviDrivingMainOptionReq.srv"
  "srv/NaviDistanceReq.srv"
  "srv/NaviSlamVersionReq.srv"
  "srv/NaviDrivingElevatorOptionReq.srv"
  "srv/NaviHomeSet.srv"
  "srv/NaviMapVersionReq.srv"
  "srv/NaviDoorPathReq.srv"
  "srv/NaviActionPause.srv"
  "srv/NaviActionPath.srv"
  "srv/NaviActionResume.srv"
  "srv/NaviActionPos.srv"
  "srv/NaviDrivingSubOptionSet.srv"
  "srv/NaviActionStop.srv"
  "srv/NaviLogFileEnable.srv"
  "srv/NaviDrivingMainOptionSet.srv"
  "srv/NaviDrivingElevatorOptionSet.srv"
  "srv/NaviPositionSet.srv"
  "srv/NaviActionBasic.srv"
  "srv/NaviElevHeightReq.srv"
  "srv/NaviMapPositionSet.srv"
  "srv/NaviVersionReq.srv"
  "srv/NaviVirtualObsPosMsg.srv"
  "srv/NaviLogLev.srv"
  "srv/NaviMultiPointInOrder.srv"
  "srv/NaviMultiPointInOrderReq.srv"
  "srv/NaviDrivingSubOptionReq.srv"
  "srv/NaviFacoryModeSet.srv"
  "srv/NaviSensorMaskSet.srv"
  "srv/SlamSrvInit3DPosSet.srv"
  "srv/NaviStatus.srv"
)


rosidl_generate_interfaces(${PROJECT_NAME}
    ${msg_files}
#    ${srv_files}
    DEPENDENCIES std_msgs
    DEPENDENCIES std_srvs
    DEPENDENCIES lgnav_common_msgs 
# slam_msgs
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




























































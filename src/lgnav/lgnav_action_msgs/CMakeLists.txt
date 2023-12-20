cmake_minimum_required(VERSION 3.5)
project(lgnav_action_msgs)

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


set(msg_files
  "msg/ActionID.msg"
  "msg/ActionInfo.msg"
  "msg/ActionRegExtPathParam.msg"
  "msg/ActionReqExtParam.msg"
  "msg/ActionStatus.msg"
  "msg/CurrentPath.msg"
  "msg/LaserFilterParam.msg"
  "msg/LaserSpikeNoiseFilterParam.msg"
  "msg/LaserVeilingFilterParam.msg"
  "msg/LocalMapParam.msg"
  "msg/MotionStatus.msg"
  "msg/NaviMapVersion.msg"
  "msg/ParamMsg.msg"
  "msg/ParamMsgVal.msg"
  "msg/SenstivityLv.msg"
)

set(srv_files
  "srv/ActionLocalMapMask.srv"
  "srv/ActionMaxVelSet.srv"
  "srv/ActionParam.srv"
  "srv/ActionPath.srv"
  "srv/ActionPause.srv"
  "srv/ActionRegExtPathParam.srv"
  "srv/ActionReqExtParam.srv"
  "srv/ActionResume.srv"
  "srv/ActionStatus.srv"
  "srv/ActionStop.srv"
  "srv/CurrentActionParam.srv"
  "srv/CurrentMotionParam.srv"
  "srv/CurrentParamReq.srv"
  "srv/CurrentPathplanParam.srv"
  "srv/LaserFilterParam.srv"
  "srv/MotionParam.srv"
  "srv/ParamMsg.srv"
  "srv/PathplanParam.srv"
)
rosidl_generate_interfaces(${PROJECT_NAME}
    ${msg_files}
    ${srv_files}
    DEPENDENCIES std_msgs
    DEPENDENCIES std_srvs
    DEPENDENCIES lgnav_common_msgs
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

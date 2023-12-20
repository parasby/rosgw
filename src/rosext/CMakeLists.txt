cmake_minimum_required(VERSION 3.5)
project(rosext)

# Default to C99
if(NOT CMAKE_C_STANDARD)
  set(CMAKE_C_STANDARD 99)
endif()

# Default to C++14
if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 14)
endif()

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic -fpermissive)
endif()

set(header
  ${PROJECT_SOURCE_DIR}/include/rosext/create_generic_pubsub.hpp
  ${PROJECT_SOURCE_DIR}/include/rosext/extnode_impl.hpp
  ${PROJECT_SOURCE_DIR}/include/rosext/extnode.hpp
  ${PROJECT_SOURCE_DIR}/include/rosext/generic_publisher.hpp
  ${PROJECT_SOURCE_DIR}/include/rosext/generic_subscription.hpp
  ${PROJECT_SOURCE_DIR}/include/rosext/generic_type_support.hpp
)

# find dependencies
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rclcpp_components REQUIRED)
find_package(rcutils REQUIRED)
find_package(rcpputils REQUIRED)
find_package(rmw REQUIRED)
find_package(rmw_fastrtps_shared_cpp REQUIRED)
find_package(rosidl_typesupport_fastrtps_cpp REQUIRED)
find_package(rmw_dds_common REQUIRED)

add_library(rosext SHARED
src/extnode.cpp
src/generic_subscription.cpp
src/generic_publisher.cpp
src/generic_type_support.cpp
)

target_include_directories(rosext PUBLIC
"$<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>"
"$<BUILD_INTERFACE:${CMAKE_CURRENT_BINARY_DIR}/include>"
"$<INSTALL_INTERFACE:include>")

ament_target_dependencies(${PROJECT_NAME}
  rclcpp 
  rclcpp_components 
  rcutils    
  rmw_fastrtps_shared_cpp 
  rmw_dds_common
  rosidl_typesupport_fastrtps_cpp
  rmw)


# uncomment the following section in order to fill in
# further dependencies manually.
# find_package(<dependency> REQUIRED)

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

install(TARGETS
    ${PROJECT_NAME} EXPORT ${PROJECT_NAME}
    ARCHIVE DESTINATION lib
    LIBRARY DESTINATION lib
    RUNTIME DESTINATION bin
    )

ament_export_include_directories(include)
ament_export_libraries(${PROJECT_NAME})
#ament_export_targets(${PROJECT_NAME}) # use only when do you have /bin/some_exe

ament_export_dependencies(rclcpp)
ament_export_dependencies(rcutils)
ament_export_dependencies(rmw_fastrtps_shared_cpp)
ament_export_dependencies(rmw_dds_common)
ament_export_dependencies(rosidl_typesupport_fastrtps_cpp)
ament_export_dependencies(rmw)
      
ament_package()

install(
  DIRECTORY include/ 
  DESTINATION include
)

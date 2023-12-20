cmake_minimum_required(VERSION 3.5)

project(rosextpy)

# Default to C++17
if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 17)
endif()
# Default to C11
if(NOT CMAKE_C_STANDARD)
  set(CMAKE_C_STANDARD 11)
endif()
if(CMAKE_COMPILER_IS_GNUCC OR CMAKE_C_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra)
endif()


find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rosext REQUIRED)
find_package(python_cmake_module REQUIRED)
find_package(PythonExtra REQUIRED)
find_package(Python3 REQUIRED COMPONENTS Interpreter Development)

# for msg type
# find_package(rosidl_default_generators REQUIRED)

# rosidl_generate_interfaces(${PROJECT_NAME}
# msg/Typeinfo.msg)
# ##



set(_PYTHON_EXECUTABLE "${PYTHON_EXECUTABLE}")

set(PYBIND11_PYTHON_VERSION ${PYTHONVERSION}) 

if(WIN32 AND CMAKE_BUILD_TYPE STREQUAL "Debug")
  # Set the python debug interpreter.
  # pybind11 will setup the build for debug now.
  set(PYTHON_EXECUTABLE "${PYTHON_EXECUTABLE_DEBUG}")
endif()

find_package(pybind11 CONFIG REQUIRED
    PATHS 
    "/usr/local/lib/python3.8/dist-packages/pybind11/share/cmake/pybind11"
    "/usr/local/lib/python3.11/dist-packages/pybind11/share/cmake/pybind11"
    "${HOME}/.local/lib/python3.8/site-packages/pybind11/share/cmake/pybind11"
    "${HOME}/.local/lib/python3.11/site-packages/pybind11/share/cmake/pybind11"
    )


#execute_process(COMMAND ~/.local/bin/pybind11-cofig --cmakedir OUTPUT_VARIABLE PYBIND11_HINTS)
#list(APPEND CMAKE_MODULE_PATH "${HOME}/.local/lib/python3.8/site-packages/pybind11/share/cmake/pybind11")

#find_package(pybind11_vendor REQUIRED)
#find_package(Python COMPONENTS Interpreter Development REQUIRED)


if(WIN32 AND CMAKE_BUILD_TYPE STREQUAL "Debug")
  # pybind11 logic for setting up a debug build when both a debug and release
  # python interpreter are present in the system seems to be pretty much broken.
  # This works around the issue.
  set(PYTHON_LIBRARIES "${PYTHON_DEBUG_LIBRARIES}")
endif()

function(clean_windows_flags target)
  # Hack to avoid pybind11 issue.
  #
  # TODO(ivanpauno):
  # This can be deleted when we update `pybind11_vendor` to a version including
  # https://github.com/pybind/pybind11/pull/2590.
  #
  # They are enabling /LTCG on Windows to reduce binary size,
  # but that doesn't play well with MSVC incremental linking (default for Debug/RelWithDebInfo).
  #
  # See:
  # - https://docs.microsoft.com/en-us/cpp/build/reference/incremental-link-incrementally?view=vs-2019
  # - https://docs.microsoft.com/en-us/cpp/build/reference/ltcg-link-time-code-generation?view=vs-2019

  if(MSVC AND "${CMAKE_BUILD_TYPE}" STREQUAL "RelWithDebInfo")
    get_target_property(target_link_libraries ${target} LINK_LIBRARIES)
    list(REMOVE_ITEM target_link_libraries "$<$<NOT:$<CONFIG:Debug>>:-LTCG>")
    set_target_properties(${target} PROPERTIES LINK_LIBRARIES "${target_link_libraries}")

    get_target_property(target_compile_options ${target} COMPILE_OPTIONS)
    list(REMOVE_ITEM target_compile_options "$<$<NOT:$<CONFIG:Debug>>:/GL>")
    set_target_properties(${target} PROPERTIES COMPILE_OPTIONS "${target_compile_options}")
  endif()
endfunction()

# pybind11_add_module sets a compile definition Py_DEBUG, but the CPython
# pyconfig.h header on windows also sets Py_DEBUG when _DEBUG is set.
# This leadds to a C4005 compiler warning for a duplicate definition of
# Py_DEBUG.
# The pybind11.h header has logic to work around that, but not all of these
# CPython extensions are using pybind11.
# This function strips the Py_DEBUG compile definition.
# It should only be used if pybind11_add_module is used but the module does not
# include pybind11.h.
function(remove_py_debug_definition_on_win32 target)
  if(WIN32 AND CMAKE_BUILD_TYPE STREQUAL "Debug")
  get_target_property(compile_definitions "${target}" COMPILE_DEFINITIONS)
  set(compile_definitions_to_keep "")
  foreach(definition ${compile_definitions})
    if("Py_DEBUG" STREQUAL definition)
      # Skip!
      continue()
    endif()
    list(APPEND compile_definitions_to_keep "${definition}")
  endforeach()
  set_target_properties("${target}" PROPERTIES COMPILE_DEFINITIONS "${compile_definitions_to_keep}")
  endif()
endfunction()

# enables using the Python extensions from the build space for testing
#file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/test_rclpy/__init__.py" "")

ament_python_install_package(${PROJECT_NAME})

# Set the build location and install location for a CPython extension
function(configure_build_install_location _library_name)
  # Install into test_rclpy folder in build space for unit tests to import
  set_target_properties(${_library_name} PROPERTIES
    # Use generator expression to avoid prepending a build type specific directory on Windows
    LIBRARY_OUTPUT_DIRECTORY $<1:${CMAKE_CURRENT_BINARY_DIR}/test_rclpy>
    RUNTIME_OUTPUT_DIRECTORY $<1:${CMAKE_CURRENT_BINARY_DIR}/test_rclpy>)

  # Install library for actual use
  install(TARGETS ${_library_name}
    DESTINATION "${PYTHON_INSTALL_DIR}/${PROJECT_NAME}"
  )
endfunction()

add_library(rosextpy_common SHARED
  src/common.cpp
)

ament_target_dependencies(rosextpy_common 
  pybind11 rclcpp rosext)
  
install(TARGETS rosextpy_common
  ARCHIVE DESTINATION lib
  LIBRARY DESTINATION lib
  RUNTIME DESTINATION bin
)

install(PROGRAMS 
  scripts/run_gateway
  DESTINATION lib/${PROJECT_NAME}
)

install(FILES
  launch/gateway_launch.xml
  DESTINATION share/${PROJECT_NAME}/launch
)

pybind11_add_module(_rosextpy_pybind11 SHARED
  src/rosextpy.cpp
)

target_include_directories(_rosextpy_pybind11 PRIVATE
  src/
)

target_link_libraries(_rosextpy_pybind11  PRIVATE
   pybind11::pybind11
   rclcpp::rclcpp
   rosextpy_common
)

configure_build_install_location(_rosextpy_pybind11)
clean_windows_flags(_rosextpy_pybind11)
ament_export_libraries(_rosextpy_pybind11)

set(PYTHON_EXECUTABLE "${_PYTHON_EXECUTABLE}")

ament_package()

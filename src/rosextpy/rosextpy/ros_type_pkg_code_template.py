#  MIT License
#
#  Copyright (c) 2021, Electronics and Telecommunications Research Institute (ETRI) All Rights Reserved.
#
#  Permission is hereby granted, free of charge, to any person obtaining a copy
#  of this software and associated documentation files (the "Software"), to deal
#  in the Software without restriction, including without limitation the rights
#  to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#  copies of the Software, and to permit persons to whom the Software is
#  furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

# rosextpy.ros2_pkg_code_gen (ros2-ws-gateway)
# Author: ByoungYoul Song(parasby@gmail.com)


ROS2_TYPE_PKG_CMAKE_TEMPLATE = "\
cmake_minimum_required(VERSION 3.5)\n\
project({package_name})\n\
find_package(ament_cmake REQUIRED)\n\
find_package(rosidl_default_generators REQUIRED)\n\n\
rosidl_generate_interfaces(${{PROJECT_NAME}}\n\
{interface_files}\
)\n\
ament_package()\
"

ROS2_TYPE_PKG_PROFILE_TEMPLATE = '\
<?xml version="1.0"?>\n\
<?xml-model href="http://download.ros.org/schema/package_format3.xsd" schematypens="http://www.w3.org/2001/XMLSchema"?>\n\
<package format="3">\n\
<name>{package_name}</name>\n\
<version>{package_version}</version>\n\
<description>{package_description}</description>\n\
<maintainer email="{package_maintainer_email}">{package_maintainer}</maintainer>\n\
<license>{package_license}</license>\n\
<buildtool_depend>ament_cmake</buildtool_depend>\n\
<member_of_group>rosidl_interface_packages</member_of_group>\n\
<export>\n\
<build_type>ament_cmake</build_type>\n\
</export>\n\
</package>\n\
'

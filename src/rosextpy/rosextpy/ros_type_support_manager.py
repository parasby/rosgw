#  MIT License
#
#  Copyright (c) 2021,
#       Electronics and Telecommunications Research Institute (ETRI) All Rights Reserved.
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

# rosextpy.ros_type_support_manager (ros2-ws-gateway)
# Author: parasby@gmail.com
"""ROS IDL typesupport agent
 share type information(msg files) and runtime time reload
"""
import sys
import logging
import os
import subprocess
import difflib
import time
from typing import Tuple, Dict, Union  # List, Dict,
# import traceback
import asyncio

###################
#
#  /request_type_info : request_type = std_msgs/String
#  /type_support_info : typedata = Typeinfo { request_type, dataFile}
#
# must import configuration module before any other sub modules

from rosextpy.ros_type_pkg_code_template import (
    ROS2_TYPE_PKG_PROFILE_TEMPLATE, ROS2_TYPE_PKG_CMAKE_TEMPLATE)
########################
##
# type_support_agent_test
##
##
# In ROS Protocol:
# * type 정보 공유를 위해
# "/type_support" 토픽으로 TypeInfo.msg의 데이터가 전송됨
# for ROS:  TypeInfo.msg = [ string packageName , uint8[] data ]
# * type 정보 요청을 위해
# "/type_support_request"  Service가 요청됨 parameter는 "packagename.typeName"
# 요청의 결과는 msg 파일임.
# In REST Api:
# * type 정보 전송을 위해
# "add_type_info"  , parameter는 {
#       'typeName' : $packageName.type, 'msg': base64.encode($msg_file_contents)}
# * type 정보 요청은
# "req_type_info"  , parameter는 typename
# -> result: { 'msg' : base64 encoded binary}
##
#########################

mlogger = logging.getLogger('ros_type_support_manager')
# logging.basicConfig(
#     stream=sys.stdout,
#     format='%(levelname)-6s [%(filename)s:%(lineno)d] %(message)s',
#     level=logging.DEBUG)
# mlogger.setLevel(logging.DEBUG)

#
#  Receive ROS type_support message and pub something
#


class RosTypeSupportManager():
    """RosTypeSupportManager
    """

    def __init__(self, loop=None, option=None, **kwargs):
        _ = kwargs  # reserved
        self.loop = loop if loop is not None else asyncio.get_event_loop()
        if option is not None:
            self.cpath = os.path.abspath(option.cpath)
        else:
            self.cpath = os.path.abspath(os.getcwd())
        self.pkg_path = ''.join([self.cpath, '/pkgs'])
        self.builds_path = ''.join([self.cpath, '/builds'])
        self.install_path = ''.join([self.cpath, '/install'])
        # repo for testing building
        self.sand_path = ''.join([self.cpath, '/sands'])
        os.makedirs(self.pkg_path, exist_ok=True)
        os.makedirs(self.sand_path, exist_ok=True)
        os.makedirs(self.builds_path, exist_ok=True)
        os.makedirs(self.install_path, exist_ok=True)

    def build_type_package(self, pkgname: str):
        """build_type_package

        Args:
            pkgname (str): type package name
        """
        # get current working path
        current_dir = os.getcwd()

        # cd build path
        os.chdir(self.builds_path)

        # build package
        _pid = subprocess.Popen(
            ['colcon', 'build',
             '--packages-select', pkgname,
             '--merge-install',
             '--base-paths', self.pkg_path,
             '--build-base', self.builds_path,
             '--install-base', self.install_path
             ])

        # restore working path
        os.chdir(current_dir)

    def generate_type_cmake(self, pkg_name: str):
        """generate_type_cmake

        Args:
            pkg_name (str):  type package name
        """
        cmake_path = ''.join(
            [self.pkg_path, '/', pkg_name, '/', 'CMakeLists.txt'])
        msg_path = ''.join([self.pkg_path, '/', pkg_name, '/msg'])
        srv_path = ''.join([self.pkg_path, '/', pkg_name, '/srv'])

        cmake_contents = {}
        cmake_contents['package_name'] = pkg_name

        type_files = []

        if os.path.exists(msg_path):
            file_list = os.listdir(msg_path)
            type_files.extend([''.join(['msg/', file, "\n"])
                              for file in file_list if file.endswith('.msg')])

        if os.path.exists(srv_path):
            file_list = os.listdir(srv_path)
            type_files.extend([''.join(['srv/', file, "\n"])
                              for file in file_list if file.endswith('.srv')])

        cmake_contents['interface_files'] = ''.join(type_files)

        # mlogger.debug("type_file is %s",type_files)
        # mlogger.debug("contents is %s",cmake_contents)

        with open(cmake_path, 'w', encoding="utf-8") as file_data:
            file_data.write(
                ROS2_TYPE_PKG_CMAKE_TEMPLATE.format(**cmake_contents))

    def generate_type_profile(self, pkg_name: str, options: Union[Dict, None] = None):
        """generate_type_profile

        Args:
            pkg_name (str): type package name
            options (Union[Dict,None], optional): option dict. Defaults to None.
        """
        profile_path = ''.join(
            [self.pkg_path, '/', pkg_name, '/', 'package.xml'])
        profile_contents = {}
        profile_contents['package_name'] = pkg_name
        profile_contents['package_version'] = '0.0.0'
        profile_contents['package_description'] = 'TODO: Package description'
        profile_contents['package_maintainer_email'] = 'user@todo.todo'
        profile_contents['package_maintainer'] = 'user'
        profile_contents['package_license'] = 'TODO: License declaration'

        if options:
            profile_contents['package_version'] = options.get(
                'VERSION', '0.0.0')
            profile_contents['package_description'] = options.get(
                'PACKAGE_DESCRIPTION', 'TODO: Package description')
            profile_contents['package_maintainer_email'] = options.get(
                'PACKAGE_MAINTAINER_EMAIL', 'user@todo.todo')
            profile_contents['package_maintainer'] = options.get(
                'PACKAGE_MAINTAINER', 'user')
            profile_contents['package_license'] = options.get(
                'LICENSE', 'TODO: License declaration')

        with open(profile_path, 'w', encoding="utf-8") as file_data:
            file_data.write(
                ROS2_TYPE_PKG_PROFILE_TEMPLATE.format(**profile_contents))

    # package, [msg or srv], filename without extension
    def get_type_path(self, typestr: str) -> Tuple[str, str, str]:
        """get foler and filename tuple from typestr
            return value (package path, [msg or srv], filename without extension)
        """
        (pkg_name, file_type, file_name) = typestr.rsplit('/', 2)

        if file_type not in ["msg", "srv"]:
            raise ValueError(f"unknown type {file_type}")
        file_name = ''.join([file_name.capitalize(), '.', file_type])
        return (pkg_name, file_type, file_name.capitalize())

    def store_type_info(self, type_str: str, type_data: bytes):
        """store_type_info

        Args:
            type_str (str): type package name
            type_data (bytes): type package data

        Raises:
            ex: FileNotFoundError 
        """
        # get file save path and filename
        pkg_name, file_type, file_name = self.get_type_path(type_str)

        pkg_path = ''.join([self.pkg_path, '/', pkg_name])

        # file_type is 'msg' or 'srv'
        type_path = ''.join([pkg_path, '/', file_type])

        os.makedirs(type_path, exist_ok=True)

        file_path = ''.join([pkg_path, '/', file_type, '/', file_name])

        # compare old and new
        try:
            with open(file_path, 'rb', encoding="utf-8") as file_data:
                # found target file
                old_infos = file_data.read()
                gen = difflib.diff_bytes(difflib.unified_diff, [old_infos], [
                                         type_data])  # return generator
                if len(list(gen)) == 0:
                    mlogger.debug("file is identical")
                    return
        except FileNotFoundError as ex:
            raise ex

        # save backup file
        backup_path = ''.join([pkg_path, '/backup'])
        os.makedirs(backup_path, exist_ok=True)

        save_backup_path = ''.join(
            [backup_path, '/', file_name, '.', str(time.strftime("%Y%m%d%H%M%S")), ".back"])
        if isinstance(type_data, bytes):
            with open(save_backup_path, 'wb', encoding="utf-8") as file_data:
                file_data.write(type_data)
        else:
            with open(save_backup_path, 'w', encoding="utf-8") as file_data:
                file_data.write(type_data)

        # save target file
        if isinstance(type_data, bytes):
            with open(file_path, 'wb', encoding="utf-8") as file_data:
                file_data.write(type_data)
        else:
            with open(file_path, 'w', encoding="utf-8") as file_data:
                file_data.write(type_data)

        # update package cmake and profile
        self.generate_type_cmake(pkg_name)
        self.generate_type_profile(pkg_name)

        # build cmakes
        self.build_type_package(pkg_name)

    async def close(self):
        """close
        """
        mlogger.debug("close called")

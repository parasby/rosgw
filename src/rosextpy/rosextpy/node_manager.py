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

# rosextpy.ros_node_manager (ros-ws-gateway)
# Author: (ByoungYoul Song)parasby@gmail.com
#

"""ros2 subscription and publish management
"""
#
# ros version == foxy (rmw_fast_rtps of galactic version has some bugs )

import os
from typing import Callable, Union, Dict, Any, Awaitable, Tuple  # , Coroutine
import traceback
import functools
import logging
import uuid
from threading import Thread
import threading
import asyncio
import rclpy
import rclpy.task
import rclpy.action
import rclpy.executors
from unique_identifier_msgs.msg import UUID as ROSUUID
from rclpy.action import ActionServer, ActionClient
from rclpy.qos import qos_profile_system_default
from datetime import datetime
from rosextpy.ext_type_support import (SerializedTypeLoader, TypeLoader,
                                       SrvTypeLoader, ActionTypeLoader,
                                       ros_from_text_dict, get_hash_code)

if os.environ['ROS_VERSION'] != '2':
    raise RuntimeError("ROS VERSION 2.0 required")

mlogger = logging.getLogger('node_manager')
# mlogger.setLevel(logging.DEBUG)

ROS_SRV_CLIENT_TIMEOUT = 3.0
ROS_ACTION_CLIENT_TIMEOUT = 3.0

# pylint: disable=broad-exception-caught


class NodeManagerException(Exception):
    """ NodeManagerException """

    def __init__(self, msg: str):
        super().__init__("nodemanager fail :"+msg)


class ROSServiceFailException(Exception):
    """ ROSServiceFailException """

    def __init__(self, msg: str):
        super().__init__("ros service fail :"+msg)


class ExecutorWrapper:
    """ExecutorWrapper"""

    def __init__(self, ctx):
        self.ctx = ctx
        self.executor: rclpy.executors.Executor = \
            rclpy.executors.MultiThreadedExecutor(context=self.ctx)

    def create_node(self, node_name: str):
        """create_node"""
        _tss = round(datetime.now().timestamp()*1000)
        return rclpy.create_node(f'{node_name}_{_tss}', context=self.ctx)

    def add_node(self, node):
        """add_node"""
        self.executor.add_node(node)

    def spin_once(self, timeout_sec):
        """spin_once"""
        self.executor.spin_once(timeout_sec=timeout_sec)

    def get_nodes(self):
        """get_nodes"""
        return self.executor.get_nodes()

    def remove_node(self, node):
        """remove_node"""
        self.executor.remove_node(node)

    def shutdown(self):
        """shutdown"""
        self.executor.shutdown()


class ActionClientManager:
    """ ActionClientManager """
    # pylint: disable=too-many-instance-attributes

    def __init__(
            self, executor: ExecutorWrapper,
            act_type: str, act_name: str, israw: bool = False):
        self.executor: ExecutorWrapper = executor
        self.node = self.executor.create_node(
            node_name='acc_'+act_name.replace("/", "_"))  # type: ignore
        self.act_type: str = act_type
        self.act_name: str = act_name
        self.israw: bool = israw
        self.bridge_id = None
        self.act_cls = ActionTypeLoader(self.act_type)
        try:
            self.handle = ActionClient(self.node, self.act_cls, self.act_name)
        except Exception:
            mlogger.error(traceback.format_exc())

        self.executor.add_node(self.node)

        mlogger.debug("node create_client completed")
        self.bridges = {}

    def encode_json_to_goal(self, json_data):
        """encode_json_to_goal"""
        return ros_from_text_dict(json_data, self.act_cls.Goal())

    def encode_json_to_result(self, json_data):
        """encode_json_to_result"""
        return ros_from_text_dict(json_data, self.act_cls.Result())

    def encode_json_to_feeback(self, json_data):
        """encode_json_to_feeback"""
        return ros_from_text_dict(json_data, self.act_cls.Feedback())

    def __feedback_callback(self,
                            feedback_msg: Any,
                            feedback_callback: Callable[[str, Any, uuid.UUID], None]):
        mlogger.debug("__feedback_callback ")
        feedback_callback(self.act_name, feedback_msg.feedback,
                          uuid.UUID(bytes=feedback_msg.goal_id.uuid.tobytes()))

    def __get_result_callback(self,
                              future: Any,
                              action_result_callback: Callable[[str, Any, uuid.UUID], None],
                              goal_id):
        mlogger.debug("__get_result_callback")
        action_result_callback(self.act_name, future.result().result,
                               uuid.UUID(bytes=goal_id.uuid.tobytes()))

    # # pylint: disable=too-many-arguments
    def __call_goal_async(
            self,
            goal_msg, goal_id: Union[uuid.UUID, None],
            feedback_callback: Union[Callable[[str, Any, uuid.UUID], None], None],
            action_result_callback: Union[Callable[[str, Any, uuid.UUID], None], None],
            goal_accept_callback: Union[Callable[[
                str, rclpy.action.client.ClientGoalHandle], None], None],
            goal_reject_callback: Union[Callable[[
                str, rclpy.action.client.ClientGoalHandle], None], None]
    ) -> Union[rclpy.task.Future, None]:
        mlogger.debug("__call_goal_async ")
        if self.handle is None:
            return None

        def goal_response_callback(future):
            goal_handle = future.result()
            if goal_handle.accepted:
                if goal_accept_callback is not None:
                    goal_accept_callback(self.act_name, goal_handle)

                if action_result_callback is not None:
                    _get_result_future = goal_handle.get_result_async()
                    _get_result_future.add_done_callback(
                        functools.partial(
                            self.__get_result_callback,
                            action_result_callback=action_result_callback,
                            goal_id=goal_handle.goal_id))
            else:
                if goal_reject_callback is not None:
                    goal_reject_callback(self.act_name, goal_handle)

        _goal_id = None
        if goal_id is not None:
            _goal_id = ROSUUID(uuid=list(goal_id.bytes))
        _send_goal_future = None

        try:
            if feedback_callback is not None:
                _send_goal_future = self.handle.send_goal_async(
                    goal=goal_msg,
                    feedback_callback=functools.partial(
                        self.__feedback_callback,
                        feedback_callback=feedback_callback),
                    goal_uuid=_goal_id)
            else:
                _send_goal_future = self.handle.send_goal_async(
                    goal=goal_msg, goal_uuid=_goal_id)

            if _send_goal_future is not None:
                _send_goal_future.add_done_callback(goal_response_callback)

        except Exception:
            mlogger.debug(traceback.format_exc())
            return None

        return _send_goal_future

    def send_goal_async(self,
                        request_json, goal_id: Union[uuid.UUID, None] = None,
                        feedback_callback: Union[Callable[[
                            str, Any, Any], None], None] = None,
                        action_result_callback: Union[Callable[[
                            str, Any, Any], None], None] = None,
                        goal_accept_callback: Union[Callable[[
                            str, rclpy.action.client.ClientGoalHandle], None], None] = None,
                        goal_reject_callback: Union[Callable[[
                            str, rclpy.action.client.ClientGoalHandle], None], None] = None
                        ) -> Union[rclpy.task.Future, None]:
        """send_goal_async"""
        mlogger.debug("send_goal_async %s", request_json)
        if self.handle is None:
            return None
        the_future = None
        self.handle.wait_for_server(timeout_sec=ROS_ACTION_CLIENT_TIMEOUT)
        # sometimes, service can be unavailable
        if not self.handle.server_is_ready():
            mlogger.debug("no action service available...")
            return None

        if isinstance(request_json, bytes):
            the_future = self.__call_goal_async(
                request_json, goal_id,
                feedback_callback=feedback_callback,
                action_result_callback=action_result_callback,
                goal_accept_callback=goal_accept_callback,
                goal_reject_callback=goal_reject_callback)
        else:
            if 'type' in request_json:
                if request_json['type'] == 'Buffer':
                    the_future = self.__call_goal_async(
                        bytes(request_json['data']), goal_id,
                        feedback_callback=feedback_callback,
                        action_result_callback=action_result_callback,
                        goal_accept_callback=goal_accept_callback,
                        goal_reject_callback=goal_reject_callback)
                else:
                    the_future = self.__call_goal_async(
                        self.encode_json_to_goal(request_json), goal_id,
                        feedback_callback=feedback_callback,
                        action_result_callback=action_result_callback,
                        goal_accept_callback=goal_accept_callback,
                        goal_reject_callback=goal_reject_callback)
            else:
                # cmdData['msg'] will be json or {"type":"Buffer","data"}"
                the_future = self.__call_goal_async(
                    self.encode_json_to_goal(request_json), goal_id,
                    feedback_callback=feedback_callback,
                    action_result_callback=action_result_callback,
                    goal_accept_callback=goal_accept_callback,
                    goal_reject_callback=goal_reject_callback)
        return the_future

    def add_action_client(self, bridge_id: str):
        """add_action_client"""
        self.bridge_id = bridge_id

    def remove_action_client(self, bridge_id: str):
        """remove_action_client"""
        _ = bridge_id
        self.bridge_id = None

    def destroy(self):
        """destroy"""
        if self.handle is not None:
            self.handle.destroy()
        self.handle = None
        if self.node is not None:
            self.executor.remove_node(self.node)
            self.node.destroy_node()
        self.node = None


class ActionServerManager:
    """ActionServerManager"""
    # pylint: disable=too-many-instance-attributes

    def __init__(
            self, executor: ExecutorWrapper,
            act_type: str, act_name: str, israw: bool = False):
        self.executor: ExecutorWrapper = executor
        self.node = self.executor.create_node(
            'acs_'+act_name.replace("/", "_"))  # type: ignore
        self.act_type: str = act_type
        self.act_name: str = act_name
        self.israw: bool = israw
        self.act_cls = ActionTypeLoader(self.act_type)
        self.exec_callback: Union[Callable[
            [str, str, rclpy.action.server.ServerGoalHandle], Any], None] = None
        self.goal_callback:  Union[Callable[[
            str, str, Any], rclpy.action.server.GoalResponse], None] = None
        self.cancel_callback: Union[Callable[[
            str, str, Any], rclpy.action.server.CancelResponse], None] = None
        self.handle_accepted_callback: Union[Callable[[
            str, str, rclpy.action.server.ServerGoalHandle], None], None] = None
        self.bridge_id = None

        self.handle = ActionServer(
            self.node, self.act_cls, self.act_name,
            execute_callback=self._inter_exec_callback,
            goal_callback=self._inter_goal_callback,  # type: ignore
            cancel_callback=self._inter_cancel_callback,  # type: ignore
            handle_accepted_callback=self._inter_handle_accepted_callback  # type: ignore
        )

        self.executor.add_node(self.node)

        mlogger.debug("node create_action_server completed")
        self.callback = None

    async def _inter_exec_callback(self, goal_handle):
        mlogger.debug('action call received!!! %s', self.act_name)
        if self.exec_callback is not None:
            _ret = await self.exec_callback(self.act_name, self.act_type, goal_handle)
            if _ret is not None:
                return _ret

        mlogger.debug('action call aborted!!! %s', self.act_name)
        goal_handle.abort()
        return self.get_result_class()()

    async def _inter_goal_callback(self, goal_request):
        mlogger.debug('action goal callback ')
        if self.goal_callback is not None:
            return self.goal_callback(self.act_name, self.act_type, goal_request)
        return rclpy.action.server.default_goal_callback(goal_request)

    async def _inter_cancel_callback(self, cancel_request):
        mlogger.debug('action cancel callback ')
        if self.cancel_callback is not None:
            return self.cancel_callback(self.act_name, self.act_type, cancel_request)

        return rclpy.action.server.default_cancel_callback(cancel_request)

    async def _inter_handle_accepted_callback(self, goal_handle):
        mlogger.debug('action handle_accepted callback ')
        if self.handle_accepted_callback is not None:
            self.handle_accepted_callback(
                self.act_name, self.act_type, goal_handle)

        rclpy.action.server.default_handle_accepted_callback(goal_handle)

    def add_action_server(self,
                          bridge_id: str,
                          callback: Callable[
                              [str, str, rclpy.action.server.ServerGoalHandle], Any]):
        """add_action_server"""
        self.bridge_id = bridge_id
        self.exec_callback = callback

    def get_result_class(self):
        """get_result_class"""
        return self.act_cls.Result

    def get_feedback_class(self):
        """get_feedback_class"""
        return self.act_cls.Feedback

    def get_waiter(self):
        """get_waiter"""
        fut = rclpy.task.Future()
        return fut

    def remove_action_server(self, bridge_id: str):
        """remove_action_server"""
        _ = bridge_id
        self.bridge_id = None
        self.exec_callback = None  # type: ignore

    def destroy(self):
        """destroy ActionServerManager"""
        mlogger.debug("destroy ActionServerManager")
        self.exec_callback = None  # type: ignore
        if self.handle is not None:
            self.handle.destroy()
        self.handle = None
        if self.node is not None:
            self.executor.remove_node(self.node)
            self.node.destroy_node()
        self.node = None


class SrvClientManager:
    """SrvClientManager"""
    # pylint: disable=too-many-instance-attributes

    def __init__(self,
                 executor: ExecutorWrapper,
                 srv_type: str, srv_name: str, israw: bool = False):
        self.executor: ExecutorWrapper = executor
        self.node = self.executor.create_node(
            'svc_'+srv_name.replace("/", "_"))  # type: ignore
        self.srv_type: str = srv_type
        self.srv_name: str = srv_name
        self.israw: bool = israw
        self.bridge_id = None
        self.srv_cls = SrvTypeLoader(self.srv_type)
        self.on_call = False

        try:
            self.handle = self.node.create_client(
                self.srv_cls,
                self.srv_name, qos_profile=qos_profile_system_default)
        except Exception:
            mlogger.error(traceback.format_exc())

        self.executor.add_node(self.node)

        mlogger.debug("node create_client completed")
        self.bridges = {}

    def _when_finished(
            self,
            fut: rclpy.task.Future,
            callback: Union[Callable[[str, Any], None], None]):
        mlogger.debug("_when_finished")
        self.on_call = False
        if callback is not None:
            response = fut.result()
            callback(self.srv_name, response)
        # callback_info['callback'](
        #     self.srv_name, call_id, response, callback_info['compression'])

    def encode_json_to_request(self, json_data):
        """remove_publish"""
        return ros_from_text_dict(json_data, self.srv_cls.Request())

    def encode_json_to_respone(self, json_data):
        """remove_publish"""
        return ros_from_text_dict(json_data, self.srv_cls.Response())

    # it will be called by gateway
    # response_callback--> receive ROS response and send JSON message response
    def call_service_async(
            self,
            request_json: Any,
            callback: Union[Callable[[str, Any], None], None] = None
    ) -> Union[rclpy.task.Future, None]:
        """publish"""
        mlogger.debug("service_call %s", request_json)
        if self.handle is None:
            return None

        if self.on_call is True:
            return None

        self.handle.wait_for_service(
            timeout_sec=ROS_SRV_CLIENT_TIMEOUT)  # sometimes, service can be unavailable
        if not self.handle.service_is_ready():
            mlogger.debug("no service available...")
            return None

        the_future = None
        self.on_call = True

        if isinstance(request_json, bytes):
            the_future = self.handle.call_async(request_json)
        else:
            if 'type' in request_json:
                if request_json['type'] == 'Buffer':
                    the_future = self.handle.call_async(
                        bytes(request_json['data']))
                else:
                    the_future = self.handle.call_async(
                        self.encode_json_to_request(request_json))
            else:
                # cmdData['msg'] will be json or {"type":"Buffer","data"}"
                the_future = self.handle.call_async(
                    self.encode_json_to_request(request_json))
        the_future.add_done_callback(
            functools.partial(self._when_finished, callback=callback))

        return the_future

    def add_srv_client(self, bridge_id: str):
        """add_srv_client"""
        self.bridge_id = bridge_id

    def remove_srv_client(self, bridge_id: str):
        """remove_srv_client"""
        _ = bridge_id
        self.bridge_id = None

    def destroy(self):
        """ destroy """
        if self.node is not None and self.handle is not None:
            self.node.destroy_client(self.handle)
        self.handle = None
        if self.node is not None:
            self.executor.remove_node(self.node)
            self.node.destroy_node()
        self.node = None


class SrvServiceManager:
    """ SrvServiceManager """
    # pylint: disable=too-many-instance-attributes

    def __init__(self,
                 executor: ExecutorWrapper,
                 srv_type: str, srv_name: str, israw: bool = False):
        self.executor: ExecutorWrapper = executor
        self.node = self.executor.create_node(
            'svs_'+srv_name.replace("/", "_"))  # type: ignore
        self.srv_type: str = srv_type
        self.srv_name: str = srv_name
        self.israw: bool = israw
        self.srv_cls = SrvTypeLoader(self.srv_type)
        self.bridge_id = None
        self.callback: Union[Callable[[str, str, Any, Any], Any], None] = None

        try:
            self.handle = self.node.create_service(
                self.srv_cls, self.srv_name,
                self._inter_callback, qos_profile=qos_profile_system_default)
        except Exception:
            mlogger.error(traceback.format_exc())

        self.executor.add_node(self.node)

        mlogger.debug("node create_client completed")

    # The _inter_callback receives a request from local ROS peers and it should return a response.

    async def _inter_callback(self, request, response):
        mlogger.debug('service call received %s', type(request))
        if self.callback is not None:
            return await self.callback(self.srv_name, self.srv_type, request, response)
        return response

    def get_response_class(self):
        """ get_response_class"""
        return self.srv_cls.Response

    def get_waiter(self):
        """ get_waiter"""
        fut = rclpy.task.Future()
        return fut

    def add_srv_service(self, bridge_id: str, callback: Callable[[str, str, Any, Any], Any]):
        """add_srv_service"""
        self.bridge_id = bridge_id
        self.callback = callback

    def remove_srv_service(self, bridge_id: str):
        """remove_srv_service"""
        _ = bridge_id
        self.bridge_id = None
        self.callback = None

    def destroy(self):
        """destroy"""
        mlogger.debug('ros service %s destroyed', self.srv_name)
        self.callback = None
        if self.node is not None and self.handle is not None:
            self.node.destroy_service(self.handle)
        self.handle = None
        if self.node is not None:
            self.executor.remove_node(self.node)
            self.node.destroy_node()
        self.node = None


class SubscriptionManager:
    """SubscriptionManager"""
    # pylint: disable=too-many-instance-attributes

    # pylint: disable=too-many-arguments
    def __init__(self, executor: ExecutorWrapper,
                 topic_type: str, topic_name: str,
                 queue_length: int = 0, israw: bool = False):
        self.executor: ExecutorWrapper = executor
        self.node = self.executor.create_node(
            'sub_'+topic_name.replace("/", "_"))  # type: ignore
        self.topic_type: str = topic_type
        self.topic_name: str = topic_name
        self.queue_length: int = queue_length
        self.israw: bool = israw

        if israw:
            self.type_cls = SerializedTypeLoader(topic_type)
        else:
            self.type_cls = TypeLoader(topic_type)

        try:
            self.handle = self.node.create_subscription(
                self.type_cls,
                topic_name, self._inter_callback,
                qos_profile=qos_profile_system_default, raw=self.israw)
        except Exception:
            mlogger.error(traceback.format_exc())

        self.executor.add_node(self.node)

        self.callbacks: Dict[str, Tuple[Callable[[str, Any], None], Any]] = {}
        mlogger.debug("subscription to %s", self.topic_name)

    def _inter_callback(self, message):
        # mlogger.debug('mesage received!!! %s', type(message))
        for _callback in list(self.callbacks.values()):
            if asyncio.iscoroutinefunction(_callback[0]):
                asyncio.run_coroutine_threadsafe(
                    _callback[0](self.topic_name, message), loop=_callback[1])
            else:
                _callback[0](self.topic_name, message)  # type: ignore
        # for callback_info in list(self.callbacks.values()):
        #     callback_info['callback'](
        #         self.topic_name, message, callback_info['compression'])

    def add_subscription(self, bridge_id: str, callback: Callable[[str, Any], None]):
        """add_subscription"""
        if asyncio.iscoroutinefunction(callback):
            self.callbacks[bridge_id] = (               # type: ignore
                callback, asyncio.get_running_loop())
        else:
            self.callbacks[bridge_id] = (callback, None)

    def remove_subscription(self, bridge_id: str):
        """remove_subscription"""
        self.callbacks.pop(bridge_id, None)

    def destroy(self):
        """destroy"""
        self.callbacks = {}
        if self.node is not None and self.handle is not None:
            self.node.destroy_subscription(self.handle)
        self.handle = None
        if self.node is not None:
            self.executor.remove_node(self.node)
            self.node.destroy_node()
        self.node = None

    def destroy_when_empty(self):
        """destroy_when_empty """
        if len(self.callbacks) == 0:
            self.destroy()
            return None
        return self


class PublishManager:
    """PublishManager"""
    # pylint: disable=too-many-instance-attributes

    # pylint: disable=too-many-arguments
    def __init__(self, executor: ExecutorWrapper, topic_type: str,
                 topic_name: str, queue_length: int = 10, israw: bool = False):
        mlogger.debug("create PublishManager")
        self.executor: ExecutorWrapper = executor
        self.node = self.executor.create_node(
            'pub_'+topic_name.replace("/", "_"))  # type: ignore
        self.topic_type: str = topic_type
        self.topic_name: str = topic_name
        self.queue_length: int = queue_length
        self.israw: bool = israw

        if israw:
            self.type_cls = SerializedTypeLoader(topic_type)
        else:
            self.type_cls = TypeLoader(topic_type)

        self.handle = self.node.create_publisher(
            self.type_cls,
            topic_name, qos_profile=qos_profile_system_default)

        self.executor.add_node(self.node)

        mlogger.debug("node create_publisher completed")
        self.bridges = {}

    def change_raw(self, state):
        """change raw mode"""
        if state != self.israw:
            if state is True:
                self.israw = True
                self.type_cls = SerializedTypeLoader(self.topic_type)
            else:
                self.israw = False
                self.type_cls = TypeLoader(self.topic_type)

    def get_class_obj(self):
        """ get_class_obj"""
        return self.type_cls()

    def get_class_type(self):
        """ get_class_type"""
        return self.type_cls

    def add_publish(self, bridge_id: str):
        """add_publish"""
        self.bridges[bridge_id] = 1

    def remove_publish(self, bridge_id: str):
        """remove_publish"""
        self.bridges.pop(bridge_id, None)

    def publish(self, ros_mesg):
        """publish """
        mlogger.debug("publish called")
        if self.handle is None:
            mlogger.debug("no publisher handle error")
            return
        #print("pub mesg is ", ros_mesg)
        self.handle.publish(ros_mesg)

    def destroy(self):
        """destroy"""
        self.bridges = {}
        if self.node is not None and self.handle is not None:
            self.node.destroy_publisher(self.handle)
        self.handle = None
        if self.node is not None:
            self.executor.remove_node(self.node)
            self.node.destroy_node()
        self.node = None

    def destroy_when_empty(self):
        """destroy_when_empty """
        if len(self.bridges) == 0:
            self.destroy()
            return None
        return self

# manage all subscription and publisher


class NodeManager(Thread):
    """NodeManager"""
    # pylint: disable=too-many-instance-attributes, too-many-public-methods

    def __init__(self, options=None):
        super().__init__(daemon=True)
        self.ctx = rclpy.context.Context()
        rclpy.init(args=options, context=self.ctx)
        # rclpy.create_node(f'ros_nod_mgr_{os.getpid()}', context=self.ctx)  # type: ignore
        self.node = rclpy.create_node(
            f'ros_nod_mgr_{os.getpid()}', context=self.ctx)  # type: ignore
        # self.executor: rclpy.executors.Executor = rclpy.executors.MultiThreadedExecutor()
        # self.executor: rclpy.executors.Executor = rclpy.executors.SingleThreadedExecutor(context=self.ctx)
        self.executor: ExecutorWrapper = ExecutorWrapper(self.ctx)
        self.publisher: Dict[str, PublishManager] = {}
        self.subscriptions: Dict[str, SubscriptionManager] = {}
        self.srv_services: Dict[str, SrvServiceManager] = {}
        self.srv_clients: Dict[str, SrvClientManager] = {}
        self.act_servers: Dict[str, ActionServerManager] = {}
        self.act_clients: Dict[str, ActionClientManager] = {}
        self.srv_name_and_types: Dict[str, str] = {}
        self.act_name_and_types: Dict[str, str] = {}
        self.topic_name_and_types: Dict[str, str] = {}
        self.stopped = False
        self.nm_dict_lock = threading.RLock()  # lock for create somthing
        mlogger.debug("ros node manager created")

    def run(self):
        mlogger.debug("ros node manager started")
        try:
            while self.ctx.ok():  # rclpy.ok():
                if self.stopped is True:
                    break
                try:
                    self.executor.spin_once(timeout_sec=0.001)
                except ROSServiceFailException as ex:
                    # ROS executer raises an exception.
                    mlogger.error('service call gets error for [%s]', ex)
                except Exception as oex:
                    mlogger.error('other exception in loop: [%s]', oex)
                    #raise
        except Exception:
            mlogger.error(traceback.format_exc())
        finally:
            mlogger.debug("ros node manager stopped")
            self.executor.shutdown()
            if self.node:
                self.node.destroy_node()
                self.node = None
            rclpy.shutdown(context=self.ctx)

    def stop(self):
        """NodeManager stop"""
        mlogger.debug("ros node manager stopping")
        self.stopped = True
        self.executor.shutdown()
        # executor.shutdown()
        # if self.node:
        #     self.node.destroy_node()
        #     self.node = None
        #     rclpy.shutdown()

    def get_now(self):
        """get_now"""
        if self.node is not None:
            return self.node.get_clock().now()
        raise NodeManagerException("main node cannot be null")

    def get_node(self):
        """get_node"""
        return self.node

    def get_topic_list(self):
        """get topic list"""
        if self.node is not None:
            return self.node.get_topic_names_and_types()
        raise NodeManagerException("main node cannot be null")

    def remove_with_gateway(self, bridge_id: str):
        """remove_bridges"""
        self.destroy_subscription_by_bridge_id(bridge_id)
        self.destroy_publisher_by_bridge_id(bridge_id)

    def create_action_server(
            self,
            act_type: str,
            act_name: str,
            bridge_id: str,
            callback: Callable[[
                str, str, rclpy.action.server.ServerGoalHandle], Any]) -> ActionServerManager:
        # callback: Callable) -> ActionServerManager:
        """create_action_server

        Args:
            act_type (str): target action type
            act_name (str): target action name
            bridge_id (str): calling bridge id
            callback (Callable): action callback function

        Returns:
            ActionServerManager: return action server manager instance
        """
        mlogger.debug("create_action_server %s :%s :%s",
                      act_type, act_name, bridge_id)
        act_mgr = self.act_servers.get(act_name)
        if not act_mgr:
            try:
                if act_type is None:
                    raise NodeManagerException("action type cannot be none")
                act_mgr = ActionServerManager(
                    self.executor, act_type, act_name)
                self.act_servers[act_name] = act_mgr
            except Exception:
                mlogger.debug(traceback.format_exc())
                raise
        act_mgr.add_action_server(bridge_id, callback)
        return act_mgr

    def create_action_client(
            self, act_type: Union[str, None],
            act_name: str, bridge_id: str) -> ActionClientManager:
        """create_action_client

        Args:
            act_type (str): target action type
            act_name (str): target action name
            bridge_id (str): calling bridge id

        Raises:
            NodeManagerException: raised if cannot make action client

        Returns:
            ActionClientManager:  return action client instance
        """
        mlogger.debug("create_action_client %s :%s :%s",
                      act_type, act_name, bridge_id)
        cli_mgr = self.act_clients.get(act_name, None)
        if cli_mgr is None:
            try:
                act_type = self.get_action_type(act_name)
                if act_type is None:
                    raise NodeManagerException("unknown action type")
                cli_mgr = ActionClientManager(
                    self.executor, act_type, act_name)
                self.act_clients[act_name] = cli_mgr
            except Exception:
                mlogger.debug(traceback.format_exc())
                raise
        else:
            if act_type != cli_mgr.act_type:
                # pylint: disable=consider-using-f-string
                raise NodeManagerException(
                    "The action {act} already exists with different action type {type}".format(
                        act=act_name, type=cli_mgr.act_type))

        cli_mgr.add_action_client(bridge_id)
        return cli_mgr

    def create_srv_service(
            self,
            srv_type: str,
            srv_name: str,
            bridge_id: str,
            callback: Callable[[str, str, Any, Any], Awaitable]) -> SrvServiceManager:
        # bridge_id: str, callback: Callable) -> SrvServiceManager:
        """create_srv_service

        Args:
            srv_type (str): target service type
            srv_name (str): target service name
            bridge_id (str): calling bridge id
            callback (Callable): service callback function

        Returns:
            SrvServiceManager: return service server manager instance
        """
        mlogger.debug("create_srv_service %s :%s :%s",
                      srv_type, srv_name, bridge_id)
        srv_mgr = self.srv_services.get(srv_name, None)
        if srv_mgr is None:
            try:
                if srv_type is None:
                    raise NodeManagerException("service type cannot be None")
                srv_mgr = SrvServiceManager(self.executor, srv_type, srv_name)
                self.srv_services[srv_name] = srv_mgr  # service name is unique
            except Exception:
                mlogger.debug(traceback.format_exc())
                raise
        srv_mgr.add_srv_service(bridge_id, callback)
        return srv_mgr

    def get_service_type(self, srv_name: str) -> Union[str, None]:
        """ get_service_type"""
        mlogger.debug("get_service_type %s", srv_name)
        if self.node is None:
            raise NodeManagerException("main node cannot be null")

        srvtype = self.srv_name_and_types.get(srv_name, None)
        if srvtype is None:
            srvinfos = self.node.get_service_names_and_types()
            for info in list(srvinfos):
                self.srv_name_and_types[info[0]] = info[1][0]
                if srv_name == info[0]:
                    srvtype = info[1][0]
        return srvtype

    def get_action_type(self, act_name: str) -> Union[str, None]:
        """get_action_type

        Args:
            act_name (str): target action name

        Raises:
            NodeManagerException: rasied when main node empty

        Returns:
            Union[str, None]: return action_type string if found action
        """

        mlogger.debug("get_action_type %s", act_name)
        if self.node is None:
            raise NodeManagerException("main node cannot be null")

        act_type = self.act_name_and_types.get(act_name, None)
        if act_type is None:
            act_infos = rclpy.action.get_action_names_and_types(self.node)
            for info in list(act_infos):
                self.act_name_and_types[info[0]] = info[1][0]
                if act_name == info[0]:
                    act_type = info[1][0]
        return act_type

    def get_topic_type(self, topic_name: str) -> Union[str, None]:
        """get_topic_type

        Args:
            topic_name (str): topic name 

        Raises:
            NodeManagerException: if self.node is None

        Returns:
            Union[str, None]: 
                it returns topic type string if the node find topic name, else returns None
        """
        mlogger.debug("get_topic_type %s", topic_name)
        if self.node is None:
            raise NodeManagerException("main node cannot be null")
        topictype = self.topic_name_and_types.get(topic_name, None)
        if topictype is None:
            topictypes = self.node.get_topic_names_and_types()
            for info in list(topictypes):
                self.topic_name_and_types[info[0]] = info[1][0]
                if topic_name == info[0]:
                    topictype = info[1][0]
        return topictype

    def create_srv_client(
            self, srv_type: Union[str, None],
            srv_name: str, bridge_id: str) -> SrvClientManager:
        """create_srv_client

        Args:
            srv_type (str): target service type
            srv_name (str): target service namne
            bridge_id (str): calling bridge id

        Raises:
            NodeManagerException: raised if cannot make service client

        Returns:
            SrvClientManager: return service client manager instance
        """
        mlogger.debug("create_srv_client %s :%s :%s",
                      srv_type, srv_name, bridge_id)
        cli_mgr = None

        _cli_id = get_hash_code('srvcli', [srv_name, bridge_id])

        with self.nm_dict_lock:
            # cli_mgr = self.srv_clients.get(bridge_id + srv_name, None)
            cli_mgr = self.srv_clients.get(_cli_id, None)
            if cli_mgr is None:
                # print("CREATE CLI ", srv_name, ":", bridge_id, "\n")
                try:
                    srv_type = self.get_service_type(srv_name)
                    if srv_type is None:
                        raise NodeManagerException("unknown service type")
                    cli_mgr = SrvClientManager(
                        self.executor, srv_type, srv_name)
                    # self.srv_clients[srv_name] = cli_mgr
                    self.srv_clients[_cli_id] = cli_mgr
                except Exception:
                    mlogger.debug(traceback.format_exc())
                    raise

            cli_mgr.add_srv_client(bridge_id)
        return cli_mgr

    def create_subscription(
            self, topic_type: Union[str, None], topic_name: str,
            bridge_id: str, callback: Callable[[str, Any], Any],
            queue_length=0, israw=False) -> SubscriptionManager:
        # bridge_id: str, callbackinfo: Dict, queue_length=0, israw=False) -> SubscriptionManager:
        """create_subscription

        Args:
            topic_type (str): target topic type
            topic_name (str): target topic name
            bridge_id (str): calling bridge id
            callback (Callable[[str, Any], None]): callback
            queue_length (int, optional): ROS subscriber parameter. Defaults to 0.
            israw (bool, optional): set to true if want raw mode . Defaults to False.

        Raises:
            NodeManagerException: raised if cannot make subscriber

        Returns:
            SubscriptionManager: return subscriber manager instance
        """
        mlogger.debug("create_subscription %s :%s :%s",
                      topic_type, topic_name, bridge_id)
        sub_mgr = self.subscriptions.get(
            topic_name, None)  # needs split raw and not raw
        if sub_mgr is None:
            try:
                if topic_type is None:
                    topic_type = self.get_topic_type(topic_name)
                    if topic_type is None:
                        raise NodeManagerException("unknown topic type")
                sub_mgr = SubscriptionManager(
                    self.executor, topic_type, topic_name, queue_length, israw)
                self.subscriptions[topic_name] = sub_mgr
            except Exception:
                mlogger.debug(traceback.format_exc())
                raise
        sub_mgr.add_subscription(bridge_id, callback)
        return sub_mgr

    def create_publisher(
            self, topic_type: str, topic_name: str,
            bridge_id: str,  queue_length=10, israw=False) -> PublishManager:
        """create_publisher

        Args:
            topic_type (str): target topic type
            topic_name (str): target topic name
            bridge_id (str): calling bridge id
            queue_length (int, optional): ROS publisher parameter. Defaults to 10.
            israw (bool, optional): set to true if want raw mode . Defaults to False.

        Raises:
            NodeManagerException: raised if cannot make publisher

        Returns:
            PublishManager: return publisher manager instance
        """
        mlogger.debug("create_publisher")

        pub_mgr = None

        with self.nm_dict_lock:
            pub_mgr = self.publisher.get(topic_name, None)
            if pub_mgr is None:
                try:
                    if topic_type is None:
                        raise NodeManagerException("topic type cannot be None")
                    pub_mgr = PublishManager(
                        self.executor, topic_type, topic_name, queue_length, israw)
                    self.publisher[topic_name] = pub_mgr
                except Exception:
                    mlogger.debug(traceback.format_exc())
                    raise
            else:
                if topic_type != pub_mgr.topic_type:
                    # pylint: disable=consider-using-f-string
                    raise NodeManagerException(
                        "The topic {topic} already exists with d different type {type}".format(
                            topic=topic_name, type=pub_mgr.topic_type))
            pub_mgr.add_publish(bridge_id)
        return pub_mgr

    def get_publisher_by_topic(self, topic_name: str) -> Union[PublishManager, None]:
        """get_publisher_by_topic

        Args:
            topic_name (str): target topic name

        Returns:
            Union[PublishManager, None]: 
                returns PublisherManager handle if target topic manager exists
        """
        return self.publisher.get(topic_name, None)

    def get_subscription_by_topic(self, topic_name: str) -> Union[SubscriptionManager, None]:
        """get_subscription_by_topic

        Args:
            topic_name (str): target topic name

        Returns:
            Union[SubscriptionManager, None]: 
                returns SubscriptionManager handle if target topic manager exists
        """
        return self.subscriptions.get(topic_name, None)

    def has_subscription(self, topic_name: str) -> bool:
        """has_subscription

        Args:
            topic_name (str): target topic name

        Returns:
            bool: returns true if target topic subscriber exists
        """
        return self.subscriptions.get(topic_name, None) is not None

    def destroy_action_server(self, action_name: str) -> None:
        """ destroy_action_server"""
        mlogger.debug("<destroy_action_server> [%s]", action_name)
        act_mgr = self.act_servers.get(action_name, None)
        if act_mgr:
            act_mgr.destroy()
            self.act_servers.pop(action_name)

    def destroy_srv_service(self, srvname: str) -> None:
        """destroy_srv_service """
        mlogger.debug("<destroy_srv_service> [%s]", srvname)
        svc_mgr = self.srv_services.get(srvname, None)
        if svc_mgr:
            svc_mgr.destroy()
            self.srv_services.pop(srvname)

    def destroy_publisher(self, topic_name: str, bridge_id: str) -> None:
        """destroy_publisher"""
        pub_mgr = self.publisher.get(topic_name, None)
        if pub_mgr:
            pub_mgr.remove_publish(bridge_id)
            if not pub_mgr.destroy_when_empty():
                self.publisher.pop(topic_name)

    def destroy_subscription(self, topic_name: str, bridge_id: str) -> None:
        """destroy_subscription"""
        sub_mgr = self.subscriptions.get(topic_name, None)
        if sub_mgr:
            sub_mgr.remove_subscription(bridge_id)
            if not sub_mgr.destroy_when_empty():
                self.subscriptions.pop(topic_name)

    def destroy_publisher_by_topic(self, topic_name: str) -> None:
        """destroy_publisher_by_topic"""
        val = self.publisher.pop(topic_name, None)
        if val is not None:
            val.destroy()

    def destroy_subscription_by_topic(self, topic_name: str) -> None:
        """destroy_subscription_by_topic"""
        val = self.subscriptions.pop(topic_name, None)
        if val is not None:
            val.destroy()

    def reset(self) -> None:
        """reset"""
        try:
            self.destroy_publishers()
            self.destroy_subscriptions()
            self.destroy_srv_services()
            self.destroy_srv_clients()
            self.destroy_act_servers()
            self.destroy_act_clients()
        except Exception:
            mlogger.error(traceback.format_exc())

    def destroy_publishers(self) -> None:
        """destroy_publishers"""
        mlogger.debug("destroy_publishers")
        try:
            for value in list(self.publisher.values()):
                value.destroy()
            self.publisher.clear()
        except Exception:
            mlogger.error(traceback.format_exc())

    def destroy_subscriptions(self) -> None:
        """destroy_subscriptions"""
        mlogger.debug("destroy_subscriptions")
        try:
            for value in list(self.subscriptions.values()):
                value.destroy()
            self.subscriptions.clear()
        except Exception:
            mlogger.error(traceback.format_exc())

    def destroy_srv_services(self) -> None:
        """destroy_srv_services"""
        mlogger.debug("destroy_srv_services")
        try:
            for value in list(self.srv_services.values()):
                value.destroy()
            self.srv_services.clear()
        except Exception:
            mlogger.error(traceback.format_exc())

    def destroy_srv_clients(self) -> None:
        """destroy_srv_clients"""
        mlogger.debug("destroy_srv_clients")
        try:
            for value in list(self.srv_clients.values()):
                value.destroy()
            self.srv_clients.clear()
        except Exception:
            mlogger.error(traceback.format_exc())

    def destroy_act_servers(self) -> None:
        """destroy_act_servers"""
        mlogger.debug("destroy_act_servers")
        try:
            for value in list(self.act_servers.values()):
                value.destroy()
            self.act_servers.clear()
        except Exception:
            mlogger.error(traceback.format_exc())

    def destroy_act_clients(self) -> None:
        """destroy_act_clients"""
        mlogger.debug("destroy_act_clients")
        try:
            for value in list(self.act_clients.values()):
                value.destroy()
            self.act_clients.clear()
        except Exception:
            mlogger.error(traceback.format_exc())

    def destroy_publisher_by_bridge_id(self, bridge_id: str) -> None:
        """destroy_publisher_by_bridge_id"""
        mlogger.debug("destroy_publisher_by_bridge_id")
        try:
            with self.nm_dict_lock:  # fix publisher duplicated error
                for sub in list(self.publisher.values()):
                    sub.remove_publish(bridge_id)

                tempv = {}
                for k, val in list(self.publisher.items()):
                    if val.destroy_when_empty():
                        tempv[k] = val
                self.publisher = tempv
        except Exception:
            mlogger.error(traceback.format_exc())

    def destroy_subscription_by_bridge_id(self, bridge_id: str) -> None:
        """destroy_subscription_by_bridge_id"""
        mlogger.debug("destroy_subscription_by_bridge_id")
        try:
            for sub in list(self.subscriptions.values()):
                sub.remove_subscription(bridge_id)
            tempv = {}
            for k, val in list(self.subscriptions.items()):
                if val.destroy_when_empty():
                    tempv[k] = val
            self.subscriptions = tempv
        except Exception:
            mlogger.error(traceback.format_exc())

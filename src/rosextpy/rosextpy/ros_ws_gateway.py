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

# filename: rosextpy.ros_ws_gateway
# author: parasby@gmail.com

# import sys
import asyncio
# import threading
import json
import uuid
import logging
import traceback
import functools
# import datetime
from typing import List, Dict, Any, Callable, Awaitable, Union, Tuple  # Tuple, Any
import concurrent.futures
import cbor
import rclpy.action
from rosextpy.node_manager import NodeManager, ROSServiceFailException
from rosextpy.ext_type_support import (
    ros_to_text_dict, ros_to_bin_dict, ros_serialize, ros_deserialize)
from rosextpy.ext_type_support import (
    ros_from_text_dict, ros_from_bin_dict, ros_from_compress, raw_from_compress, ros_to_compress, raw_to_compress)
from rosextpy.websocket_utils import WebSocketDisconnect

mlogger = logging.getLogger('ros_ws_gateway')


class InvalidCommandException(Exception):
    """InvalidCommandException """

    def __init__(self, msg: str = ""):
        super().__init__("gateway command fail :"+msg)


class RosWsGatewayException(Exception):
    """RosWsGatewayException """

    def __init__(self, msg: str = ""):
        super().__init__("gateway exception :"+msg)


class RosWsGatewayClosedException(Exception):
    """
    Raised when the gateway is closed
    """

    def __init__(self, msg: str = ""):
        super().__init__("gateway closed exception :"+msg)

# async def OnConnectCallback(ws_gateway):
#     pass


# async def OnDisconnectCallback(ws_gateway):
#     pass


# async def OnErrorCallback(ws_gateway, err: Exception):
#     pass

class MessageParser():
    """ MessageParser """

    def parse(self, msg: Union[bytes, str]):
        """ process """
        try:
            if isinstance(msg, bytes):
                return cbor.loads(msg)
            return json.loads(msg)
        except Exception as exc:
            mlogger.debug(traceback.format_exc())
            raise InvalidCommandException() from exc


def bytesToJSBuffer(mesg: Any) -> Dict[str, Any]:  # pylint: disable=invalid-name
    """bytesToJSBuffer

    Args:
        mesg (Any): message

    Returns:
        Dict[str, Any]: JSBuffer dict
    """
    return {'type': 'Buffer', 'data': list(mesg)}


class RosWsGateway():
    """ Process ros2 websocket gateway protocol
    """

    def __init__(self, wshandle, node_mgr, loop,
                 timeout=1.0, **kwargs):
        mlogger.debug("RosWsGateway created")
        self.activate = True
        self.bridge_id = uuid.uuid4().hex
        self.parser = MessageParser()
        self.op_map = {
            "advertise": self._op_advertise,
            "unadvertise": self._op_unadvertise,
            "publish": self._op_publish,
            "subscribe": self._op_subscribe,
            "unsubscribe": self._op_unsubscribe,
            "status": self._op_status,
            "call_service": self._op_call_service,
            # The gateway receives a call service from another gateway through the websocket
            "service_response": self._op_service_response,
            # The gateway receives a json service response
            #   and send ROS service response in the local client
            "advertise_service": self._op_advertise_service,
            # The gateway plays a role of a service server in the local network
            "unadvertise_service": self._op_unadvertise_service,
            # The gateway stops the role of a service server
            "call_action": self._op_call_action,
            # The gateway receives a ROS call action and send a JSON call action
            #   to another gateway
            "action_result": self._op_action_result,
            # The gateway receives an action result from another gateway
            #   and publishes the result in the local network.
            "action_feedback": self._op_action_feedback,
            # The gateway receives an action feedback from another gateway
            #   and publishes the feedback in the local network.
            "advertise_action": self._op_advertise_action,
            # The gateway plays a role of a action server in the local network
            "unadvertise_action": self._op_unadvertise_action,
            # The gateway stops the role of a action server
        }
        # key : topicName, value : (topicType, compression)
        self.published_topic: Dict[str, Tuple[str, str]] = {}
        # key : topicName, value : (topicType, compression)
        self.subscribed_topic: Dict[str, Tuple[str, str]] = {}
        self.node_manager: NodeManager = node_mgr
        self.wshandle = wshandle
        self.loop = loop
        self.timeout = timeout
        # loop=self.loop)
        self.batch_queue: "asyncio.Queue[Tuple]" = asyncio.Queue()
        self.id_counter = 0
        self._connect_handlers: List[Callable[[
            "RosWsGateway"], Awaitable]] = []
        self._disconnect_handlers: List[Callable[[
            "RosWsGateway"], Awaitable]] = []
        self._error_handlers: List[Callable[[
            "RosWsGateway", Exception], Awaitable]] = []
        self._closed = asyncio.Event()  # loop=self.loop)
        self._context = kwargs or {}
        self._batch_task = None
        self._adv_services: Dict[str, Dict[str, Any]] = {}
        self._adv_action_servers: Dict[str, Dict[str, Any]] = {}
        self.exposed_services: Dict[str, str] = {}
        self.exposed_actions: Dict[str, str] = {}

    async def send(self, data: Dict[str, Any], hasbytes: bool = False) -> None:
        """send

        Args:
            data (Dict[str, Any]): data to send
            hasbytes (bool, optional): it it true when data have bytes. Defaults to False.
        """
        mlogger.debug("send %s", type(data))
        # a = datetime.datetime.now()
        # print('send ... =', hasbytes, ' and ', data)
        try:
            if hasbytes:
                message = cbor.dumps(data)
            else:
                message = json.dumps(data)
            # b = datetime.datetime.now()
            # print("mesage type is ", type(message))
            #mlogger.debug("send %d bytes [byte=%r]", len(message), hasbytes)
            await self.wshandle.send(message)
            # c = datetime.datetime.now()
            # print("T: ",(b-a).microseconds/1000.0 , "ms ... ", (c-b).microseconds/1000.0,
            #       "ms ...bytes", hasbytes, " len ", len(message), "kB")
        except Exception:
            mlogger.debug(traceback.format_exc())
            raise

    def _run_async_func(self, coro):
        # a = datetime.datetime.now()
        future = asyncio.run_coroutine_threadsafe(coro, self.loop)
        try:
            # if receiver does not receive message, it can throw TimeoutError
            future.result()  # self.timeout)
        except (asyncio.CancelledError, asyncio.CancelledError, TimeoutError) as exc:
            future.cancel()
            mlogger.debug("task cancelled %s", exc)
        except concurrent.futures.TimeoutError:
            future.cancel()
            mlogger.debug("timeout exception occured")
        except WebSocketDisconnect:
            future.cancel()
            mlogger.debug("websocket disconnected")
        except Exception as excc:
            future.cancel()
            mlogger.debug("exception occured %s", type(excc))
        # finally:
        #     b = datetime.datetime.now()
        #     print("T: ",(b-a).microseconds/1000.0 , "ms ... ")

    async def _clear_act_pending_task(self, action_name):
        mlogger.debug("_clear_act_pending_task")
        t_ctx = self._adv_action_servers.get(action_name, None)
        if t_ctx:
            t_called = t_ctx['called']
            for (ft_fut, goal_handle, resp_cls, feed_cls) in t_called.values():
                _ = feed_cls
                goal_handle.abort()
                ft_fut.set_result(resp_cls())

    async def _clear_srv_pending_task(self, srv_name):
        mlogger.debug("_clear_srv_pending_task")
        t_svc_ctx = self._adv_services.get(srv_name, None)
        if t_svc_ctx:
            t_called = t_svc_ctx['called']
            for (ft_fut, _) in t_called.values():
                ft_fut.cancel()
                ft_fut.set_exception(ROSServiceFailException(srv_name))

    async def _clear_all_pending_task(self):
        mlogger.debug("_clear_all_pending_task")
        for t_svc_name in self._adv_services:
            await self._clear_srv_pending_task(t_svc_name)
            self.node_manager.destroy_srv_service(t_svc_name)

        for t_act_name in self._adv_action_servers:
            await self._clear_act_pending_task(t_act_name)
            self.node_manager.destroy_action_server(t_act_name)

    async def close(self):
        """close
        """
        mlogger.debug("close")
        try:
            await self.wshandle.close()
            self._closed.set()
            await self._clear_all_pending_task()
            self._adv_services.clear()
            if self._batch_task:
                self._batch_task.cancel()
                await asyncio.sleep(0)
                self._batch_task = None
            if self.node_manager:
                self.node_manager.remove_with_gateway(self.bridge_id)
            await self._on_handler_event(self._disconnect_handlers, self)
        except Exception as excc:
            mlogger.debug("close exception %s", type(excc))

    def is_closed(self):
        """ is_closed """
        return self._closed.is_set()

    async def wait_until_closed(self) -> bool:
        """wait_until_closed"""

        return await self._closed.wait()

    # async def spin(self):
    #     try:
    #         while not self.is_closed():
    #             mesg = await self.receive()
    #             if not mesg:
    #                 raise WebSocketDisconnect
    #             await self.on_message(mesg)
    #     except Exception:
    #         raise

    async def on_message(self, data: Union[bytes, str]):
        """on_message

        Args:
            data (Union[bytes,str]): message data
        """
        mlogger.debug("on_message %s", type(data))
        # print("data ... \n")
        # print(data)
        # print("\n.....")
        try:
            cmd_data = self.parser.parse(data)
            # print('cmddata ...\n ', cmd_data)
            await self._execute_command(cmd_data)
        except InvalidCommandException as err:
            mlogger.debug(
                "[on_message] Invalid command message message=[%s], error=%s", data[:80], err)
            await self._on_error(err)
        except Exception as err:
            mlogger.debug(
                "[on_message] Some command error message=[%s], error=%s", data[:580], err)
            await self._on_error(err)
            raise

    def register_connect_handler(
            self, coros: Union[Callable[["RosWsGateway"], Awaitable], None] = None):
        """Register a connection handler callback that will be called 
        (As an async task)) with the gateway

        :param coros (Union[Callable[["RosWsGateway"], Awaitable], None]): async callback
        :return: None
        """
        if coros is not None:
            self._connect_handlers.extend([coros])

    def register_disconnect_handler(
            self, coros: Union[Callable[["RosWsGateway"], Awaitable], None] = None):
        """
        Register a disconnect handler callback that will be called
        (As an async task)) with the gateway id

        Args:
            coros (List[Coroutine]): async callback
        """
        if coros is not None:
            self._disconnect_handlers.extend([coros])

    def register_error_handler(
            self, coros:
            Union[Callable[["RosWsGateway", Exception], Awaitable], None] = None):
        """
        Register an error handler callback that will be called
        (As an async task)) with the channel and triggered error.

        Args:
            coros (List[Coroutine]): async callback
        """
        if coros is not None:
            self._error_handlers.extend([coros])

    async def _on_handler_event(self, handlers, *args, **kwargs):
        await asyncio.gather(*(callback(*args, **kwargs) for callback in handlers))

    async def on_connect(self):
        """on_connect
        """
        mlogger.debug("on_connect")
        self._batch_task = asyncio.create_task(self.batch_cmd())
        await self._on_handler_event(self._connect_handlers, self)

    async def _on_error(self, error: Exception):
        mlogger.debug("on_error")
        await self._on_handler_event(self._error_handlers, self, error)

    async def _op_advertise(self, cmd_data):
        mlogger.debug("_op_advertises %s", cmd_data)
        topic_name = cmd_data['topic']
        (topic_type, _compression) = self.published_topic.get(
            topic_name, (None, None))

        if topic_type is None:  # None
            topic_type = cmd_data['type']
            _compression = cmd_data.get('compression', None)
            _israw = bool(_compression == 'cbor-raw')
            self.published_topic[topic_name] = (topic_type, _compression)
            if self.node_manager:
                self.node_manager.create_publisher(
                    topic_type, topic_name, self.bridge_id, _israw)
        else:
            if topic_type != cmd_data['type']:
                raise RosWsGatewayException(
                    f"The topic {topic_name} already exists with a different type")
            _compression = cmd_data.get('compression', None)
            _israw = bool(_compression == 'cbor-raw')
            if self.node_manager:
                _pm = self.node_manager.get_publisher_by_topic(topic_name)
                if _pm is None:
                    mlogger.error("publisher Cannot be Null")
                else:
                    _pm.change_raw(_israw)

        return "OK"

    async def _op_unadvertise(self, cmd_data):
        mlogger.debug("_op_unadvertise %s", cmd_data)
        topic = cmd_data['topic']
        if not topic in self.published_topic:
            raise RosWsGatewayException(
                f"The topic {topic} does not exist")

        self.published_topic.pop(topic, None)

        if self.node_manager:
            self.node_manager.destroy_publisher(topic, self.bridge_id)

        return "OK"

    def _decode_mesg_data(self, mesg_items, field, target_class, target_obj, arg_compression):
        _compression = mesg_items.get('compression', None)
        _target = mesg_items.get(field, None)
        if _target is None:
            raise RosWsGatewayException(
                f'unknown target={field}')
        if _compression is not None:
            if arg_compression != _compression:
                raise RosWsGatewayException(
                    f'Illegal compression parameter={_compression}')
        else:
            _compression = arg_compression
        if _compression is None or _compression == 'none':
            return ros_from_text_dict(_target, target_obj)
        if _compression == 'js-buffer':
            return ros_from_bin_dict(_target['data'][0], target_obj)
        if _compression == 'cbor':
            return ros_from_bin_dict(_target, target_obj)
        if _compression == 'cbor-raw':
            # _tsecs = _target['secs']
            # _tnsecs = _target['tnsecs']
            # _ = _tsecs
            # _ = _tnsecs
            #return ros_deserialize(_target['bytes'], target_class)
            return _target['bytes'] # donot deserialize data: it wiil be RTPS message
        if _compression == 'zip':
            return ros_from_compress(_target, target_obj)
        if _compression == 'rawzip':
            return raw_from_compress(_target, target_obj)
        raise RosWsGatewayException(
            f'unknown compression methods={_compression}')

    async def _op_publish(self, cmd_data):  # When encoding is not cbor
        mlogger.debug("_op_publish %s", cmd_data['topic'])
        try:
            topic = cmd_data['topic']
            (_type, _compression) = self.published_topic.get(topic, (None, None))
            if _type is None:
                raise RosWsGatewayException(
                    f"The topic {topic} does not exist")
            if self.node_manager:
                pub = self.node_manager.get_publisher_by_topic(topic)
                if pub:
                    pub.publish(self._decode_mesg_data(
                        cmd_data,
                        'msg', pub.get_class_type(), pub.get_class_obj(), _compression))
        except Exception as _ex:
            mlogger.debug(traceback.format_exc())
            raise

        return "OK"

    async def _op_subscribe(self, cmd_data: Dict[str, Any],
                            extra_cmd: Union[Dict[str, Any], None] = None):
        mlogger.debug("_op_subscribe %s", cmd_data)
        try:
            _local_topic = cmd_data.get('topic', None)
            if _local_topic is None:
                raise RosWsGatewayException('subscribe parameter erro')
            _remote_topic = _local_topic
            if extra_cmd is not None:
                _remote_topic = extra_cmd['remote_topic']

            # In new Bridge Protocol , it is option
            _topic_type: Union[str, None] = cmd_data.get('type', None)
            _queue_length = cmd_data.get('queue_length', 0)
            _compression = cmd_data.get('compression', None)  # 221102
            israw = bool(_compression == 'cbor-raw' or _compression == 'rawzip')
            if self.node_manager:
                if _topic_type is None:
                    _topic_type = self.node_manager.get_topic_type(
                        _local_topic)
                    if _topic_type is None:
                        raise RosWsGatewayException('unkown topic type')
                self.subscribed_topic[_local_topic] = (
                    _topic_type, _compression)  # 230601
                self.node_manager.create_subscription(
                    _topic_type, _local_topic, self.bridge_id,
                    functools.partial(
                        self._ros_send_subscription_callback,
                        compression=_compression, remote_topic=_remote_topic),
                    queue_length=_queue_length, israw=israw)

        except Exception as _ex:
            mlogger.debug(traceback.format_exc())
            raise RosWsGatewayException('internal error') from _ex

        return "OK"

    async def _op_unsubscribe(self, cmd_data: Dict[str, Any]):
        mlogger.debug("_op_unsubscribe  %s", cmd_data)
        topic = cmd_data['topic']
        self.subscribed_topic.pop(topic, None)
        if self.node_manager:
            if not self.node_manager.has_subscription(topic):
                raise RosWsGatewayException(
                    f"The topic {topic} does not exist")
            self.node_manager.destroy_subscription(topic, self.bridge_id)

        return "OK"

    async def _op_status(self, cmd_data: Dict[str, Any]):
        mlogger.debug("_op_status  %s", cmd_data)
        return None

    async def _op_call_service(self, cmd_data: Dict):
        mlogger.debug("_op_call_service  %s", cmd_data)
        try:
            _service_name = cmd_data['service']
            # In new Bridge Protocol , it is option
            _service_type = cmd_data.get('type', None)
            _args = cmd_data.get('args', None)
            _callid = cmd_data.get('id', None)
            _compression = cmd_data.get('compression', None)
            if self.node_manager:
                _srv_cli = self.node_manager.create_srv_client(
                    _service_type, _service_name, self.bridge_id)
                if _srv_cli:
                    _srv_cli.call_service_async(
                        _args,
                        functools.partial(
                            self._ros_send_srvcli_response_callback,
                            call_id=_callid, compression=_compression))

        except Exception as _ex:
            mlogger.debug(traceback.format_exc())
            raise RosWsGatewayException('internal error') from _ex

        return "OK"

    #
    # _op_service_response
    # command [
    #           service : serviceName
    #           id: request id
    #           values:  result of service request
    #         ]
    #

    async def _op_service_response(self, cmd_data: Dict[str, Any]):
        mlogger.debug("_op_service_response  %s", cmd_data)
        service_name = cmd_data['service']
        ctx = self._adv_services.get(service_name)
        if ctx:
            callid = cmd_data['id']
            _t1 = ctx['called'][callid]
            if _t1:
                (rq_future, resp_cls) = _t1
                res_value = cmd_data['values']
                ros_response = ros_from_text_dict(res_value, resp_cls())
                if cmd_data['result']:
                    rq_future.set_result(ros_response)
                else:
                    rq_future.cancel()
                    rq_future.set_exception(
                        ROSServiceFailException(service_name))
            else:
                return "Unknon call id"
        else:
            return "Unknown Service"

        return "OK"

    #
    # advertise_service
    # command [
    #           service : serviceName
    #           type    : serviceTypeName
    #         ]
    #
    async def _op_advertise_service(self, cmd_data: Dict[str, Any]):
        mlogger.debug("_op_advertise_service  %s", cmd_data)
        try:
            _service_name = cmd_data['service']
            _type_name = cmd_data['type']
            _compression = cmd_data.get('compression', None)
            if self.node_manager:
                srv_svc = self.node_manager.create_srv_service(
                    _type_name, _service_name, self.bridge_id,
                    functools.partial(
                        self._ros_service_proxy_callback, compression=_compression))
                self._adv_services[_service_name] = {
                    'svc': srv_svc, 'called': {}}
        except Exception as _ex:
            mlogger.debug(traceback.format_exc())
            raise RosWsGatewayException('internal error') from _ex
        return "OK"

    #
    # _op_unadvertise_service
    # command [
    #           service : serviceName
    #         ]
    #
    async def _op_unadvertise_service(self, cmd_data: Dict[str, Any]):
        mlogger.debug("_op_unadvertise_service  %s", cmd_data)
        try:
            _service_name = cmd_data['service']
            if self._adv_services.get(_service_name, None):
                await self._clear_srv_pending_task(_service_name)
                self._adv_services.pop(_service_name)
                if self.node_manager:
                    self.node_manager.destroy_srv_service(_service_name)
        except Exception as _ex:
            mlogger.debug(traceback.format_exc())
            raise RosWsGatewayException('internal error') from _ex

        return "OK"

    #
    # advertise_service
    # command [
    #           action : actionName
    #           type    : serviceTypeName
    #         ]
    #
    async def _op_advertise_action(self, cmd_data: Dict[str, Any]):
        mlogger.debug("_op_advertise_action1111  %s", cmd_data)
        try:
            _action_name = cmd_data['action']
            _type_name = cmd_data['type']
            _compression = cmd_data.get('compression', None)
            if self.node_manager:
                act_svc = self.node_manager.create_action_server(
                    _type_name, _action_name, self.bridge_id,
                    functools.partial(
                        self._ros_action_proxy_callback, compression=_compression))
                self._adv_action_servers[_action_name] = {
                    'svc': act_svc, 'called': {}}
        except Exception as _ex:
            mlogger.debug(traceback.format_exc())
            raise RosWsGatewayException('internal error') from _ex

        return "OK"

    async def _op_call_action(self, cmd_data: Dict[str, Any]):
        mlogger.debug("_op_call_action  %s", cmd_data)
        try:
            _action_name = cmd_data['action']
            _action_type = cmd_data.get('type', None)
            _args = cmd_data.get('args', None)
            _call_id = cmd_data.get('id', None)
            _compression = cmd_data.get('compression', None)
            if self.node_manager:
                srv_cli = self.node_manager.create_action_client(
                    _action_type, _action_name, self.bridge_id)

                if srv_cli:
                    srv_cli.send_goal_async(
                        _args,
                        None,  # goal_id have to be UUID type
                        feedback_callback=functools.partial(
                            self._ros_send_actcli_feedback_callback,
                            call_id=_call_id, compression=_compression),
                        action_result_callback=functools.partial(
                            self._ros_send_actcli_result_callback,
                            call_id=_call_id, compression=_compression),
                        goal_accept_callback=self._ros_send_actcli_accept_callback,
                        goal_reject_callback=self._ros_send_actcli_reject_callback,
                    )

        except Exception as _ex:
            mlogger.debug(traceback.format_exc())
            raise RosWsGatewayException('internal error') from _ex

        return "OK"

    # 'op' : 'action_result',
    # 'id' : callid,
    # 'action' : 'fibonacci',
    # 'values' : {'sequence' : [0,1,2,3,4,5]},
    # 'result' : True

    async def _op_action_result(self, cmd_data: Dict[str, Any]):
        mlogger.debug("_op_action_result  %s", cmd_data)
        action_name = cmd_data['action']
        ctx = self._adv_action_servers.get(action_name)
        if ctx:
            call_id = cmd_data['id']
            _t1 = ctx['called'][call_id]
            if _t1:
                (rq_future, goal_handle, resp_cls, feed_cls) = _t1
                _ = feed_cls
                res_value = cmd_data['values']
                ros_response = ros_from_text_dict(res_value, resp_cls())
                if cmd_data['result']:
                    goal_handle.succeed()
                    rq_future.set_result(ros_response)
                else:
                    goal_handle.abort()
                    rq_future.set_result(resp_cls())
                    # rq_future.cancel()
                    # rq_future.set_exception(ROSServiceFailException(action_name))
            else:
                return "Unknon action call id"

        else:
            return "Unknown Action"

        return "OK"

    async def _op_action_feedback(self, cmd_data: Dict[str, Any]):
        mlogger.debug("_op_action_feedback  %s", cmd_data)
        action_name = cmd_data['action']
        ctx = self._adv_action_servers.get(action_name)
        if ctx:
            call_id = cmd_data['id']
            _t1 = ctx['called'][call_id]
            if _t1:
                (rq_future, goal_handle, resp_cls, feed_cls) = _t1
                _ = rq_future
                _ = resp_cls
                res_value = cmd_data['values']
                feedback = ros_from_text_dict(res_value, feed_cls())
                goal_handle.publish_feedback(feedback)
            else:
                return "Unknon action call id"

        else:
            return "Unknown Action"

        return "OK"

    async def _op_unadvertise_action(self, cmd_data: Dict[str, Any]):
        mlogger.debug("_op_unadvertise_action  %s", cmd_data)
        try:
            action_name = cmd_data['action']
            if self._adv_action_servers.get(action_name, None):
                await self._clear_act_pending_task(action_name)
                self._adv_action_servers.pop(action_name)
                if self.node_manager:
                    self.node_manager.destroy_action_server(action_name)

        except Exception as _ex:
            mlogger.debug(traceback.format_exc())
            raise RosWsGatewayException('internal error') from _ex

        return "OK"

    def _ros_send_actcli_feedback_callback(
            self, act_name: str, feedback_data: Any,
            goal_id: uuid.UUID, call_id: Union[str, None] = None, compression=None):
        mlogger.debug("_ros_send_actcli_feedback_callback ")
        response = {"op": "action_feedback",
                    "goal_id": str(goal_id),
                    "action": act_name, "result": True}
        if call_id is not None:
            response["id"] = call_id

        self._send_mesg_data(response, 'values', feedback_data, compression)

    def _ros_send_actcli_result_callback(
            self, act_name: str, result_data: Any,
            goal_id: uuid.UUID, call_id: Union[str, None] = None, compression=None):
        mlogger.debug("_ros_send_actcli_result_callback ")
        response = {"op": "action_result",
                    "goal_id": str(goal_id),
                    "action": act_name, "result": True}
        if call_id is not None:
            response["id"] = call_id
        self._send_mesg_data(response, 'values', result_data, compression)

    def _ros_send_actcli_accept_callback(
            self, act_name: str,
            goal_handle: rclpy.action.client.ClientGoalHandle):
        _ = act_name
        _ = goal_handle
        mlogger.debug("_ros_send_actcli_accept_callback ")

    def _ros_send_actcli_reject_callback(
            self, act_name: str,
            goal_handle: rclpy.action.client.ClientGoalHandle):
        _ = act_name
        _ = goal_handle
        mlogger.debug("_ros_send_actcli_reject_callback ")

    async def _ros_action_proxy_callback(
            self, action_name: str,
            action_type: str, goal_handle: rclpy.action.server.ServerGoalHandle, compression):
        mlogger.debug("_ros_action_proxy_callback")

        call_id = ''.join(['act:', uuid.uuid4().hex])
        callmsg = {'op': 'call_action', 'id': call_id,
                   'action': action_name, 'type': action_type}

        ctx = self._adv_action_servers.get(action_name)
        if ctx:
            rq_future = ctx['svc'].get_waiter()  # get future from ros context
            ctx['called'][call_id] = (
                rq_future, goal_handle,
                ctx['svc'].get_result_class(), ctx['svc'].get_feedback_class())

            _mesg_items, _hasbytes = self._compose_mesg_data(
                callmsg, 'args', goal_handle.request, compression)
            await self.send(_mesg_items, hasbytes=_hasbytes)
            try:
                return await rq_future  # wait response and return it to ROS rclpy logic
            except ROSServiceFailException:
                mlogger.debug(
                    "The call_action for [%s] gets an error", action_name)
                raise
            finally:
                if self._adv_action_servers.get(action_name, None):
                    del self._adv_action_servers[action_name]['called'][call_id]
        else:
            mlogger.debug("The service [%s] was not advertised", action_name)
            raise ROSServiceFailException(action_name)

    async def _ros_service_proxy_callback(self, srv_name, srv_type, request, response, compression):
        mlogger.debug("_ros_service_proxy_callback")
        # this callback is called from ROS executor
        _ = response

        call_id = ''.join(['svc:', uuid.uuid4().hex])
        callmsg = {'op': 'call_service', 'id': call_id,
                   'service': srv_name, 'type': srv_type}
        ctx = self._adv_services.get(srv_name)
        if ctx:
            rq_future = ctx['svc'].get_waiter()  # get future from ros context
            ctx['called'][call_id] = (
                rq_future, ctx['svc'].get_response_class())
            _mesg_items, _hasbytes = self._compose_mesg_data(
                callmsg, 'args', request, compression)
            await self.send(_mesg_items, hasbytes=_hasbytes)
            try:
                return await rq_future  # wait response and return it to ROS rclpy logic
            except ROSServiceFailException:
                mlogger.debug(
                    "The call_service for [%s] gets an error", srv_name)
                raise
            finally:
                if self._adv_services.get(srv_name, None):
                    del self._adv_services[srv_name]['called'][call_id]
        else:
            mlogger.debug("The service [%s] was not advertised", srv_name)
            raise ROSServiceFailException(srv_name)

    # node_manager needs sync callback
    def _ros_send_srvcli_response_callback(
            self, srv_name: str, res_mesg: Any,
            call_id: Union[str, None],  compression: Union[str, None]):
        mlogger.debug("_ros_send_srvcli_response_callback ")
        response = {"op": "service_response",
                    "service": srv_name,
                    "result": True}
        if call_id is not None:
            response["id"] = call_id
        # if hasattr(res_mesg, 'topics'):
        #     print("res_mesg ... ", getattr(res_mesg, 'topics'), "\n" )
        self._send_mesg_data(response, 'values', res_mesg, compression)

    def _send_mesg_data(self, mesg_items: Dict[str, Any], data_tag, data_mesg, compression):
        _mesg_items, _hasbytes = self._compose_mesg_data(
            mesg_items, data_tag, data_mesg, compression)
        self._run_async_func(self.send(_mesg_items, hasbytes=_hasbytes))

    def _compose_mesg_data(self, mesg_items: Dict[str, Any], data_tag, data_mesg, compression):
        if compression is None or compression == 'none':
            mesg_items[data_tag] = ros_to_text_dict(data_mesg)
            return mesg_items, False

        if compression == 'js-buffer':
            mesg_items[data_tag] = bytesToJSBuffer(
                ros_to_bin_dict(data_mesg))  # it will be text
        elif compression == 'cbor':
            mesg_items[data_tag] = ros_to_bin_dict(data_mesg)
        elif compression == 'cbor-raw':
            (secs, nsecs) = self.node_manager.get_now().seconds_nanoseconds()
            if isinstance(data_mesg, bytes):
                mesg_items[data_tag] = {
                    "secs": secs, "nsecs": nsecs, "bytes": data_mesg}
            else:
                mesg_items[data_tag] = {
                    "secs": secs, "nsecs": nsecs, "bytes": ros_serialize(data_mesg)}
        elif compression == 'zip':
            mesg_items[data_tag] = ros_to_compress(data_mesg)
        elif compression == 'rawzip':
            mesg_items[data_tag] = raw_to_compress(data_mesg)
        else:
            mlogger.debug('unknown compression methods %s', compression)
            raise RosWsGatewayException(
                f'unknown compression methods:{compression}')
        mesg_items['compression'] = compression
        return mesg_items, True

    # node_manager needs sync callback
    def _ros_send_subscription_callback(self,
                                        topic_name, mesg, compression, remote_topic=None):
        if remote_topic is None:
            remote_topic = topic_name
        mlogger.debug("sendSubscription  %s", remote_topic)
        response = {"op": "publish", "topic": remote_topic}  # 221102
        self._send_mesg_data(response, 'msg', mesg, compression)

    async def _send_back_operation_status(self, opid: str, msg='', level='none'):
        mlogger.debug("sendBackOperationStatus id= %s", opid)
        if level == 'none':
            return
        status = {"op": "status", "level": level, "msg": msg, "id": opid}
        # status = {"op": "set_level", "level": level, "msg": msg, "id": opid}
        # await self.send(status) # rosbridge does not receive status

    async def batch_cmd(self):
        """ batch_cmd """
        mlogger.debug("batch_cmd")        

        while True:
            try:
                item_tuple = await self.batch_queue.get()                
                mlogger.debug("item is %s:%s:%s:%s:%s",
                              item_tuple[0], item_tuple[1],
                              item_tuple[2], item_tuple[3], item_tuple[4])

                _compression = item_tuple[4]
                if item_tuple[3] is True:
                    _compression = 'cbor-raw'

                self.id_counter += 1
                if item_tuple[0] == 'pub':
                    subid = ''.join(
                        ['subscribe:', str(self.bridge_id), ':', str(self.id_counter)])
                    await self._op_subscribe(
                        {'op': 'subscribe', 'id': subid,
                         'topic': item_tuple[1], 'type': item_tuple[2],
                         'compression':  _compression})
                    advid = ''.join(
                        ['advertise:', str(self.bridge_id), ':', str(self.id_counter)])
                    data = {'op': 'advertise', 'id': advid,
                            'topic': item_tuple[1], 'type': item_tuple[2]}
                    if _compression is not None:
                        data['compression'] = _compression

                    await self.send(data)

                elif item_tuple[0] == 'unadv':
                    try:
                        await self._op_unsubscribe({'op': 'unsubscribe', 'topic': item_tuple[1]})
                        cmdid = ''.join(
                            ['unadvertise:', str(self.bridge_id), ':', str(self.id_counter)])
                        data = {'op': 'unadvertise',
                                'id': cmdid, 'topic': item_tuple[1]}
                        await self.send(data)
                    except RosWsGatewayException as err:
                        mlogger.debug("unadv exception '%s'", err)

                elif item_tuple[0] == 'sub':
                    advid = ''.join(
                        ['advertise:', str(self.bridge_id), ':', str(self.id_counter)])
                    await self._op_advertise(
                        {'op': 'advertise', 'id': advid,
                         'topic': item_tuple[1], 'type': item_tuple[2],
                         'compression':  _compression})
                    subid = ''.join(
                        ['subscribe:', str(self.bridge_id), ':', str(self.id_counter)])
                    data = {'op': 'subscribe',  'id': subid,
                            'topic': item_tuple[1], 'type': item_tuple[2]}
                    if _compression is not None:
                        data['compression'] = _compression
                    await self.send(data)

                elif item_tuple[0] == 'unsub':
                    try:
                        await self._op_unadvertise({'op': 'unadvertise', 'topic': item_tuple[1]})
                        cmdid = ''.join(
                            ['unsubscribe:', str(self.bridge_id), ':', str(self.id_counter)])
                        data = {'op': 'unsubscribe',
                                'id': cmdid, 'topic': item_tuple[1]}
                        await self.send(data)
                    except RosWsGatewayException as err:
                        mlogger.debug("unsub exception '%s'", err)

                elif item_tuple[0] == 'expsrv':  # expose service to remote gateway
                    reqid = ''.join(
                        ['exposesrv:', str(self.bridge_id), ':', str(self.id_counter)])
                    data = {'op': 'advertise_service', 'id': reqid,
                            'service': item_tuple[1], 'type': item_tuple[2]}
                    self.exposed_services[item_tuple[1]] = item_tuple[2]
                    if _compression is not None:
                        data['compression'] = _compression
                    await self.send(data)

                elif item_tuple[0] == 'delsrv':  # hide exposed service to remote gateway
                    reqid = ''.join(
                        ['delsrv:', str(self.bridge_id), ':', str(self.id_counter)])
                    data = {'op': 'unadvertise_service', 'id': reqid,
                            'service': item_tuple[1]}
                    await self.send(data)
                    self.exposed_services.pop(item_tuple[1], None)

                elif item_tuple[0] == 'expact':  # expose action to remote gateway
                    reqid = ''.join(
                        ['exposeact:', str(self.bridge_id), ':', str(self.id_counter)])
                    data = {'op': 'advertise_action', 'id': reqid,
                            'action': item_tuple[1], 'type': item_tuple[2]}
                    self.exposed_actions[item_tuple[1]] = item_tuple[2]
                    if _compression is not None:
                        data['compression'] = _compression
                    await self.send(data)

                elif item_tuple[0] == 'delact':  # hide exposed action to remote gateway
                    reqid = ''.join(
                        ['delact:', str(self.bridge_id), ':', str(self.id_counter)])
                    data = {'op': 'unadvertise_action', 'id': reqid,
                            'action': item_tuple[1]}
                    await self.send(data)
                    self.exposed_actions.pop(item_tuple[1], None)

                elif item_tuple[0] == 'trpub':
                    subid = ''.join(
                        ['subscribe:', str(self.bridge_id), ':', str(self.id_counter)])
                    await self._op_subscribe(
                        {'op': 'subscribe', 'id': subid,
                         'topic': item_tuple[1], 'type': item_tuple[2],
                         'compression':  _compression}, {'remote_topic': item_tuple[5]})
                    advid = ''.join(
                        ['advertise:', str(self.bridge_id), ':', str(self.id_counter)])
                    data = {'op': 'advertise', 'id': advid,
                            'topic': item_tuple[5], 'type': item_tuple[2]}
                    # item_tuple[5] is target_topic
                    if _compression is not None:
                        data['compression'] = _compression

                    await self.send(data)
                else:
                    mlogger.debug("Unknwon command %s", item_tuple[0])
            except Exception as err:
                mlogger.debug(traceback.format_exc())
                mlogger.debug("Error in batch_cmd for '%s'", err)
                raise

    async def _execute_command(self, command_data: Dict):
        mlogger.debug("executeCommand %s", str(command_data['op']))
        op_func = self.op_map.get(command_data['op'])
        if not op_func:
            mlogger.debug("Operation %s is not supported", command_data['op'])
            return
        try:
            result = await op_func(command_data)
            if result is not None:
                await self._send_back_operation_status(command_data.get('id', '0'), result, 'none')
        except RosWsGatewayException as err:
            error_data = {
                "id": command_data.get('id', '0'),
                "op": command_data['op'], "reason": str(err)}
            await self._send_back_operation_status(
                command_data.get('id', '0'), 'error', json.dumps(error_data))

    # 221102
    def add_publish(
            self, topic_name: str, topic_type: Union[str, None],
            israw: bool = False, compression: Union[str, None] = None):
        """ add_publish """
        mlogger.debug("add_publish")
        self.batch_queue.put_nowait(
            ('pub', topic_name, topic_type, israw, compression))  # 221102

    def remove_publish(self, topic_name: str):
        """ remove_publish """
        mlogger.debug("remove_publish")
        self.batch_queue.put_nowait(('unadv', topic_name, "", None, None))

    def remove_subscribe(self, topic_name: str):
        """ remove_subscribe """
        mlogger.debug("remove_subscribe")
        self.batch_queue.put_nowait(('unsub', topic_name, "", None, None))

    def add_subscribe(
            self, topic_name: str, topic_type: Union[str, None],
            israw: bool = False, compression: Union[str, None] = None):
        """ add_subscribe """
        mlogger.debug("add_subscribe")
        self.batch_queue.put_nowait(
            ('sub', topic_name, topic_type, israw, compression))

    def expose_service(
            self, srv_name: str, srv_type: Union[str, None],
            israw: bool = False, compression: Union[str, None] = None):
        """ expose_service """
        mlogger.debug("expose_service")
        self.batch_queue.put_nowait(
            ('expsrv', srv_name, srv_type, israw, compression))

    def hide_service(self, srv_name: str):
        """ hide_service """
        mlogger.debug("hide_service")
        self.batch_queue.put_nowait(('delsrv', srv_name, "", False, None))

    def expose_action(
            self, act_name: str, act_type: Union[str, None],
            israw: bool = False, compression: Union[str, None] = None):
        """ expose_action """
        mlogger.debug("expose_action")
        self.batch_queue.put_nowait(
            ('expact', act_name, act_type, israw, compression))

    def hide_action(self, act_name: str):
        """ hide_action """
        mlogger.debug("hide_action")
        self.batch_queue.put_nowait(('delact', act_name, "", False, None))

    def get_publihsed_topics(self) -> List[str]:
        """ get publihsed topic list
        """
        return list(self.subscribed_topic.keys())

    def get_subscribed_topics(self) -> List[str]:
        """ get subscribed topic list
        """
        return list(self.published_topic.keys())

    def get_publihsed(self) -> Dict[str, Tuple[str, str]]:
        """ get publihsed topic and type dict 
                [add_publish internally trigger ROS topic subscribe]
        """
        return self.subscribed_topic

    def get_subscribed(self) -> Dict[str, Tuple[str, str]]:
        """ get subscribed topic and type dict 
                [add_subscribe internally trigger ROS topic publish]
        """
        return self.published_topic

    def get_op_subscribed(self) -> Dict[str, Tuple[str, str]]:
        """ get op subscribed topic and type dict
        """
        return self.subscribed_topic

    def get_op_publihsed(self) -> Dict[str, Tuple[str, str]]:
        """ get op subscribed topic and type dict
        """
        return self.published_topic

    # experimental
    def add_trans_publish(self,
                          local_topic: str, topic_type: Union[str, None],
                          remote_topic: str, israw: bool = False,
                          compression: Union[str, None] = None):
        """add_trans_publish
            publish local topic to remote as target_topic

        Args:
            local_topic (str): local topic_name
            topic_type (Union[str, None]): local topic type
            remote_topic (str): remote topic name
            israw (bool, optional):  Defaults to False.
            compression (Union[str, None], optional): Defaults to None.
        """
        mlogger.debug("add_trans_publish")
        self.batch_queue.put_nowait(
            ('trpub', local_topic, topic_type,
                israw, compression, remote_topic))  # 230427

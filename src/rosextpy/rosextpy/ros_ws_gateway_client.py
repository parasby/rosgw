#  MIT License
#
#  Copyright (c) 2021,
#   Electronics and Telecommunications Research Institute (ETRI) All Rights Reserved.
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

# rosextpy.ros_ws_gateway_client (ros2-ws-gateway)
# Author: ByoungYoul Song(parasby@gmail.com)
"""ros_ws_gateway_client
"""

# based on fastapi_websocket_rpc
import asyncio
import logging
# import traceback
from typing import List, Any, Union, Callable, Dict, Awaitable
from tenacity import retry, wait
import tenacity
from tenacity.retry import retry_if_exception
import websockets.client
import websockets.exceptions
from websockets.exceptions import (
    InvalidStatusCode, WebSocketException, ConnectionClosedError, ConnectionClosedOK)
from rosextpy.node_manager import NodeManager
from rosextpy.ros_ws_gateway import RosWsGateway
from rosextpy.websocket_utils import WebSocketDisconnect

mlogger = logging.getLogger('ros_ws_gateway_client')

# STOP_FLAG = False


# def set_stop(state: bool):
#     """set_stop

#     Args:
#         state (bool): set to STOP_FLAG with state arguments
#     """
#     global STOP_FLAG
#     STOP_FLAG = state


def isNotInvalidStatusCode(status: Any) -> bool:  # pylint: disable=invalid-name
    """isNotInvalidStatusCode

    Args:
        status (Any): status code

    Returns:
        bool: returns true if status is InvalidStatusCode
    """
    return not isinstance(status, InvalidStatusCode)


def isNotForbbiden(value) -> bool:  # pylint: disable=invalid-name
    """
    Returns:
        bool: Returns True 
            as long as the given exception value is not InvalidStatusCode with 401 or 403
    """
    return not (isinstance(value, InvalidStatusCode) and (value.status_code in (401, 403)))


def logerror(retry_state: tenacity.RetryCallState) -> None:
    """logerror

    Args:
        retry_state (tenacity.RetryCallState): retry_state
    """
    if retry_state.outcome is not None:
        mlogger.exception(retry_state.outcome.exception())

# import datetime


class WebSocketClientInterface:
    """WebSocketClientInterface
    """

    def __init__(self, websocket):
        self.websocket = websocket

    # @property
    async def send(self, mesg):  # WebSocketClientProtocol
        """send"""
        try:
            # return await self.websocket.send(mesg)
            # a = datetime.datetime.now()
            await self.websocket.send(mesg)
            # b = datetime.datetime.now()
            # print(f'{(b-a).microseconds/ 1000.0} ms')
        except (ConnectionClosedError, ConnectionClosedOK) as exc:
            raise WebSocketDisconnect() from exc

    @property
    def recv(self):  # WebSocketClientProtocol
        """recv"""
        return self.websocket.recv

    async def close(self, code: int = 1000):
        """close"""
        await self.websocket.close(code)  # WebSocketClientProtocol

    async def accept(self):  # WebSocketClientProtocol
        """accept"""
        mlogger.debug("accept")
        # await self.websocket.accept()
        await self.websocket.ensure_open()

    # @property
    def address(self):
        """address"""
        # self.websocket.remote_address  #WebSocketClientProtocol
        return self.websocket.remote_address


class RosWsGatewayClient:
    """
       ROS Websocket client to connect to an ROS2-web-bridge compliant service
    """

    DEFAULT_RETRY_CONFIG = {
        'wait': wait.wait_random_exponential(min=0.1, max=120),
        'retry': retry_if_exception(isNotForbbiden),
        'reraise': True,
        "retry_error_callback": logerror
    }

    WAIT_FOR_INITIAL_CONNECTION = 1

    MAX_CONNECTION_ATTEMPTS = 5

    def __init__(self, uri: str, node_manager: NodeManager,
                 retry_connect=True,
                 loop=None,
                 retry_config=None,
                 default_timeout: Union[float, None] = None,
                 on_connect: Union[Callable[["RosWsGateway"],
                                            Awaitable], None] = None,
                 on_disconnect: Union[Callable[[
                     "RosWsGateway"], Awaitable], None] = None,
                 **kwargs):
        """
        Args:
            uri (str): server uri to connect to (e.g. 'ws://localhost:2000')

            node_manager (NodeManager): ROS2 Node Manager to process ROS2 command

            retry_config (dict): 
                Tenacity.retry config 
                    (@see https://tenacity.readthedocs.io/en/latest/api.html#retry-main-api)
                     Default: False(no retry), When retry_config is None, it uses default config

            default_timeout (float): default time in seconds

            on_connect (List[Coroutine]): 
                callbacks on connection being established (each callback is called with the gateway)
                    @note exceptions thrown in on_connect callbacks propagate 
                        to the client and will cause connection restart!

            on_disconnect (List[Coroutine]): 
                callbacks on connection termination (each callback is called with the gateway)
            **kwargs: Additional args passed to connect (@see class Connect at websockets/client.py)
                      https://websockets.readthedocs.io/en/stable/api.html#websockets.client.connect
            usage:
                async with  RosWsGatewayClient(uri, node_manager) as client:
                   await client.wait_on_reader()

        """

        # ros node manager
        self.node_manager = node_manager

        if node_manager is None:
            mlogger.warning("node_manager is None")

        self.connect_kwargs = kwargs

        # Websocket connection
        self.conn = None
        # Websocket object
        self._ws = None

        # ros ws bridge uri : target gateway/bridge URI
        self.uri = uri

        # reader worker
        self._read_task = None

        # timeout
        self.default_timeout = default_timeout

        # Ros WS Gateway
        self.gateway: Union[RosWsGateway, None] = None

        # retry config for Tenacity.retry

        # if retry_config is not None else self.DEFAULT_RETRY_CONFIG
        if retry_connect is False:
            self.retry_config = None
        else:
            if retry_config is None:
                self.retry_config = self.DEFAULT_RETRY_CONFIG
            else:
                self.retry_config = retry_config

        # event handlers
        self._on_connect: Union[Callable[[
            "RosWsGateway"], Awaitable], None] = on_connect
        self._on_disconnect: Union[Callable[[
            "RosWsGateway"], Awaitable], None] = on_disconnect

        self._req_advertise_handlers: List[
            Callable[[str, str, bool, str], None]] = []
        self._req_unadvertise_handlers: List[
            Callable[[str], None]] = []
        self._req_subscribe_handlers: List[
            Callable[[str, str, bool, str], None]] = []
        self._req_unsubscribe_handlers: List[
            Callable[[str], None]] = []
        self._req_expose_service_handlers: List[
            Callable[[str, str, bool, str], None]] = []
        self._req_hide_service_handlers: List[
            Callable[[str], None]] = []
        self._req_expose_action_handlers: List[
            Callable[[str, str, bool, str], None]] = []
        self._req_hide_action_handlers: List[Callable[[str], None]] = []
        self._req_reserve_service_handlers: List[
            Callable[[str, str, bool, str], None]] = []
        self._req_cancel_rsv_service_handlers: List[
            Callable[[str], None]] = []
        self._req_reserve_action_handlers: List[
            Callable[[str, str, bool, str], None]] = []
        self._req_cancel_rsv_action_handlers: List[
            Callable[[str], None]] = []

        # event loop for multi threading event loop
        self.loop = loop if loop is not None else asyncio.get_event_loop()

    def run_operation(self, opr: str, cfg: Dict) -> bool:
        """run_operation"""
        if opr == 'publish':
            self.add_publish(cfg['name'], cfg['type'],
                             (cfg.get('israw', 'False') != 'False'),
                             cfg.get('compression', None))
        elif opr == 'subscribe':
            self.add_subscribe(cfg['name'], cfg['type'],
                               (cfg.get('israw', 'False') != 'False'),
                               cfg.get('compression', None))
        elif opr == 'expose-service':
            self.expose_service(cfg['name'], cfg['type'],
                                (cfg.get('israw', 'False') != 'False'),
                                cfg.get('compression', None))
        elif opr == 'expose-action':
            self.expose_action(cfg['name'], cfg['type'],
                               (cfg.get('israw', 'False') != 'False'),
                               cfg.get('compression', None))
        elif opr == 'reserve-service':
            self.reserve_service(cfg['name'], cfg['type'],
                                (cfg.get('israw', 'False') != 'False'),
                                cfg.get('compression', None))
        elif opr == 'reserve-action':
            self.reserve_action(cfg['name'], cfg['type'],
                               (cfg.get('israw', 'False') != 'False'),
                               cfg.get('compression', None))
        elif opr == 'trans-publish':
            self.add_trans_publish(cfg['name'], cfg['type'],
                                   cfg['remote_name'],
                                   (cfg.get('israw', 'False') != 'False'),
                                   cfg.get('compression', None))
        else:
            return False
        return True

    def register_req_advertise_handler(
            self,
            callbacks: Union[List[Callable[[str, str, bool, str], None]], None] = None):
        """
        Register a request advertise handler callback that will be called

        Args:
            callbacks (List[function]): callback
        """
        if callbacks is not None:
            self._req_advertise_handlers.extend(callbacks)

    def register_req_unadvertise_handler(
            self, callbacks: Union[List[Callable[[str], None]], None] = None):
        """
        Register a request unadvertise handler callback that will be called

        Args:
            callbacks (List[function]): callback
        """
        if callbacks is not None:
            self._req_unadvertise_handlers.extend(callbacks)

    def register_req_subscribe_handler(
            self, callbacks: Union[List[Callable[[str, str, bool, str], None]], None] = None):
        """
        Register a request subscribe handler callback that will be called

        Args:
            callbacks (List[function]): callback
        """
        if callbacks is not None:
            self._req_subscribe_handlers.extend(callbacks)

    def register_req_unsubscribe_handler(
            self, callbacks: Union[List[Callable[[str], None]], None] = None):
        """
        Register a request unsubscribe handler callback that will be called

        Args:
            callbacks (List[function]): callback
        """
        if callbacks is not None:
            self._req_unsubscribe_handlers.extend(callbacks)

    def register_req_expose_service_handler(
            self, callbacks: Union[List[Callable[[str, str, bool, str], None]], None] = None):
        """
        Register a request expose service handler callback that will be called

        Args:
            callbacks (List[function]): callback
        """
        if callbacks is not None:
            self._req_expose_service_handlers.extend(callbacks)

    def register_req_hide_service_handler(
            self, callbacks: Union[List[Callable[[str], None]], None] = None):
        """
        Register a request hide service handler callback that will be called

        Args:
            callbacks (List[function]): callback
        """
        if callbacks is not None:
            self._req_hide_service_handlers.extend(callbacks)

    def register_expose_action_handler(
            self, callbacks: Union[List[Callable[[str, str, bool, str], None]], None] = None):
        """
        Register a request expose action handler callback that will be called

        Args:
            callbacks (List[function]): callback
        """
        if callbacks is not None:
            self._req_expose_action_handlers.extend(callbacks)

    def register_req_hide_action_handler(
            self, callbacks: Union[List[Callable[[str], None]], None] = None):
        """
        Register a request hide action handler callback that will be called

        Args:
            callbacks (List[function]): callback
        """
        if callbacks is not None:
            self._req_hide_action_handlers.extend(callbacks)

    def register_reserve_action_handler(
            self, callbacks: Union[List[Callable[[str, str, bool, str], None]], None] = None):
        """
        Register a request reserve action handler callback that will be called

        Args:
            callbacks (List[function]): callback
        """
        if callbacks is not None:
            self._req_reserve_action_handlers.extend(callbacks)

    def register_cancel_rsv_action_handler(
            self, callbacks: Union[List[Callable[[str], None]], None] = None):
        """
        Register a request stop reserve action handler callback that will be called

        Args:
            callbacks (List[function]): callback
        """
        if callbacks is not None:
            self._req_cancel_rsv_action_handlers.extend(callbacks)            

    def register_reserve_service_handler(
            self, callbacks: Union[List[Callable[[str, str, bool, str], None]], None] = None):
        """
        Register a request reserve  action handler callback that will be called

        Args:
            callbacks (List[function]): callback
        """
        if callbacks is not None:
            self._req_reserve_service_handlers.extend(callbacks)

    def register_cancel_rsv_service_handler(
            self, callbacks: Union[List[Callable[[str], None]], None] = None):
        """
        Register a request stop reserve action handler callback that will be called

        Args:
            callbacks (List[function]): callback
        """
        if callbacks is not None:
            self._req_cancel_rsv_service_handlers.extend(callbacks)  

    def _on_handler_event(self, handlers, *args, **kwargs) -> None:
        for callback in handlers:
            callback(*args, **kwargs)

    def add_publish(
            self, topic_name: str, topic_type: Union[str, None],
            israw: bool = False, compression: Union[str, None] = None):
        """add_publish

        Args:
            topic_name (str): topic name
            topic_type (Union[str, None]): topic type
            israw (bool, optional): ROS topic raw mode_. Defaults to False.
            compression (Union[str, None], optional): data compression mode. Defaults to None.
        """
        mlogger.debug("add_publish %s:%s:%s:%s", topic_name,
                      topic_type, israw, compression)  # 221102
        if self.gateway:
            self.gateway.add_publish(
                topic_name, topic_type, israw, compression)  # 221102
        self._on_handler_event(self._req_advertise_handlers,
                               topic_name, topic_type, israw, compression)  # 221102

    def remove_publish(self, topic_name: str):
        """remove_publish

        Args:
            topic_name (str): topic name
        """
        mlogger.debug("remove_publish %s", topic_name)
        if self.gateway:
            self.gateway.remove_publish(topic_name)
        self._on_handler_event(self._req_unadvertise_handlers, topic_name)

    def add_subscribe(
            self, topic_name: str, topic_type: Union[str, None],
            israw: bool = False, compression: Union[str, None] = None):
        """add_subscribe

        Args:
            topic_name (str): topic name
            topic_type (Union[str, None]): topic type
            israw (bool, optional): ROS topic raw mode_. Defaults to False.
            compression (Union[str, None], optional): data compression mode. Defaults to None.
        """
        mlogger.debug("add_subscribe %s:%s:%s:%s", topic_name,
                      topic_type, israw, compression)
        if self.gateway:
            self.gateway.add_subscribe(
                topic_name, topic_type, israw, compression)
        self._on_handler_event(self._req_subscribe_handlers,
                               topic_name, topic_type, israw)

    def remove_subscribe(self, topic_name: str):
        """remove_subscribe

        Args:
            topic_name (str): topic name
        """
        mlogger.debug("remove_subscribe %s", topic_name)
        if self.gateway:
            self.gateway.remove_subscribe(topic_name)
        self._on_handler_event(self._req_unsubscribe_handlers, topic_name)

    def expose_service(
            self, srv_name: str, srv_type: Union[str, None],
            israw: bool = False, compression: Union[str, None] = None):
        """expose_service

        Args:
            srv_name (str): ROS service name
            srv_type (Union[str, None]): ROS service type
            israw (bool, optional): ROS data raw mode. Defaults to False.
            compression (Union[str, None], optional): data compression mode. Defaults to None.
        """
        mlogger.debug("expose_service %s:%s:%s:%s",
                      srv_name, srv_type, israw, compression)
        if self.gateway:
            self.gateway.expose_service(srv_name, srv_type, israw, compression)
        self._on_handler_event(
            self._req_expose_service_handlers, srv_name, srv_type, israw)

    def hide_service(self, srv_name: str):
        """hide_service

        Args:
            srv_name (str): ROS service name
        """
        mlogger.debug("hide_service %s", srv_name)
        if self.gateway:
            self.gateway.hide_service(srv_name)
        self._on_handler_event(self._req_hide_service_handlers, srv_name)

    def expose_action(
            self, act_name: str, act_type: Union[str, None],
            israw: bool = False, compression: Union[str, None] = None):
        """expose_action

        Args:
            act_name (str): ROS action name
            act_type (Union[str, None]): ROS action type
            israw (bool, optional): ROS data raw mode. Defaults to False.
            compression (Union[str, None], optional): data compression mode. Defaults to None.
        """
        mlogger.debug("expose_action %s:%s:%s:%s", act_name,
                      act_type, israw, compression)
        if self.gateway:
            self.gateway.expose_action(act_name, act_type, israw, compression)
        self._on_handler_event(
            self._req_expose_action_handlers, act_name, act_type, israw)

    def hide_action(self, act_name: str):
        """hide_action

        Args:
            act_name (str):  ROS action name
        """
        mlogger.debug("hide_action %s", act_name)
        if self.gateway:
            self.gateway.hide_action(act_name)
        self._on_handler_event(self._req_hide_action_handlers, act_name)

    async def __connect__(self):
        try:
            self._cancel_tasks()
            mlogger.debug("Connection to ros ws bridge - %s", self.uri)
            # Start connection
            self.conn = websockets.client.connect(
                self.uri, ping_interval=None, **self.connect_kwargs)
#                self.uri, **self.connect_kwargs)
            # get websocket
            self._ws = await self.conn.__aenter__()  # self.ws is WebSocketClientProtocol

            self.loop = asyncio.get_event_loop()

            self.gateway = RosWsGateway(WebSocketClientInterface(self._ws),
                                        self.node_manager, self.loop, timout=self.default_timeout)

            # register handler
            self.gateway.register_connect_handler(self._on_connect)
            self.gateway.register_disconnect_handler(self._on_disconnect)

            # start reading incoming message
            self._read_task = asyncio.create_task(self._reader())

            # trigger connect handlers
            await self.gateway.on_connect()
            return self

        except ConnectionRefusedError:
            mlogger.debug("ros ws connection was refused by server")
            raise
        except ConnectionClosedError:
            mlogger.debug("ros ws connection lost")
            raise
        except ConnectionClosedOK:
            mlogger.debug("ros ws connection closed")
            raise
        except InvalidStatusCode as err:
            mlogger.debug(
                "ros ws Websocket failed - with invalid status code %s", err.status_code)
            raise
        except WebSocketException as err:
            mlogger.debug("ros ws Websocket failed - with %s", err)
            raise
        except OSError as err:
            mlogger.debug("ros ws Connection failed - %s", err)
            raise
        except asyncio.exceptions.CancelledError as err:
            mlogger.debug("ros ws Connection cancelled - %s", err)
            raise
        except Exception as err:
            mlogger.exception("ros ws Error")
            raise

    async def __aenter__(self):
        if self.retry_config is None:
            return await self.__connect__()
        return await retry(**self.retry_config)(self.__connect__)()

    async def __aexit__(self, *args, **kwargs):
        mlogger.debug("__aexit__")
        await self.close()
        if self.conn is not None:
            if hasattr(self.conn, "ws_client"):
                await self.conn.__aexit__(*args, **kwargs)

    async def close(self):
        """close
        """
        mlogger.debug("Closing ros ws client for %s", self.uri)
        # Close underlying connection
        self._cancel_tasks()
        if self._ws is not None:
            mlogger.debug("close websocket")
            await self._ws.close()
        # Notify callbacks (but just once)
        if self.gateway is not None:
            if not self.gateway.is_closed():
                mlogger.debug("close gateway")
                # notify handlers (if any)
                await self.gateway.close()
            else:
                mlogger.debug("gateway closed")
        # Clear tasks
        # self.cancel_tasks()

    def _cancel_tasks(self):
        mlogger.debug("cancel_tasks")
        # Stop reader - if created
        self._cancel_reader_task()

    def _cancel_reader_task(self):
        mlogger.debug("cancel_reader_task")
        if self._read_task is not None:
            self._read_task.cancel()
            self._read_task = None

    async def _reader(self):
        mlogger.debug("Reading ..")
        try:
            if self._ws is not None and self.gateway is not None:
                while True:
                    raw_message = await self._ws.recv()
                    await self.gateway.on_message(raw_message)
        except asyncio.exceptions.CancelledError as exc:
            mlogger.debug("reader task was cancelled.")
            await self.close()
            raise asyncio.CancelledError() from exc
        except (websockets.exceptions.ConnectionClosedError,
                websockets.exceptions.ConnectionClosedOK) as exc:
            # closed by server
            mlogger.debug("Connection was terminated.")
            await self.close()
            raise exc
        except Exception as exc:
            mlogger.debug("ros ws reader task exception %s", type(exc))
            raise

    async def wait_on_reader(self):
        """wait_on_reader
        """
        try:
            mlogger.debug("Wait read")
            if self._read_task is not None:
                await self._read_task
        except asyncio.CancelledError:
            mlogger.debug("ros ws Reader task was cancelled.")

    async def send(self, message: Dict[str, Any], timeout: Union[float, None] = None):
        """send

        Args:
            message (_type_): _description_
            timeout (Union[float, None], optional): _description_. Defaults to None.
        """
        _ = timeout  # reserved
        if self.gateway is not None:
            await self.gateway.send(message)

    # experimental

    def add_trans_publish(  # 230427
            self, topic_name: str, topic_type: Union[str, None], remote_topic: str,
            israw: bool = False, compression: Union[str, None] = None):
        """add_publish

        Args:
            topic_name (str): local topic name
            topic_type (Union[str, None]): topic type
            remote_topic (str): remote topic name
            israw (bool, optional): ROS topic raw mode_. Defaults to False.
            compression (Union[str, None], optional): data compression mode. Defaults to None.
        """
        mlogger.debug("add_trans_publish %s:%s:%s:%s:%s", topic_name,
                      topic_type, remote_topic, israw, compression)  # 230427
        if self.gateway:
            self.gateway.add_trans_publish(
                topic_name, topic_type, remote_topic, israw, compression)  # 230427
        self._on_handler_event(self._req_advertise_handlers,
                               topic_name, topic_type, israw, compression)  # 230427
        
    # exprimental : Apr. 2024        
    def reserve_service(
            self, srv_name: str, srv_type: Union[str, None],
            israw: bool = False, compression: Union[str, None] = None):
        """reserve_service

        Args:
            srv_name (str): ROS service name
            srv_type (Union[str, None]): ROS service type
            israw (bool, optional): ROS data raw mode. Defaults to False.
            compression (Union[str, None], optional): data compression mode. Defaults to None.
        """
        mlogger.debug("reserve_service %s:%s:%s:%s",
                      srv_name, srv_type, israw, compression)
        if self.gateway:
            self.gateway.reserve_service(srv_name, srv_type, israw, compression)
        self._on_handler_event(
            self._req_reserve_service_handlers, srv_name, srv_type, israw)
        
    def cancel_reserve_service(self, srv_name: str):
        """cancel_reserve_service

        Args:
            srv_name (str): ROS service name
        """
        mlogger.debug("cancel_reserve_service %s", srv_name)
        if self.gateway:
            self.gateway.cancel_reserve_service(srv_name)
        self._on_handler_event(self._req_cancel_rsv_service_handlers, srv_name)        

    def reserve_action(
            self, act_name: str, act_type: Union[str, None],
            israw: bool = False, compression: Union[str, None] = None):
        """reserve_action

        Args:
            act_name (str): ROS action name
            act_type (Union[str, None]): ROS action type
            israw (bool, optional): ROS data raw mode. Defaults to False.
            compression (Union[str, None], optional): data compression mode. Defaults to None.
        """
        mlogger.debug("reserve_action %s:%s:%s:%s", act_name,
                      act_type, israw, compression)
        if self.gateway:
            self.gateway.reserve_action(act_name, act_type, israw, compression)
        self._on_handler_event(
            self._req_reserve_action_handlers, act_name, act_type, israw)        
        
    def cancel_reserve_action(self, act_name: str):
        """cancel_reserve_action

        Args:
            act_name (str):  ROS action name
        """
        mlogger.debug("cancel_reserve_action %s", act_name)
        if self.gateway:
            self.gateway.cancel_reserve_action(act_name)
        self._on_handler_event(self._req_cancel_rsv_action_handlers, act_name)                

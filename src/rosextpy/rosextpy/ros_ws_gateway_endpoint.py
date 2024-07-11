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

# rosextpy.ros_ws_gateway_client (ros2-ws-gateway)
# Author: ByoungYoul Song(parasby@gmail.com)
"""ros_ws_gateway_client
"""

from __future__ import absolute_import
# import datetime
import asyncio
import logging
# import traceback
from typing import Union, Any, Callable, Awaitable, Type
# from node_manager import NodeManager
from rosextpy.ros_ws_gateway import RosWsGateway
from rosextpy.node_manager import NodeManager
from rosextpy.websocket_utils import (
    ConnectionManager, WebSocketInterface, WebSocketDisconnect, register_ws_route)

mlogger = logging.getLogger('ros_ws_gateway_endpoint')


class RosWsGatewayEndpoint:
    """
       ROS Websocket Server to receive the ROS2-web-bridge compliant protocol messages
    """

    def __init__(self, node_manager: NodeManager,
                 manager: Union[ConnectionManager, None] = None,
                 on_connect_handler: Union[Callable[[
                     "RosWsGateway"], Awaitable], None] = None,
                 on_disconnect_handler: Union[Callable[["RosWsGateway"], Awaitable], None] = None):
        ###
        # Args:
        #     node_manager (NodeManager): ROS2 Node Manager to process ROS2 command
        #     loop (asyncio.loop) : event loop for running this gateway server
        #     manager ([ConnectionManager], optional):
        #         Connection tracking object. Defaults to None (i.e. new ConnectionManager()).
        #     on_disconnect (List[coroutine], optional): Callbacks per disconnection
        #     on_connect(List[coroutine], optional):
        #         Callbacks per connection
        # (Server spins the callbacks as a new task, not waiting on it.)
        #     usage:
        #        # for FastAPI
        #         app = FastAPI()
        #         endpoint = RosWsGatewayEndpoint(node_manager)
        #         endpoint.register_route(app)
        ###
        # ros node manager
        self.node_manager: NodeManager = node_manager
        # connection manager
        self.manager: ConnectionManager = manager if manager is not None else ConnectionManager()
        # event handlers
        self._on_connect_handler: Union[Callable[[
            "RosWsGateway"], Awaitable], None] = on_connect_handler
        self._on_disconnect_handler: Union[Callable[[
            "RosWsGateway"], Awaitable], None] = on_disconnect_handler
        self.stop_flag = False
        self.run_event = asyncio.Event()

    async def wait_stop(self):
        """wait_stop
        """
        self.stop_flag = True
        await self.run_event.wait()
        self.run_event.clear()

    async def serve(
            self, websocket: Any, ws_provider: Type[WebSocketInterface],
            request: Union[Any, None] = None,
            client_id: Union[str, None] = None, **kwargs) -> None:
        """serve

        Args:
            websocket (Any): websocket handle
            request (Union[Any, None], optional): Request message. Defaults to None.
            client_id (Union[str, None], optional): client id. Defaults to None.

        Raises:
            WebSocketDisconnect: _description_
        """
        mlogger.debug("serve")
        _ = client_id  # reserved
        _ = kwargs  # reserved

        the_loop = asyncio.get_event_loop()
        wshandle = ws_provider(websocket, request)

        try:
            await self.manager.accept(wshandle)  # FastAPI Webdsocket Only
            mlogger.debug("Server URL is %s, Client Connected from %s",
                          wshandle.url, wshandle.address)

            gateway = RosWsGateway(wshandle, self.node_manager, the_loop)

            gateway.register_connect_handler(self._on_connect_handler)
            gateway.register_disconnect_handler(self._on_disconnect_handler)
            await gateway.on_connect()
            try:
                while self.stop_flag is not True:
                    data = await wshandle.recv()
                    if not data:
                        raise WebSocketDisconnect
                    # a = datetime.datetime.now()
                    await gateway.on_message(data)
                    # b = datetime.datetime.now()
                    # print(f'{(b-a).microseconds/ 1000.0} ms for {len(data)/1000}kb')

                await gateway.close()
            except WebSocketDisconnect:
                mlogger.debug("Client disconnected - %s :: %s",
                              wshandle.address, gateway.bridge_id)
                await self._handle_disconnect(wshandle, gateway)
            except asyncio.exceptions.CancelledError:
                mlogger.debug("Client disconnected - %s :: %s",
                              wshandle.address, gateway.bridge_id)
                await self._handle_disconnect(wshandle, gateway)
            except Exception as exc:
                mlogger.error("exception occured %s", exc)
                mlogger.error("Client failed - %s :: %s",
                              wshandle.address, gateway.bridge_id)
                #await wshandle.send(str(exc)) ## for debug
                await self._handle_disconnect(wshandle, gateway)
        except Exception as excc:
            mlogger.debug("exception occured %s", type(excc))
            mlogger.error("Failed to serve %s", wshandle.address)
            self.manager.disconnect(wshandle)
        finally:
            mlogger.debug("gateway endpoint closed")
            self.run_event.set()

    async def _handle_disconnect(self, wshandle: WebSocketInterface, gateway: RosWsGateway):
        mlogger.debug("handle_disconnect")
        self.manager.disconnect(wshandle)
        await gateway.close()

    # function for fastapi endpoint

    def register_route(self, router: Any, path: str = "/"):
        """register_route

        Args:
            router (Any): router object
            path (str, optional): route path string. Defaults to "/".
        """
        register_ws_route(self, router, path)

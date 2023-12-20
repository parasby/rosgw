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

# rosextpy.websocket_utils (ros2-ws-gateway)
# Author: parasby@gmail.com

"""websocket_util
"""
import logging
import json
from typing import Any, Union
import traceback
from .mod_config import WS_CONFIG

mlogger = logging.getLogger('websocket_utils')


class WebSocketDisconnect(Exception):
    """WebSocketDisconnect    
    """

    def __init__(self, msg=""):
        super().__init__("websocket disconnected :"+msg)


class ConnectionManager:
    """ConnectionManager
    """

    def __init__(self):
        self.connections = []

    async def accept(self, websocekt: Any):
        """accept

        Args:
            websocekt (Any): websocket handle
        """
        await websocekt.accept()
        self.connections.append(websocekt)
#        print([s.address for s in self.connections])

    def disconnect(self, websocekt: Any):
        """disconnect

        Args:
            websocekt (Any): websocket handle
        """
        self.connections.remove(websocekt)


# config for fastapi
# from fastapi import WebSocket, WebSocketDisconnect

def register_ws_route(cls, router: Any, path: str):
    """register_ws_route"""
    @router.websocket(path)
    async def websocket_endpoint(websocket):
        await cls.serve(websocket)


class WebSocketInterface:
    """WebSocketInterface"""

    def __init__(self, websocket, request):
        self.websocket = websocket
        self.request = request

    async def send(self, mesg: Union[bytes, str]):
        """send

        Args:
            mesg (Union[bytes, str]): send message on websocket
        """
        _ = mesg
        mlogger.error("not implemented")

    # @property
    async def recv(self) -> Union[str, bytes, None]:
        """recv

        Returns:
            Union[str, bytes, None]: receive data
        """
        mlogger.error("not implemented")
        return None

    async def close(self, code: int = 1000):
        """close"""
        _ = code
        mlogger.error("not implemented")

    # @property

    async def accept(self):
        """accept"""
        mlogger.error("not implemented")
        return None

    @property
    def address(self):
        """address"""
        mlogger.error("not implemented")
        return ""

    @property
    def url(self):
        """url"""
        mlogger.error("not implemented")
        return ""


class WebSocketInterfaceSanicAPI(WebSocketInterface):
    """WebSocketInterface
    """

    def __init__(self, websocket, request):
        super().__init__(websocket=websocket, request=request)
        # self.websocket = websocket
        # self.request = request
        mlogger.debug("websocket is %s ", type(websocket))
        mlogger.debug("Mod config is %s", WS_CONFIG['wsf'])

    # @property
    # def send(self):
    async def send(self, mesg: Union[bytes, str]):
        """send

        Args:
            mesg (Union[bytes, str]): send message on websocket
        """
        await self.websocket.send(mesg)
    # @property

    async def recv(self) -> Union[str, bytes, None]:
        """recv

        Returns:
            Union[str, bytes, None]: receive data
        """
        return await self.websocket.recv()

    async def close(self, code: int = 1000):
        """close"""
        await self.websocket.close(code)

    # @property
    async def accept(self):
        """accept"""
        return None

    @property
    def address(self):
        """address"""
        return f"{self.request.ip}:{self.request.port}"   # FastAPI Webdsocket Only"

    @property
    def url(self):
        """url"""
        return self.request.url

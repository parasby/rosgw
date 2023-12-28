#  MIT License
#
#  Copyright (c) 2021, Electronics and Telecommunications Research Institute
#   (ETRI) All Rights Reserved.
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

# rosextpy.ros_gateway_agent (ros-ws-gateway)
# Author: parasby@gmail.com
"""ros_gateway_agent
"""
import os
import logging, logging.handlers
import asyncio
import socket
import argparse
from typing import List, Dict, Any
from pydantic import BaseModel, Field   # pylint: disable=no-name-in-module
# from pydantic.utils import deep_update
from sanic import Sanic, Request, Websocket
from sanic.response import json, JSONResponse, text
from sanic.exceptions import (SanicException)
from sanic_cors import CORS
from sanic_ext import openapi, validate

try:
    from ujson import load as json_loadf  # type: ignore
except ImportError:
    from json import load as json_loadf  # type: ignore

# must import configuration module before any other sub modules
from rosextpy.ros_gateway_agent import RosWsGatewayAgent   # pylint: disable=no-name-in-module, import-error
from rosextpy.websocket_utils import (WebSocketInterfaceSanicAPI)


mlogger = logging.getLogger(__name__)


class GatewayAddresses(BaseModel):
    ''' GatewayAddresses '''
    address: List[str] = Field(
        example=['ws://localhost:9000', 'ws://localhost:8000'])


class TopicList(BaseModel):
    """TopicList"""
    topics: List[str] = Field(
        example=["/my_topic", "/some_topic"])


class GatewayRequestResult(BaseModel):
    """GatewayRequestResult"""
    result: str


class GatewayPublishRule(BaseModel):
    ''' GatewayPublishRule '''
    address: str = Field("", example="ws://localhost:9000")
    publish: List[Dict[str, str]] = \
        Field("[]",
              example=[{"name": "/my_topic",
                        "messageType": "std_msgs/msg/String", "compression": "cbor-raw"}])


class GatewayTransPublishRule(BaseModel):
    ''' GatewayTransPublishRule '''
    address: str = Field("", example="ws://localhost:9000")
    publish: List[Dict[str, str]] = \
        Field("[]",
              example=[{"name": "/my_topic",
                        "messageType": "std_msgs/msg/String",
                        "remote_name": "/remote_topic",
                        "compression": "cbor-raw"}])


class GatewaySubscribeRule(BaseModel):
    ''' GatewaySubscribeRule '''
    address: str = Field("", example="ws://localhost:9000")
    subscribe: List[Dict[str, str]] = \
        Field("[]",
              example=[{"name": "/my_topic",
                        "messageType": "std_msgs/msg/String", "israw": False}])


class GatewayServiceRule(BaseModel):
    ''' GatewayServiceRule '''
    address: str = Field("", example="ws://localhost:9000")
    service: List[Dict[str, str]] = \
        Field("[]",
              example=[{"service": "add_two_ints",
                        "serviceType": "srv_tester_if.srv.AddTwoInts",
                        "israw": False}])


class GatewayActionRule(BaseModel):
    ''' GatewayActionRule '''
    address: str = Field("", example="ws://localhost:9000")
    action: List[Dict[str, str]] = \
        Field("[]",
              example=[{"action": "fibonacci",
                        "actionType": "action_tester_if.action.Fibonacci",
                        "israw": False}])


class GatewayRule(BaseModel):
    ''' GatewayRule '''
    address: str
    publish: List[Dict[str, str]] = []
    subscribe: List[Dict[str, str]] = []
    service: List[Dict[str, str]] = []
    action: List[Dict[str, str]] = []


class ROSRESTRule(BaseModel):
    """ROSRESTRule"""
    service_name: str
    service_uri: str
    service_method: str
    request_rule: Dict[str, Any] = {}
    response_rule: Dict[str, Any] = {}


class ROSRESTStopRule(BaseModel):
    ''' ROSRESTStopRule '''
    id: str


app = Sanic("rosgw")
CORS(app)
app.config.WEBSOCKET_MAX_SIZE = 2 ** 24
app.config.WEBSOCKET_PING_INTERVAL = 20  # None
app.config.WEBSOCKET_PING_TIMEOUT = 20  # 200
# app.config.RESPONSE_TIMEOUT =200
# app.config.KEEP_ALIVE_TIMEOUT = 200
app.config.OAS_UI_DEFAULT = "swagger"

parser = argparse.ArgumentParser()
parser.add_argument("-p", "--port", type=int,
                    default=9000,
                    help="Listen port, default to :9000")
parser.add_argument("-f", "--file",
                    help="config file name")
parser.add_argument("-n", "--name", help="gateway namespace")
parser.add_argument("-r", "--rlog", help="rsyslog address ex: ipaddress:port") #, default="172.28.165.227:51400")
parser.add_argument("-l", "--loglevel",
                    default="warning",
                    help="Provide logging level. Example --loglevel debug, default=warning")
OPTIONS = parser.parse_args()  # type: ignore
OPTIONS.name = socket.gethostbyname(socket.gethostname()) if OPTIONS.name is None else OPTIONS.name

#logging.basicConfig(level=OPTIONS.loglevel.upper())
#FORMAT= '%(asctime)s [rosgw:'+OPTIONS.name+':%(name)-14s:%(lineno)-5d] %(levelname)-6s %(message)s'
FORMAT= '%(asctime)s '+OPTIONS.name+' rosgw - - - [%(name)-14s:%(lineno)-5d] %(levelname)-6s %(message)s'
if OPTIONS.rlog is not None:    
    rlogaddr, rlogport = OPTIONS.rlog.split(':')
    #print(rlogaddr, '...', rlogport)
    handler = logging.handlers.SysLogHandler(address=(rlogaddr, int(rlogport)), facility=19)
    logging.basicConfig(handlers=[handler],level=OPTIONS.loglevel.upper(),
        format=FORMAT, datefmt='%Y-%m-%dT%H:%M:%S%z')
else:
    logging.basicConfig(level=OPTIONS.loglevel.upper(), format=FORMAT, datefmt='%Y-%m-%dT%H:%M:%S%z')

#FORMAT= '[%(created)f][rosgw:'+OPTIONS.name+'] %(levelname)-6s %(name)s [%(filename)s:%(lineno)d] %(message)s'
#FORMAT= '[%(asctime)s][rosgw:'+OPTIONS.name+':%(name)s.%(funcName)s:%(lineno)d] %(levelname)-6s %(message)s'
#logging.basicConfig(level=logging.DEBUG)
MONITOR = None

AGENT = RosWsGatewayAgent(loop=asyncio.get_event_loop(), namespace=OPTIONS.name)


class TaskManager:
    """TaskManager
    """

    def __init__(self, manager):

        self.handle = manager

    def submit(self, name: str, proc: Any, params: dict):
        """submit"""
        self.handle.manage(name, proc, params)


@app.main_process_ready
async def ready(app: Sanic, __):
    try:
        AGENT.ready(task_manager=TaskManager(app.manager))
        if OPTIONS.file:
            with open(OPTIONS.file, encoding='UTF-8') as json_file:
                configs = json_loadf(json_file)
                AGENT.apply_configs(configs)
    except Exception as err:
        mlogger.error(err)


@app.signal("server.init.before")  # server.init.before
async def task_start(**context):
    ''' task_start '''
    _ = context
    mlogger.debug("Command option is %s", OPTIONS)

    await AGENT.start()
    # if OPTIONS.file:
    #     with open(OPTIONS.file, encoding='UTF-8') as json_file:
    #         configs = json_loadf(json_file)
    #         AGENT.apply_configs(configs)


@app.signal("server.shutdown.before")  # server.shutdown.after
async def task_stop(**context):
    ''' task_stop '''
    _ = context
    await AGENT.close()  # type: ignore
    print("Server stopped OK")

# Agent Information API


@app.get('/topic')
@openapi.definition(
    summary="Get topic lists being published ",
    description="request to get topic lists being distributed "
)
@openapi.response(200,
                  {"application/json": TopicList},
                  "topic lists being published"
                  )
async def get_topic_list(request: Request) -> JSONResponse:
    ''' get_topic_list '''
    _ = request
    topic_list = AGENT.api_get_topic_list()  # type: ignore
    return json(topic_list)


#@app.get('/gateway')
@openapi.definition(
    summary="Get gateway lists",
    description="request to get gateway lists to be configured to connect "
)
@openapi.response(200,
                  {"application/json": GatewayAddresses},
                  "gateway lists to connect"
                  )
async def get_gateway_list(request: Request) -> JSONResponse:
    ''' get_gateway_list '''
    _ = request
    gw_list = AGENT.api_get_gw_list()  # type: ignore
    return json(gw_list)


#@app.post('/gateway/get/config')
@openapi.definition(
    summary="Get gateway configs",
    description="get configs requested by addresses")
@openapi.body({"application/json": GatewayAddresses})
@openapi.response(200,
                  {"application/json": GatewayRule},
                  "gateway configs")
@validate(json=GatewayAddresses)
async def get_gateway_config(_, body: GatewayAddresses) -> JSONResponse:
    """get_gateway_config"""
    results = AGENT.api_get_config(body.address)  # type: ignore
    return json(results)

# Topic Publish


#@app.post('/gateway/publisher/add')
@openapi.definition(
    summary="Add publish rule to the gateway",
    description="request to add publish rules to the gateway",
    body={'application/json': GatewayPublishRule}
)
@openapi.body({"application/json": GatewayPublishRule})
@openapi.response("default",
                  {"application/json": GatewayRequestResult},
                  "result of publisher add requst")
@validate(json=GatewayPublishRule)
async def publisher_add(_, body: GatewayPublishRule) -> JSONResponse:
    """publisher_add"""
    results = AGENT.api_publisher_add(body.address,
                                      body.publish)  # type: ignore
    return json({"result": results})


#@app.put('/gateway/publisher/remove')
@openapi.definition(
    body={"application/json": GatewayPublishRule},
    summary="Remove Forwarding(publish) from gateway",
    description="request to remove subscribe rules from the gateway"
)
@openapi.response("default",
                  {"application/json": GatewayRequestResult},
                  "result of publisher remove requst")
@validate(json=GatewayPublishRule)
async def publisher_remove(_, body: GatewayPublishRule) -> JSONResponse:
    """publisher_remove"""
    results = AGENT.api_publisher_remove(  # type: ignore
        body.address, body.publish)  # type: ignore
    if results != "ok":
        return json({"result": results}, 404)
    return json({"result": results})


#@app.post('/gateway/subscriber/add')
@openapi.definition(
    body={"application/json": GatewaySubscribeRule},
    summary="Add subscribe rule to the gateway",
    description="request to add subscribe rules to the gateway ")
@openapi.response("default",
                  {"application/json": GatewayRequestResult},
                  "operation result")
@validate(json=GatewaySubscribeRule)
async def subscriber_add(_, body: GatewaySubscribeRule) -> JSONResponse:
    """subscriber_add"""
    results = AGENT.api_subscriber_add(  # type: ignore
        body.address, body.subscribe)  # type: ignore
    return json({"result": results})


#@app.put('/gateway/subscriber/remove')
@openapi.definition(
    body={"application/json": GatewaySubscribeRule},
    summary="Remove subscriptions from gateway",
    description="request to remove subscribe rules from the gateway")
@openapi.response("default",
                  {"application/json": GatewayRequestResult},
                  "result of remove request")
@validate(json=GatewaySubscribeRule)
async def subscriber_remove(_, body: GatewaySubscribeRule) -> JSONResponse:
    """subscriber_remove"""
    results = AGENT.api_subscriber_remove(  # type: ignore
        body.address, body.subscribe)  # type: ignore
    return json({"result": results})


# ROS SRV

#@app.post('/gateway/service/expose')
@openapi.definition(
    body={"application/json": GatewayServiceRule},
    summary="Add expose service rule to the gateway",
    description="request to add expose service rules to the gateway ")
@openapi.response("default",
                  {"application/json": GatewayRequestResult},
                  "operation result")
@validate(json=GatewayServiceRule)
async def service_expose(_, body: GatewayServiceRule) -> JSONResponse:
    """service_expose"""
    results = AGENT.api_service_expose(  # type: ignore
        body.address, body.service)  # type: ignore
    return json({"result": results})


#@app.put('/gateway/service/hide')
@openapi.definition(
    body={"application/json": GatewayServiceRule},
    summary="Hide exposed service from remote gateway",
    description="request to hide exposed service to the gateway")
@openapi.response("default",
                  {"application/json": GatewayRequestResult},
                  "operation result")
@validate(json=GatewayServiceRule)
async def service_hide(_, body: GatewayServiceRule) -> JSONResponse:
    """service_hide"""
    results = AGENT.api_service_hide(  # type: ignore
        body.address, body.service)  # type: ignore
    return json({"result": results})

# ROS ACTION


#@app.post('/gateway/action/expose')
@openapi.definition(
    body={"application/json": GatewayActionRule},
    summary="Add expose action rule to the gateway",
    description="request to add expose action rules to the gateway ")
@openapi.response("default",
                  {"application/json": GatewayRequestResult},
                  "operation result")
@validate(json=GatewayActionRule)
async def action_expose(_, body: GatewayActionRule) -> JSONResponse:
    """action_expose"""
    results = AGENT.api_action_expose(  # type: ignore
        body.address, body.action)  # type: ignore
    return json({"result": results})


#@app.put('/gateway/action/hide')
@openapi.definition(
    body={"application/json": GatewayActionRule},
    summary="Hide exposed action from remote gateway",
    description="request to hide exposed action to the gateway")
@openapi.response("default",
                  {"application/json": GatewayRequestResult},
                  "operation result")
@validate(json=GatewayActionRule)
async def action_hide(_, body: GatewayActionRule) -> JSONResponse:
    """action_hide"""
    results = AGENT.api_action_hide(body.address, body.action)
    return json({"result": results})

# trans pub/sub


#@app.post('/gateway/transpub/add')
@openapi.definition(
    summary="Add trans-publish rule to the gateway",
    description="request to add trans-publish rules to the gateway",
    body={'application/json': GatewayTransPublishRule}
)
@openapi.body({"application/json": GatewayTransPublishRule})
@openapi.response("default",
                  {"application/json": GatewayRequestResult},
                  "result of publisher add requst")
@validate(json=GatewayTransPublishRule)
async def trans_publisher_add(_, body: GatewayTransPublishRule) -> JSONResponse:
    """publisher_add"""
    results = AGENT.api_trans_publisher_add(body.address,
                                            body.publish)  # type: ignore
    return json({"result": results})


# ros-rest
############


#@app.post('/gateway/rosrest/add')
@openapi.definition(
    body={"application/json": ROSRESTRule},
    summary="Add ROS-REST Mapping",
    description="add ROS-REST mapping")
@openapi.response("default",
                  {"application/json": GatewayRequestResult},
                  "operation result")
@validate(json=ROSRESTRule)
async def rosrest_add(req: Request, body: ROSRESTRule) -> JSONResponse:
    """rosrest_add"""
    _ = req
    results = AGENT.api_rosrest_add(body)  # type: ignore
    return json({"result": results})

# ros-rest lists
############


#@app.get('/gateway/rosrest/lists')
@openapi.definition(
    summary="get ROS-REST Mapping lists",
    description="get ROS-REST Mapping lists")
# @openapi.response("default",
#                   {"application/json": },
#                   "operation result")
async def rosrest_lists(request: Request) -> JSONResponse:
    """rosrest_lists"""
    _ = request
    results = AGENT.api_rosrest_lists()  # type: ignore
    return json(results)

# ros-rest stop
############


#@app.put('/gateway/rosrest/stop')
@openapi.definition(
    summary="Stop ROS-REST mapping process",
    description="Stop ROS-REST mapping process")
@openapi.response("default",
                  {"application/json": GatewayRequestResult},
                  "operation result")
@openapi.body({"application/json": ROSRESTStopRule})
@openapi.response("default",
                  {"application/json": GatewayRequestResult},
                  "operation result")
async def rosrest_stop(request: Request) -> JSONResponse:
    """rosrest_stop"""
    results = AGENT.api_rosrest_stop(request.json['id'])  # type: ignore
    if results != "ok":
        return json({'results': results}, status=404)
    return json({'results': results})


# sanic websocket
@app.websocket("/")
async def ros_ws_endpoint(request: Request, wshandle: Websocket):
    """ros_ws_endpoint"""
    _ = request
    await AGENT.serve(websocket=wshandle,  # type: ignore
                      ws_provider=WebSocketInterfaceSanicAPI,
                      request=request)


@app.exception(SanicException)
async def exception_handler(request, _exception: SanicException):
    """exception_handler"""
    _ = _exception
    return text(f"Error occured {request.url}")


if __name__ == '__main__':
    # , single_process = True) #, single_process=True, debug=True)
    # app.run(host="0.0.0.0", port=OPTIONS.port, motd=False)
    app.run(host="0.0.0.0", port=OPTIONS.port, motd=False, workers=10) # performance eval
    # single_process=True) # debug=True)

#  MIT License
#
#  Copyright (c) 2021,
#    Electronics and Telecommunications Research Institute (ETRI) All Rights Reserved.
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

# rosextpy.ros_rpc_gateway_client (ros-ws-gateway)
# Author: (ByoungYoul Song)paraby@gmail.com
"""ros_rest_gateway
"""
import logging
import uuid
import json
import traceback
# from typing import List, Dict
import io
import functools
from collections import deque
from asyncio import Future
from typing import List, Dict, Any
import pybase64
from PIL import Image as PILImage
# must import configuration module before any other sub modules
from rosextpy.ros_rpc_utils import (
    set_obj_with_path, process_header_rule, replace_env_in_string, get_obj_with_path)
from rosextpy.node_manager import NodeManager
from rosextpy.ext_type_support import (
    get_ros_value, set_ros_value)

mlogger = logging.getLogger('ros_rpc_gateway_client')
#logging.basicConfig(level=logging.DEBUG)

# pylint: disable=broad-exception-caught
# pylint: disable=too-many-arguments
# pylint: disable=too-many-instance-attributes


class ROSRPCGatewayException(Exception):
    """ROSRPCGatewayException """

    def __init__(self, msg: str = ""):
        super().__init__("ROSRPCGatewayException :"+msg)


def topic_to_json(topics: Dict[str, Any], mapping: List[Dict[str, str]]):
    """topic_to_json"""
    body = {}
    for rule in list(mapping):
        if rule['in'].startswith('#'):  # special char
            if rule['in'] == '#const':
                outstr = replace_env_in_string(rule['from'])
                body = set_obj_with_path(body, rule['to'], outstr)
            else:
                raise ROSRPCGatewayException(rule['in'])

        elif rule['in'] in topics.keys():
            if rule['out'] == '#body':  # body means json
                # print('topics ', topics[rule['in']])
                body = set_obj_with_path(body,
                                         rule['to'],
                                         get_ros_value(topics[rule['in']], rule['from']))
    return body


class RosRPCGatewayClient():
    """RosRPCGatewayClient
    """

    def __init__(self, node_mgr, rpc_mgr, service_uri, service_method, request_rule, response_rule):
        self.node_manager: NodeManager = node_mgr
        self.rpc_manager = rpc_mgr
        self.service_uri = service_uri  # target service URI
        self.service_method = service_method  # default POST
        self.request_rule = request_rule    # json['request']
        self.response_rule = response_rule
        self.subscribers = {}   # {topic, handler} dict
        self.publishers = {}  # {topic, handler} dict
        self.gwid = uuid.uuid4().hex  # hex form "xxxxxxxx...xxx"
        self.close_flag = Future()
        self._init()


    def _init(self):
        mlogger.debug("_init  ")
        for topic, topic_type in self.request_rule['topics'].items():
            self.subscribers[topic] = self.node_manager.create_subscription(
                topic_type, topic, self.gwid,
                functools.partial(
                    self._ros_subscription_callback, compression=None))

        for topic, topic_type in self.response_rule['topics'].items():
            self.publishers[topic] = self.node_manager.create_publisher(
                topic_type, topic, self.gwid)

    async def wait_for_close(self):
        """wait_for_close"""
        await self.close_flag

    def close(self):
        """close
        """        
        for topics in list(self.publishers.keys()):
            self.node_manager.destroy_publisher(topics, self.gwid)
        for topics in list(self.subscribers.keys()):
            self.node_manager.destroy_subscription(topics, self.gwid)
        self.close_flag.set_result(True)
        self.close_flag.done()

    def reset(self, request_rule, response_rule):
        """reset

        Args:
            request_rule (_type_): _description_
            response_rule (_type_): _description_
        """
        self.close()
        self.request_rule = request_rule
        self.response_rule = response_rule
        self._init()

    def _ros_subscription_callback(self, topic_name, mesg, compression):
        mlogger.debug("_ros_subscription_callback  %s", topic_name)
        outctx = {}
        response = None
        _ = compression  # reserved

        headers = process_header_rule(self.request_rule.get('content-type'),
                                      self.request_rule.get('headers'))

        if self.request_rule['content-type'] == 'application/json':
            data = self.make_json_request(topic_name, mesg)
            if data:
                # response = requests.post(self.service_uri, data=json.dumps(data))
                response = self.rpc_manager.call(self.service_uri, self.service_method,
                                                 headers=headers, data=json.dumps(data))
                #print("RES IS !!", response.text)
        elif self.request_rule['content-type'] == 'multipart/form-data':
            files = self.make_file_request(topic_name, mesg)
            if files:
                # response = requests.post(self.service_uri, files=files)
                response = self.rpc_manager.call(self.service_uri, self.service_method,
                                                 headers=headers, files=files)
        if response is not None:  
            #print("response is !!!!!!!!!!!!!!!!!!!!!! \n", response)         
            try: 
                outctx.update(self.response_to_mesg(response, req_ctx={topic_name: mesg}))
            except Exception:
                mlogger.debug(traceback.format_exc())

        # else:
        #     print("response is None!!")

        #mlogger.debug(f"outctx is {outctx}")

        for i_key, i_msg in outctx.items():
            mlogger.debug(" PUB !!! Topic [%s] ", i_key)
            self.publishers[i_key].publish(i_msg)

    def make_file_request(self, topic_name, mesg):
        """make_file_request"""
        topic_type = self.request_rule['topics'].get(topic_name)

        if topic_type == 'sensor_msgs/msg/CompressedImage':
            # files = { self.mapping.properties[0]['name'] : mesg.data}
            for rule in list(self.request_rule['mapping']):
                if rule['in'] == topic_name:
                    if rule['out'] == '#files':
                        if len(rule['to']) == 0:
                            return {"file": mesg.data}
                        return {rule['to']: mesg.data}

        elif topic_type == 'sensor_msgs/msg/Image':
            _img = None
            if mesg.encoding == 'rgb8':
                _img = PILImage.frombytes(
                    'RGB', (mesg.width, mesg.height), mesg.data)
            elif mesg.encoding == 'mono8':
                _img = PILImage.frombytes(
                    'L', (mesg.width, mesg.height), mesg.data)

            if _img:
                outdata = io.BytesIO()
                _img.save(outdata, format='jpeg')
                for rule in list(self.request_rule['mapping']):
                    if rule['in'] == topic_name:
                        if rule['out'] == '#files':
                            if len(rule['to']) == 0:
                                return {"file": outdata.getvalue()}
                            return {rule['to']: outdata.getvalue()}

        else:
            mlogger.debug("cannot make file request for [%s]", topic_type)

        return None

    def make_json_request(self, topic_name, mesg):
        """make_json_request:make REST service request body  """
        # check topic type :At present, it does not make JSON for Image type topic.

        topic_type = self.request_rule['topics'].get(topic_name)

        if topic_type == 'sensor_msgs/msg/CompressedImage':
            for rule in list(self.request_rule['mapping']):
                if rule['in'] == topic_name:
                    if rule['out'] == '#body':
                        return {rule['to']: pybase64.b64encode(mesg.data.tobytes()).decode()}

        if topic_type == 'sensor_msgs/msg/Image':
            _img = None
            if mesg.encoding == 'rgb8':
                _img = PILImage.frombytes(
                    'RGB', (mesg.width, mesg.height), mesg.data)
            elif mesg.encoding == 'mono8':
                _img = PILImage.frombytes(
                    'L', (mesg.width, mesg.height), mesg.data)

            if _img:
                outdata = io.BytesIO()
                _img.save(outdata, format='jpeg')
                for rule in list(self.request_rule['mapping']):
                    if rule['in'] == topic_name:
                        if rule['out'] == 'files':
                            return {rule['to']: pybase64.b64encode(outdata.getvalue()).decode()}

        # Image types cannot be converted to JSON
        # if topicType in self.no_json_list:
        #     mlogger.error('type %s cannot be encoded to json', topicType)
        #     return None

        body = topic_to_json(topics={topic_name: mesg},
                             mapping=self.request_rule['mapping'])

        return body

    # outctx = {topicName: ros_obj}
    def _map_resp_to_mesg(self, mapping, req_ctx) -> Dict:
        """_map_resp_to_mesg: map REST json response to ROS message"""
        mlogger.debug("_map_resp_to_mesg")
        # validate context chain
        _v_ctx=[]

        for _irule in list(mapping):
            if _irule['out'] == "#context.json":
                _v_ctx.append( _irule['to'])

        for _irule in list(mapping):
            if _irule['in'] == "#context.json":
                if _irule['from'] not in _v_ctx:                    
                    raise ROSRPCGatewayException("illegal context mapping")

        outmsgs = {}
        rule_q = deque()
        rule_q.extendleft(list(mapping))

        while len(rule_q) != 0:
            #print("len is rule ", len(rule_q))
            _rule = rule_q.pop()
            if _rule['in'] not in ['#const','#body','#context.json'] and req_ctx.get(_rule['in']) is None:
                #print("Raise ERROIR !!!")
                raise ROSRPCGatewayException(f"illegal mapping  {_rule['in']}")

            if _rule['out'] == '#context.json':
                if req_ctx.get('#context.json') is None:
                    req_ctx['#context.json'] = {}

                if _rule['in'] == "#context.json":
                    if req_ctx['#context.json'].get(_rule['from']) is None:
                        rule_q.appendleft(_rule)
                    else:
                        value = req_ctx['#context.json'][_rule['from']]
                        req_ctx['#context.json'][_rule['to']] = value
                elif _rule['in'] == '#const':
                    value = replace_env_in_string(_rule['from'])
                    req_ctx['#context.json'][_rule['to']] = json.loads(value)
                elif _rule['in'] == '#body':
                    value = get_obj_with_path(req_ctx.get('#body'), _rule['from'])                    
                    req_ctx['#context.json'][_rule['to']] = json.loads(value)
            else:
                t_obj = outmsgs.get(_rule['out'])

                if t_obj is None:  # make target ROS object
                    _pub = self.publishers.get(_rule['out'])
                    if _pub is None:
                        raise ROSRPCGatewayException(f"unknown topic  {_rule['out']}")
                    t_obj = _pub.get_class_obj()
                    outmsgs[_rule['out']] = t_obj

                if _rule['in'] == "#context.json":
                    if req_ctx.get('#context.json') is None:
                        req_ctx['#context.json'] = {}

                    if req_ctx['#context.json'].get(_rule['from']) is None:
                        rule_q.appendleft(_rule)
                    else:
                        value = req_ctx['#context.json'][_rule['from']]
                        if _rule['to'] == '#value':
                            set_ros_value(t_obj, "", value)
                        else:
                            set_ros_value(t_obj, _rule['to'], value)
                elif _rule['in'] == '#const':
                    value = replace_env_in_string(_rule['from'])
                    if _rule['to'] == '#value':
                        set_ros_value(t_obj, "", value)
                    else:
                        set_ros_value(t_obj, _rule['to'], value)
                elif _rule['in'] == '#body':
                    value = get_obj_with_path(req_ctx.get('#body'), _rule['from'])
                    if _rule['to'] == '#value':
                        set_ros_value(t_obj, "", value)
                    else:
                        set_ros_value(t_obj, _rule['to'], value)
                else:
                    value = get_ros_value(req_ctx.get(_rule['in']), _rule['from'])
                    if _rule['to'] == '#value':
                        set_ros_value(t_obj, "", value)
                    else:
                        set_ros_value(t_obj, _rule['to'], value)



        # for rule in list(mapping):
        #     if rule['in'] != '#const' and req_ctx.get(rule['in']) is None:
        #         raise ROSRPCGatewayException("illegal mapping")

        #     t_obj = outmsgs.get(rule['out'])

        #     if t_obj is None:  # make target ROS object
        #         t_obj = self.publishers[rule['out']].get_class_obj()
        #         outmsgs[rule['out']] = t_obj

        #     if rule['in'] == '#const':
        #         value = replace_env_in_string(rule['from'])
        #         set_ros_value(t_obj, rule['to'], value)
        #     elif rule['in'] == '#body':
        #         value = get_obj_with_path(req_ctx.get('#body'), rule['from'])
        #         set_ros_value(t_obj, rule['to'], value)
        #     else:  # rule['in'] is  ros topic
        #         value = get_ros_value(req_ctx.get(rule['in']), rule['from'])
        #         set_ros_value(t_obj, rule['to'], value)

        return outmsgs

    # req_ctx = {subscribed topic name : subscribed ros message object}
    def response_to_mesg(self, resp, req_ctx):
        """response_to_mesg :  
            make ros message from REST response (when status==200 OK)
            Args:
                resp: response from python 'requests' call
                req_ctx: { resource_name : resource_object} : 
                    req_ctx can be request object
        """
        outmsgs = {}
        content_type = resp.headers['content-type'].split('/')
        expected_type = self.response_rule['content-type'].split('/')
        if content_type[0] != expected_type[0]:
            mlogger.warning('Response type [%s] is not matched to expected type [%s]',
                          resp.headers['content-type'], self.response_rule['content-type'])
            return outmsgs

        if content_type[0] == 'application':
            # json to ros message
            if content_type[1] == 'json':
                resp_json = resp.json()
                #print("RESP JSON is \n")
                #print(resp_json)
                req_ctx["#body"] = resp_json
                # req_ctx has request topic and response body
                outmsgs.update(self._map_resp_to_mesg(
                    self.response_rule['mapping'], req_ctx))                
            else:
                mlogger.warning(
                    "Not Supported Yet for content-type [%s]", resp.headers['content-type'])

        elif content_type[0] == 'image':  # file type response image/jpeg, jpg, jpe
            # image to ros Image or CompressedImage
            outtopic = list(self.response_rule['topics'].keys())[0]
            outtype = list(self.response_rule['topics'].values())[0]
            if outtype == 'sensor_msgs/msg/CompressedImage':
                img_msg = self.publishers[outtopic].get_class_obj()
                img_msg.format = content_type[1]
                img_msg.data = resp.content
                outmsgs[outtopic] = img_msg
            elif outtype == 'sensor_msgs/msg/Image':
                img_msg = self.publishers[outtopic].get_class_obj()
                _im = PILImage.open(io.BytesIO(resp.content))
                _im = _im.convert('RGB')
                img_msg.header.stamp = self.node_manager.get_now().to_msg()
                img_msg.height = _im.height
                img_msg.width = _im.width
                img_msg.encoding = 'rgb8'
                img_msg.is_bigendian = False
                img_msg.step = 3 * _im.width
                img_msg.data = _im.tobytes()
                outmsgs[outtopic] = img_msg
            else:
                mlogger.warning(
                    "Not Supported Yet for converting image to %s", outtype)
        # 'text/css, text/html, text/plain, text/xml, text/xsl
        elif content_type[0] == 'text':
            # cannot handle 'text/html' in json api
            mlogger.warning("Not Supported Yet")

        return outmsgs

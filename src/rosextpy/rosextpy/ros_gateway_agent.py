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

# rosextpy.ros_gateway_agent (ros2-ws-gateway)
# Author: parasby@gmail.com
"""ros_gateway_agent
"""

import os
from asyncio.tasks import Task
import multiprocessing
from concurrent.futures import ProcessPoolExecutor, Future
import logging
import asyncio
import threading
import traceback
import functools
import hashlib
import json
# import os
import signal
# from datetime import datetime
from typing import List, Dict, Any, Union
import requests
from tenacity import retry, wait
import tenacity
# from tenacity.retry import retry_if_exception
from pydantic import BaseModel  # pylint: disable=no-name-in-module, import-error

# configuration module have to be importedbefore any other sub modules
# from ..mod_config import WS_CONFIG
# WS_CONFIG['wsf'] = 'fastapi'

from rosextpy.ros_ws_gateway_client import RosWsGatewayClient  # , isNotForbbiden
from rosextpy.node_manager import NodeManager
from rosextpy.ros_ws_gateway_endpoint import RosWsGatewayEndpoint
from rosextpy.ros_ws_gateway import RosWsGateway
from rosextpy.ros_rpc_gateway_client import RosRPCGatewayClient

mlogger = logging.getLogger('ros_gateway_agent')
# mlogger.setLevel(logging.DEBUG)
# logging.basicConfig(
#     stream=sys.stdout,
#     format='%(levelname)-6s [%(filename)s:%(lineno)d] %(message)s', level=logging.DEBUG)

# pylint: disable=broad-exception-caught


def logerror(retry_state: tenacity.RetryCallState):
    """logerror"""
    mlogger.debug("connection failed finally because %s", retry_state.outcome)
#    mlogger.debug(traceback.format_exc())



########################
# exception
#######################

class GatewayAgentException(Exception):
    """GatewayAgentException"""
    def __init__(self, msg=None):
        self.msg = msg

    def __str__(self):
        return f"GatewayAgentException {self.msg}"

########################
##
# GatewayTaskLog : it stores the gateway tasks(pub/sub...)
#########################


class ROSRESTRule(BaseModel):
    """ROSRESTRule"""
    service_name: str
    service_uri: str
    service_method: str
    request_rule: Dict[str, Any]
    response_rule: Dict[str, Any]

######################
# DefaultRPCManager
#######################


class DefaultRPCManager:
    """ DefaultRPCManager"""

    def __init__(self, timeout=30):
        self.timeout = timeout

    def call(self, service_uri, service_method, headers=None, data=None, files=None):
        """call"""
        mlogger.debug(
            "emulate to send action result to action caller.............")
        # print("\nDATA...\n")
        # print(data)
        # print("\nHEAD...\n")
        # print(headers)
        # print("\n...\n")
        try:
            if service_method == 'POST':
                return requests.post(service_uri, headers = headers,
                    files=files, data=data, timeout=self.timeout)
        except Exception as err:
            mlogger.debug("An error occurred in requests due to [%s]", err)
            return None

    def close(self):
        """close"""
        self.timeout = 0

########################
##
# RosWsGatewayAgent : create gateway_endpoint, and manage gateway_client
#########################


class GatewayTaskMap():
    """GatewayTaskMap
    """

    def __init__(self):
        # reader task can be GatewayClient or GatewayTask from endpoint
        self.gw_tasks: Dict[str, Union[Task, Future]] = {}
        # self.gw_tasks: Dict[str, Any] = {}  # test for humble
        self.gw_tasks_lock = threading.RLock()

    def stop_tasks(self):
        """stop_tasks
        """
        mlogger.debug("stop_tasks")
        try:
            for t_task in list(self.gw_tasks.values()):
                t_task.cancel()
        except Exception:
            mlogger.debug(traceback.format_exc())

    # def add_task(self, codekey: str, task: Any): # test for humble
    def add_task(self, codekey: str, task: Union[Task, Future]):
        """add_task

        Args:
            codekey (str): 
            task (Task): 
        """
        with self.gw_tasks_lock:
            self.gw_tasks[codekey] = task  # gateway client instance

    def del_task(self, codekey: str):
        """del_task

        Args:
            codekey (str): 
        """
        with self.gw_tasks_lock:
            self.gw_tasks.pop(codekey)


class GatewayConfigLog():
    """GatewayConfigLog"""

    def __init__(self):
        # [uri, [operation, [codekey, config]]]
        self.gw_config_log: Dict[str, Dict[str, Dict[str, Dict]]] = {}
        self.gw_config_log_lock = threading.RLock()

    def add_config_log(self, uri: str, opr: str, codekey: str, cfg: Union[Dict, ROSRESTRule]):
        """add_config_log

        Args:
            uri (str): uri of the gateway to store
            opr (str): operation of the gateway to store
            codekey (str): codekey of the gateway to store
            cfg (Dict): config of the gateway to store
        """
        with self.gw_config_log_lock:
            # save config into config_log
            if self.gw_config_log.get(uri, None) is None:
                self.gw_config_log[uri] = {}
            if self.gw_config_log[uri].get(opr, None) is None:
                self.gw_config_log[uri][opr] = {}
            if isinstance(cfg, ROSRESTRule):
                self.gw_config_log[uri][opr][codekey] = cfg.dict()
            else:
                self.gw_config_log[uri][opr][codekey] = cfg

    def remove_config_log(self, uri: str, opr: str, codekey: str):
        """remove_config_log

        Args:
            uri (str): uri of the gateway to remove
            opr (str): opr of the gateway to remove
            codekey (str): codekey of the gateway to remove
        """
        if self.gw_config_log.get(uri, None) is not None:
            if codekey is not None:
                with self.gw_config_log_lock:
                    self.gw_config_log[uri].pop(codekey, None)
            elif opr is not None:
                with self.gw_config_log_lock:
                    self.gw_config_log[uri].pop(opr, None)

    def get_config_lists(self, uri: Union[str, None], opr: str) -> str:
        """get_config_lists

        Args:
            uri (str): uri of the gateway to retrieve
            opr (str): opr of the gateway to retrieve

        Returns:
            str: json dump string of selected configs
        """
        if uri is None and opr is None:
            return ""
        if uri is None:
            results = {}
            for _kuri, _cfg in self.gw_config_log.items():
                _item = _cfg.get(opr, None)
                if _item is not None:
                    if results.get(_kuri, None) is None:
                        results[_kuri][opr] = []
                    elif results[_kuri].get(opr, None) is None:
                        results[_kuri][opr] = []
                    results[_kuri][opr].extend(_item)
            return json.dumps(results)

        if self.gw_config_log[uri].get(opr, None) is None:
            return ""

        results = {uri: {opr: self.gw_config_log[uri][opr]}}
        return json.dumps(results)

    def to_json(self) -> str:
        """to_json

        Returns:
            str: json dump string of all configs
        """
        return json.dumps(self.gw_config_log)


class GatewayClientMap():
    """GatewayClientMap"""

    def __init__(self):
        # [uri, [codekey, client]]
        self.gwc_map: Dict[str, Dict[str, RosWsGatewayClient]] = {}
        self.gwc_map_lock = threading.RLock()

    def get_uri_clients(self, uri: str) -> Union[Dict[str, RosWsGatewayClient], None]:
        """get_uri_clients

        Args:
            uri (str): uri of the client to get

        Returns:
            Union[Dict[str, RosWsGatewayClient],None]: map of codekey and RosWsGatewayClient
        """
        return self.gwc_map.get(uri, None)

    def get_client_uris(self) -> List[str]:
        """get_client_uris

        Returns:
            List[str]: uri list of all clients
        """
        return list(self.gwc_map.keys())

    def get_codekey_client(self, uri: str, codekey: str) -> Union[RosWsGatewayClient, None]:
        """get_codekey_client

        Args:
            uri (str): uri of the client to get
            codekey (str): codekey of the client to get

        Returns:
            Union[RosWsGatewayClient, None]:  selected client or None
        """
        if uri is None:
            for cfg in self.gwc_map.values():
                _gw = cfg.get(codekey, None)
                if _gw is not None:
                    return _gw
            return None

        if self.gwc_map.get(uri, None) is None:
            return None
        return self.gwc_map[uri].get(codekey, None)

    def set_client(self, uri: str, codekey: str, client: RosWsGatewayClient):
        """set_client

        Args:
            uri (str): uri of the client to set
            codekey (str): codekey of the client to set
            client (RosWsGatewayClient): client of the client to set
        """
        with self.gwc_map_lock:
            if self.gwc_map.get(uri, None) is None:
                self.gwc_map[uri] = {}
            self.gwc_map[uri][codekey] = client

    def del_client(self, uri: str, codekey: str):
        """del_client

        Args:
            uri (str): uri of client to remove 
            codekey (str): codekey of client to remove 
        """
        if uri is None:
            for cfg in self.gwc_map.values():
                _gw = cfg.get(codekey, None)
                if _gw is not None:
                    with self.gwc_map_lock:
                        cfg.pop(codekey, None)
        else:
            if self.gwc_map.get(uri, None) is not None:
                with self.gwc_map_lock:
                    self.gwc_map[uri].pop(codekey, None)

    async def close(self):
        """close all clients in GatewayClientMap
        """
        with self.gwc_map_lock:
            # [uri, [codekey, client]]
            for val in list(self.gwc_map.values()):
                for _tgwc in list(val.values()):
                    await _tgwc.close()
            self.gwc_map.clear()


class RPCClientMap():
    """RPCClientMap"""

    def __init__(self):
        # uri, [codekey, client]
        self.rpc_map: Dict[str, Dict[str, RosRPCGatewayClient]] = {}
        self.rpc_map_lock = threading.RLock()

    def get_uri_clients(self, uri: str) -> Union[Dict[str, RosRPCGatewayClient], None]:
        """get_uri_clients

        Args:
            uri (str): uri of the client to get

        Returns:        
            Union[Dict[codekey: str, RosRPCGatewayClient], None]: 
                dictionary of codekey and clients that match the requested uri
        """
        if self.rpc_map is not None:
            return self.rpc_map.get(uri, None)
        return None

    def get_client_uris(self) -> List[str]:
        """get_client_uris

        Returns:
            List[str]: uri list of all clients
        """
        return list(self.rpc_map.keys())

    def get_codekey_client(
        self, uri: Union[str, None],
            codekey: str) -> Union[RosRPCGatewayClient, None]:
        """get_codekey_client

        Args:
            uri (str): uri of client to get 
            codekey (str): codekey of client to get 

        Returns:
            Union[RosRPCGatewayClient, None]: selected client
        """
        if uri is None:
            for cfg in self.rpc_map.values():
                _gw = cfg.get(codekey, None)
                if _gw is not None:
                    return _gw
            return None

        if self.rpc_map.get(uri, None) is None:
            return None
        return self.rpc_map[uri].get(codekey, None)

    def set_client(self, uri: str, codekey: str, client: RosRPCGatewayClient):
        """set_client

        Args:
            uri (str): uri of client to set 
            codekey (str): codekey of client to set 
            client (RosRPCGatewayClient): client of client to set 
        """
        with self.rpc_map_lock:
            if self.rpc_map.get(uri, None) is None:
                self.rpc_map[uri] = {}
            self.rpc_map[uri][codekey] = client

    def del_client(self, uri: Union[str, None], codekey: str):
        """del_client

        Args:
            uri (str): uri of client to del 
            codekey (str): codekey of client to del 
        """
        if uri is None:
            for cfg in self.rpc_map.values():
                _gw = cfg.get(codekey, None)
                if _gw is not None:
                    with self.rpc_map_lock:
                        cfg.pop(codekey, None)
        else:
            if self.rpc_map.get(uri, None) is not None:
                with self.rpc_map_lock:
                    self.rpc_map[uri].pop(codekey, None)

    def close(self):
        """close all clients in RPCClientMap
        """
        with self.rpc_map_lock:
            # [uri, [codekey, client]]
            for val in list(self.rpc_map.values()):
                for _tgwc in list(val.values()):
                    _tgwc.close()
            self.rpc_map.clear()


class CliCtx:
    """CliCtx
        : gateway client context
    """

    def __init__(self):
        self._ok = True
        self.client = None
        self.fut: Union[Task, None] = None
        self.codekey = None
        self.retry_config = None

    def is_ok(self):
        """is_ok"""
        return self._ok

    def set_task(self, fut):
        """set_task"""
        self.fut = fut

    def stop_task(self):
        """stop_task"""
        if self.fut is not None:
            self.fut.cancel()

    def set_ok(self, state):
        """set_ok"""
        self._ok = state

    def set_client(self, codekey, client):
        """set_client"""
        self.codekey = codekey
        self.client = client


async def run_mp_cli_func(ctx: CliCtx, uri, node_mgr, codekey, opr, cfg):
    """run_mp_cli_func"""
    mlogger.debug("run_mp_cli_func  %s", cfg)
    try:
        if opr == "ros-rest":
            client = RosRPCGatewayClient(node_mgr, DefaultRPCManager(),uri,cfg['service_method'], cfg['request_rule'], cfg['response_rule'])
            ctx.set_client(codekey, client)
            await client.wait_for_close()
            #print("WAIT CLOSE END")
        else:
            async with RosWsGatewayClient(uri, node_mgr, retry_config=None,
                                        max_size=2**25
                                        ) as client:
                ctx.set_client(codekey, client)
                if client.run_operation(opr, cfg) is True:
                    await client.wait_on_reader()
                else:
                    mlogger.debug("Operation Fail %s...%s", opr, cfg)
    except Exception:
        mlogger.debug(traceback.format_exc())
    finally:
        node_mgr.reset()
        # for t_nn in node_mgr.executor.get_nodes():
        #     node_mgr.executor.remove_node(t_nn)
        #     t_nn.destroy_node()
        raise GatewayAgentException("run cli") # trigger for retrying


async def retry_cli_func(ctx: CliCtx, uri, node_mgr, codekey, opr, cfg):
    """retry_cli_func"""
    try:
        await retry(**ctx.retry_config)(run_mp_cli_func)(ctx, uri, node_mgr, codekey, opr, cfg)
    except Exception:
        mlogger.debug(traceback.format_exc())


async def cli_func(ctx: CliCtx, uri, codekey, opr, cfg):
    """cli_func"""
    node_mgr = NodeManager()
    try:
        node_mgr.setDaemon(True)
        node_mgr.start()
        await retry_cli_func(ctx, uri, node_mgr, codekey, opr, cfg)

        # async with RosWsGatewayClient(
        #     uri, node_mgr, retry_config=None,
        #     max_size=2**25
        # ) as client:
        #     ctx.set_client(codekey, client)
        #     if client.run_operation(opr, cfg) is True:
        #         await client.wait_on_reader()

    except Exception:
        mlogger.debug(traceback.format_exc())
    finally:
        mlogger.debug("node manager stopped in child process %s", os.getpid())
        node_mgr.stop()
        node_mgr.join()


async def async_intr_callback(ctx: CliCtx):
    """async_intr_callback"""
    ctx.set_ok(False)
    if ctx.client is not None:
        await ctx.client.close()
    ctx.stop_task()


def run_cli_task(uri, codekey, opr, cfg: Dict):
    """run_cli_task
        : run client task in spawned process
    """
    myctx = CliCtx()
    myctx.retry_config = {  # for MP, config has to be defined in subprocess
        'wait': wait.wait_random_exponential(min=1, max=10),
        # 'retry': retry_if_exception(isNotForbbiden),
        'reraise': True,
        # 'stop': stop_after_attempt(1),  # debug config
        "retry_error_callback": logerror
    }

    loop = asyncio.get_event_loop()
    fut = loop.create_task(cli_func(myctx, uri, codekey, opr, cfg))
    myctx.set_task(fut)
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(
            sig, lambda: asyncio.create_task(async_intr_callback(myctx)))
    try:
        loop.run_until_complete(fut)
    finally:
        loop.close()

class RosWsGatewayAgent():  # pylint : disable=too-many-instance-attributes
    """Forwards ROS messages from its own subnet to the gateway of another subnets, 
    receives ROS messages from other subnets, and delivers them to the subnet it belongs to.
    """

    # , **kwargs):
    def __init__(self, loop=None, namespace = None):
        self.loop = loop if loop is not None else asyncio.get_event_loop()
        self.node_manager = None
        self.node_manager_self_stop = False
        self.rpc_manager = DefaultRPCManager()
        self.endpoint = None
        self.rpc_map = RPCClientMap()
        self.gw_config_log = GatewayConfigLog()
        self.gwc_map = GatewayClientMap()
        self.gw_tasks = GatewayTaskMap()
        self.task_manager = None
        self.namespace = namespace
       

        # try:
        #     ctx = multiprocessing.get_context('spawn')
        #     self.cli_pool = ProcessPoolExecutor(mp_context=ctx)
        # except Exception:
        #     mlogger.debug(traceback.format_exc())

    def ready(self, task_manager):
        """ready"""
        self.task_manager = task_manager

    async def start(self, node_manager: Union[NodeManager, None] = None):
        """start"""
        try:
            if node_manager is None:
                self.node_manager = NodeManager()
                self.node_manager_self_stop = True
                self.node_manager.setDaemon(True)
                self.node_manager.start()
            else:
                self.node_manager = node_manager
                self.node_manager_self_stop = False
            self.endpoint = RosWsGatewayEndpoint(node_manager=self.node_manager)
        except Exception as er:
            mlogger.error("RosWsGatewayAgent error [%s]", str(er))


    async def _on_connect(self, rgw: RosWsGateway):
        mlogger.debug("_on_connect")
        mlogger.debug("Connected to(from) %s", rgw.wshandle.address())

    async def _on_disconnect(self, rgw: RosWsGateway):
        mlogger.debug("_on_disconnect : %s", rgw.wshandle.address())

    def _run_gateway_client(self, uri, codekey, opr, cfg: Dict):
        mlogger.debug("_run_gateway_client: ")
        try:
            #print("_run_gateway_client!!!")
            # mp_ctx = multiprocessing.get_context('spawn')
            # p =mp_ctx.Process(target=run_cli_task, args=(uri,codekey,opr,cfg))
            # p.start()
            if self.task_manager is not None:
                self.task_manager.submit(
                    f"task{codekey}", proc = run_cli_task,
                    params={"uri": uri, "codekey" : codekey, "opr" : opr, "cfg" : cfg})
            else:
                mlogger.error("task_manager cannot be None")

            # _t1 = self.cli_pool.submit(
            #     run_cli_task, uri=uri, codekey=codekey, opr=opr, cfg=cfg)
            # self.gw_tasks.add_task(codekey, _t1)
            # _t1.add_done_callback(functools.partial(
            #     self._task_discards, codekey=codekey))
        except Exception as ex:
            mlogger.error("_run_gateway_client exception error %s", str(ex))
            mlogger.error(traceback.format_exc())

    def _task_discards(self, task, codekey):
        mlogger.debug("_task_discards")
        _ = task
        self.gw_tasks.del_task(codekey)

    def apply_configs(self, configs):
        """apply the agent configuration about ROS pub/sub 
            forwarding with configs[python object from json]
        Args:
            configs: python object[from json]
            ex:{'title' : 'a1', 
                'active' : True,
                'address': 'ws://xxx.xxx.xx.xxx:9090', 
                'publish': [{'name': '/example_topic', 'messageType': 'std_msgs/msg/String'},
                            {'name': '/my_topic', 'messageType': 'std_msgs/msg/String'}], 
                'subscribe': [{'name': '/my_topic', 'messageType': 'std_msgs/msg/String'}]
                },
                {
                    "service_name": "detect service",
                    "service_uri": "http://localhost:9001/detect/",
                    "service_method": "POST",
                    "request_rule": {
                        "content-type": "multipart/form-data",
                        "topics": {
                        "/image1": "sensor_msgs/msg/CompressedImage"
                        },
                        "mapping": [
                        {
                            "in": "/image1",
                            "from": "data",
                            "out": "files",
                            "to": "files"
                        }
                        ]
                    },
                    "response_rule": {
                        "content-type": "image/jpeg",
                        "topics": {
                        "/target": "sensor_msgs/msg/CompressedImage"
                        },
                        "mapping": [
                        {
                            "in": "content",
                            "from": "",
                            "out": "/target",
                            "to": ""
                        }
                        ]
                    }
                }
        Examples:
            >>> with open('filename.json') as json_file:
                    configs = json.load(json_file)
                    agent.apply_configs(configs)            
        """
        if isinstance(configs, List):
            for data in configs:
                active = data.get('active', True)
                if active is True:
                    if data.get('service_uri', None) is not None:
                        t_rule = ROSRESTRule(
                            service_name=data['service_name'],
                            service_uri=data['service_uri'],
                            service_method=data['service_method'],
                            request_rule=data['request_rule'],
                            response_rule=data['response_rule']
                        )
                        self.api_rosrest_add(t_rule)
                    elif data.get('address', None) is not None:
                        self._apply_gw_config(data)
                    else:
                        mlogger.debug("Illegal Configs")
        elif isinstance(configs, Dict):
            active = configs.get('active', True)
            if active is True:
                if configs.get('service_uri', None) is not None:
                    t_rule = ROSRESTRule(
                        service_name=configs['service_name'],
                        service_uri=configs['service_uri'],
                        service_method=configs['service_method'],
                        request_rule=configs['request_rule'],
                        response_rule=configs['response_rule']
                    )
                    self.api_rosrest_add(t_rule)
                elif configs.get('address', None) is not None:
                    self._apply_gw_config(configs)
                else:
                    mlogger.debug("Illegal Configs")
        else:
            mlogger.debug("Unknwon Configs")

    def _apply_gw_config(self, data: Dict):
        """ apply the config of ros2 publish/subscribe agent task
        Args:
            data (dict): config dict
                ex:{'title' : 'a1', 
                    'active' : True,
                    'address': 'ws://xxx.xxx.xx.xxx:9090', 
                    'publish': [{'name': '/example_topic', 'messageType': 'std_msgs/msg/String'},
                                {'name': '/my_topic', 'messageType': 'std_msgs/msg/String'}], 
                    'subscribe': [{'name': '/my_topic', 'messageType': 'std_msgs/msg/String'}]
                    }
        """
        mlogger.debug("_apply_gw_config %s", data)
        try:
            _uri = data.get('address', None)
            if _uri is None:
                mlogger.debug("Illegal Configs")
                return "error"

            # process publish
            pubcfg = data.get('publish', None)
            if pubcfg is not None:
                self.api_publisher_add(_uri, pubcfg)

            subcfg = data.get('subscribe', None)
            if subcfg is not None:
                self.api_subscriber_add(_uri, subcfg)

            srvcfg = data.get('expose-service', None)
            if srvcfg is not None:
                self.api_service_expose(_uri, srvcfg)

            actcfg = data.get('expose-action', None)
            if actcfg is not None:
                self.api_action_expose(_uri, actcfg)

            trpubcfg = data.get('trans-publish', None)
            if trpubcfg is not None:
                self.api_trans_publisher_add(_uri, trpubcfg)

            return "ok"
        except Exception:
            mlogger.debug(traceback.format_exc())
            return "error"

    def _get_codekey(self, uri: str, opr: str, tokens: List[str]):
        _val = [uri, opr]
        _val.extend(tokens)
        _utxt = '<'.join(str(_val))
        _ho = hashlib.sha256(_utxt.encode("utf-8"))
        _ukey = _ho.hexdigest()
        return _ukey

    # def api_remove_gateways(self, rule: List[str]):
    #     """Set the address of the gateway to disconnect.
    #         It stops connection retry to the specified gateways.
    #     Args:
    #         rule (List[str]): list of gateway addresses to disconnect
    #     Returns:
    #         "ok"
    #     """
    #     mlogger.debug("api_remove_gateways %s",rule)
    #     try:
    #         for uri in rule:
    #             gw_task = self.gw_tasks.get(uri, None)
    #             if gw_task:
    #                 gw_task.cancel()
    #         return "ok"
    #     except Exception:
    #         mlogger.debug(traceback.format_exc())
    #         pass

    #############################################
    #  API for gateway API Service
    ############

    #
    # CREATE or UPDATE gateway operation (pub,sub,exp-srv,exp-act)
    ####

    def api_publisher_add(self, uri: str, rule: List[Dict[str, str]]):
        """ set the ROS message forwarding configuration to the specified gateway.
            It causes configured ROS messages to be delivered to the specified gateway.
        Args:
            uri : target gateway address
            rule (List[str]): list of publication forwarding rule        
        Returns:
            "ok" 
        Examples:
            api.add_publish("ws://targetgw",
                [{name:"/my_topic", messageType:"std_msgs/msg/String", israw: False}])
        """
        mlogger.debug("api_publisher_add %s", uri)
        try:
            for cfg in rule:
                codekey = self._get_codekey(uri, 'publish', list(cfg.values()))
                self.gw_config_log.add_config_log(uri, 'publish', codekey, cfg)
                _gw = self.gwc_map.get_codekey_client(uri, codekey)
                if _gw is not None:  # connection remaied
                    mlogger.debug(
                        "publisher reused for [%s]:[%s] ", uri, cfg['name'])
                    _gw.add_publish(cfg['name'], cfg['messageType'],
                                    (cfg.get('israw', 'False') != 'False'),
                                    cfg.get('compression', None))
                else:
                    self._run_gateway_client(uri, codekey, 'publish', cfg)
            return "ok"
        except Exception:
            mlogger.debug(traceback.format_exc())
            return "error"

    def api_subscriber_add(self, uri: str, rule: List[Dict[str, str]]):
        """ set the ROS message pulling configuration to the specified gateway.
            It causes the configured ROS messages of the specified gateway 
            to be delivered to its own gateway.
        Args:
            uri : target gateway address
            rule (List[str]): list of subscription rule        
        Returns:
            "ok" 
        Examples:
            api.add_subscribe("ws://targetgw",
                [{name:"/my_topic", messageType:"std_msgs/msg/String"}])
        """
        mlogger.debug("api_subscriber_add %s", uri)
        try:
            for cfg in rule:
                codekey = self._get_codekey(
                    uri, 'subscribe', list(cfg.values()))
                self.gw_config_log.add_config_log(
                    uri, 'subscribe', codekey, cfg)
                _gw = self.gwc_map.get_codekey_client(uri, codekey)
                if _gw is not None:
                    mlogger.debug(
                        "subscriber reused for [%s]:[%s] ", uri, cfg['name'])
                    _gw.add_subscribe(cfg['name'], cfg['messageType'],
                                      (cfg.get('israw', 'False') != 'False'),
                                      cfg.get('compression', None))
                else:
                    self._run_gateway_client(uri, codekey, 'subscribe', cfg)
            return "ok"
        except Exception:
            mlogger.debug(traceback.format_exc())
            return "error"

    def api_service_expose(self, uri: str, rule: List[Dict[str, str]]):
        """ set the service to be exposed to the specified gateway.            
        Args:
            uri : target gateway address
            rule (List[str]): list of service expose rule        
        Returns:
            "ok" 
        Examples:
            api.api_service_expose("ws://targetgw",
                [{service:"add_two_ints", "serviceType:"srv_tester_if.srv.AddTwoInts"}])
        """
        mlogger.debug("api_service_expose %s", uri)
        try:
            for cfg in rule:
                codekey = self._get_codekey(uri, 'service', list(cfg.values()))
                self.gw_config_log.add_config_log(
                    uri, 'service', codekey,  cfg)
                _gw = self.gwc_map.get_codekey_client(uri, codekey)
                if _gw is not None:
                    mlogger.debug(
                        "service reused for [%s]:[%s] ", uri, cfg['service'])
                    _gw.expose_service(cfg['service'], cfg['serviceType'],
                                       (cfg.get('israw', 'False') != 'False'),
                                       cfg.get('compression', None))
                else:
                    self._run_gateway_client(
                        uri, codekey, 'expose-service', cfg)
            return "ok"
        except Exception:
            mlogger.debug(traceback.format_exc())
            return "error"

    def api_action_expose(self, uri: str, rule: List[Dict[str, str]]):
        """ set the action to be exposed to the specified gateway.            
        Args:
            uri : target gateway address
            rule (List[str]): list of action expose rule        
        Returns:
            "ok" 
        Examples:
            api.api_action_expose("ws://targetgw",
                [{action:"fibonacci", actionType:"action_tester_if.action.Fibonacci"}])
        """
        mlogger.debug("api_action_expose %s", uri)
        try:
            for cfg in rule:
                codekey = self._get_codekey(uri, 'action', list(cfg.values()))
                self.gw_config_log.add_config_log(uri, 'action', codekey, cfg)
                _gw = self.gwc_map.get_codekey_client(uri, codekey)
                if _gw is not None:
                    mlogger.debug(
                        "action reused for [%s]:[%s] ", uri, cfg['action'])
                    _gw.expose_action(cfg['action'], cfg['actionType'],
                                      (cfg.get('israw', 'False') != 'False'),
                                      cfg.get('compression', None))
                else:
                    self._run_gateway_client(
                        uri, codekey, 'expose-action', cfg)

            return "ok"
        except Exception:
            mlogger.debug(traceback.format_exc())
            return "error"

    #
    # DELETE gateway operation (pub,sub,exp-srv,exp-act)
    ####
    def api_publisher_remove(self, uri: str, rule: List[Dict[str, str]]):
        """ stops the ROS message forwarding for the specified gateway
        Args:
            uri : target gateway address
            rule (List[str]): list of published ROS messages        
        Returns:
            "ok" If successful, "unknown gateway address" otherwise.
        Examples:
            api.api_remove_publish("ws://targetgw",
                [{name:"/my_topic", messageType:"std_msgs/msg/String"}])
        """
        mlogger.debug("api_publisher_remove %s", uri)
        try:
            for cfg in rule:
                codekey = self._get_codekey(uri, 'publish', list(cfg.values()))
                _gw = self.gwc_map.get_codekey_client(uri, codekey)
                if _gw is not None:
                    _gw.remove_publish(cfg['name'])
                    self.gw_config_log.remove_config_log(
                        uri, 'publish', codekey)
            return "ok"
        except Exception:
            mlogger.debug(traceback.format_exc())
            return "error"

    def api_subscriber_remove(self, uri: str, rule: List[Dict[str, str]]):
        """ requests the specified gateway to stop sending ROS messages to its own gateway.
        Args:
            uri : target gateway address
            rule (List[str]): list of subscribed ROS messages        
        Returns:
            "ok" If successful, "unknown gateway address" otherwise.
        Examples:
            api.api_remove_subscribe("ws://targetgw",
                [{name:"/my_topic", messageType:"std_msgs/msg/String"}])
        """
        mlogger.debug("api_subscriber_remove %s", uri)
        try:
            for cfg in rule:
                codekey = self._get_codekey(
                    uri, 'subscribe', list(cfg.values()))
                _gw = self.gwc_map.get_codekey_client(uri, codekey)
                if _gw is not None:
                    _gw.remove_subscribe(cfg['name'])
                    self.gw_config_log.remove_config_log(
                        uri, 'subscribe', codekey)
            return "ok"
        except Exception:
            mlogger.debug(traceback.format_exc())
            return "error"

    def api_service_hide(self, uri: str, rule: List[Dict[str, str]]):
        """ requests the specified gateway to stop send ROS srv request
        Args:
            uri : target gateway address
            rule (List[str]): list of exposed ROS service to be hidden
        Returns:
            "ok" If successful, "unknown gateway address" otherwise.
        Examples:
            api.api_service_hide("ws://targetgw",
                [{service:"add_two_ints"}])
        """
        mlogger.debug("api_service_hide %s", uri)
        try:
            for cfg in rule:
                codekey = self._get_codekey(uri, 'service', list(cfg.values()))
                _gw = self.gwc_map.get_codekey_client(uri, codekey)
                if _gw is not None:
                    _gw.hide_service(cfg['service'])
                    self.gw_config_log.remove_config_log(
                        uri, 'service', codekey)
            return "ok"
        except Exception:
            mlogger.debug(traceback.format_exc())
            return "error"

    def api_action_hide(self, uri: str, rule: List[Dict[str, str]]):
        """ requests the specified gateway to stop send ROS action request
        Args:
            uri : target gateway address
            rule (List[str]): list of exposed ROS action to be hidden
        Returns:
            "ok" If successful, "unknown gateway address" otherwise.
        Examples:
            api.api_action_hide("ws://targetgw",
                [{action:"fibonacci"])
        """
        mlogger.debug("api_action_hide %s", uri)
        try:
            for cfg in rule:
                codekey = self._get_codekey(uri, 'action', list(cfg.values()))
                _gw = self.gwc_map.get_codekey_client(uri, codekey)
                if _gw is not None:
                    _gw.hide_action(cfg['action'])
                    self.gw_config_log.remove_config_log(
                        uri, 'action', codekey)
            return "ok"
        except Exception:
            mlogger.debug(traceback.format_exc())
            return "error"

    #
    # RETRIEVE gateway operation config(pub,sub,exp-srv,exp-act)
    ####

    def api_get_config(self, rule: List[str]):
        """
        get the config set fro the request gateway address
        Args:
            rule (List[str]): list of gateway addresses to query
        Returns:
            list of configuration if successful, empty list otherwise.                    
        """
        mlogger.debug("api_get_config %s", rule)
        return self.gw_config_log.to_json()

    def api_get_gw_list(self):
        """ get connected gateway server list [ url ]
        """
        mlogger.debug("api_get_gw_list")
        return self.gwc_map.get_client_uris()

    def api_get_topic_list(self):
        """ get topic list being published in the network
        """
        mlogger.debug("api_get_topic_list")
        if self.node_manager is not None:
            topic_list = self.node_manager.get_topic_list()
        else:
            topic_list=[]
        return topic_list

    def api_rosrest_add(self, rule: ROSRESTRule):
        """ add rot-to-rest binding configuration              

        ##  key is (output topic + service_uri + input_topic)
        Args:
            rule: ros-rest binding config            
        Returns:
            { "id" : id}
        Examples:
            api_add_ros_rest("{}")
        """
        mlogger.debug("api_add_ros_rest%s", rule)
        try:
            _tokens = [*list(rule.response_rule['topics'].keys()),
                       *list(rule.request_rule['topics'].keys())]
            codekey = self._get_codekey(rule.service_uri, 'rest', _tokens)

            self.gw_config_log.add_config_log(
                rule.service_uri, 'ros-rest', codekey, rule)
            _gw = self.rpc_map.get_codekey_client(rule.service_uri, codekey)
            if _gw is not None:
                _gw.reset(rule.request_rule, rule.response_rule)
            else:
                self._run_gateway_client(rule.service_uri, codekey, "ros-rest", rule.dict())
            return {"id": codekey}
        except Exception:
            mlogger.debug(traceback.format_exc())
            return "error"

    def api_rosrest_lists(self):
        """ add rot-to-rest binding configuration      
        Returns:
            {uri : { operation : [ rule ]}}
            ex: 
            {
                'testuri1': {
                    'publish': [
                        {'name':'/example_topic', 'messageType' : 'std_msgs/msg/String'}
                    ]
                }
            }
        Examples:
            api_add_ros_rest("{}")
        """
        mlogger.debug("api_ros_rest_lists ")
        return self.gw_config_log.get_config_lists(None, 'ros-rest')

    def api_rosrest_stop(self, rule_id: str):
        """ requests the specified ROS-REST Mapping process .
        Args:
            rule_id : ROS-REST mapping rule id
        Returns:
            "ok" If successful, "unknown rule id" otherwise.
        Examples:
            api.api_rosrest_stop("target-id-to-stop-process")
        """
        mlogger.debug("api_rosrest_stop %s", rule_id)
        try:
            _gw = self.rpc_map.get_codekey_client(None, rule_id)
            if _gw:
                _gw.close()
                self.rpc_map.del_client(None, rule_id)
                return "ok"
            else:
                return "unknown rule id"
        except Exception:
            mlogger.debug(traceback.format_exc())
            return "error"

    # new API
    def api_trans_publisher_add(self, uri: str, rule: List[Dict[str, str]]):
        """ set the ROS message forwarding configuration 
             with another name to the specified gateway.
            It causes configured ROS messages to be delivered to the specified gateway.
        Args:
            uri : target gateway address
            rule (List[str]): list of publication forwarding rule        
        Returns:
            "ok" 
        Examples:
            api.api_trans_publisher_add("ws://targetgw",
                [{name:"/my_topic", messageType:"std_msgs/msg/String", 
                "remote_name", "/remote/mytopic", israw: False, compression: None}])
        """
        mlogger.debug("api_trans_publisher_add %s", uri)
        try:
            for cfg in rule:
                codekey = self._get_codekey(
                    uri, 'trans_publish', list(cfg.values()))
                self.gw_config_log.add_config_log(
                    uri, 'trans_publish', codekey, cfg)
                _gw = self.gwc_map.get_codekey_client(uri, codekey)
                if _gw is not None:  # connection remaied
                    mlogger.debug(
                        "trans_publisher reused for [%s]:[%s] ", uri, cfg['name'])
                    _gw.add_trans_publish(cfg['name'], cfg['messageType'],
                                          cfg['remote_name'],
                                          (cfg.get('israw', 'False') != 'False'),
                                          cfg.get('compression', None))
                else:
                    self._run_gateway_client(
                        uri, codekey, 'trans-publish', cfg)
            return "ok"
        except Exception:
            mlogger.debug(traceback.format_exc())
            return "error"

    async def close(self):
        """ close all client connections and the gateway endpoint service
        """
        mlogger.debug("agent stopped")
        self.gw_tasks.stop_tasks()
        await self.gwc_map.close()
        self.rpc_map.close()
        if self.node_manager_self_stop:
            if self.node_manager is not None:
                self.node_manager.stop()
                self.node_manager.join()

    async def serve(self, websocket, ws_provider, request=None):
        """ run the gateway endpoint service
        """
        if self.endpoint is not None:
            await self.endpoint.serve(websocket, ws_provider, request)

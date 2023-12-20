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

# rosextpy.ext_type_support (ros2-ws-gateway)
# Author: parasby@gmail.com


# run the following instructions before using this module
##
# ros:galactic, ros:rolling
##
# rosdep update
# sudo apt update
# sudo apt install -y --no-install-recommends ros-$ROS_DISTRO-rmw-fastrtps-cpp
# export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
##
import json
import importlib
import logging
# import traceback
import array
from typing import Dict, Any, List
#import zlib as Compressor
import hashlib
import lz4.frame
#import snappy

import pybase64
from rclpy.serialization import deserialize_message
from rclpy.serialization import serialize_message
from rosextpy import _rosextpy_pybind11  # pylint: disable=no-name-in-module, import-error
import cbor
from builtin_interfaces.msg._time import Time as ROSTime
# from std_msgs.msg._header import Header as ROSHeader
import numpy

mlogger = logging.getLogger('ext_type_support')

# pylint: disable=bad-mcs-classmethod-argument

class Compressor:
    """Compressor"""
    @staticmethod
    def compress(data :bytes) -> bytes:
        """compress"""
        return lz4.frame.compress(data)
        #return snappy.compress(data)


    @staticmethod
    def decompress(data :bytes) -> bytes:
        """decompress"""
        return lz4.frame.decompress(data)
        #return snappy.decompress(data)

class GenericTypeSuperMeta(type):
    """GenericTypeSuperMeta

    Args:
        type :  base class of metaclass

    """
    _FUNC1 = None
    _FUNC2 = None

    @classmethod
    def __import_type_support__(cls):
        pass

    @classmethod
    def __prepare__(cls, name, bases, **kwargs):
        _ = name
        _ = bases
        _ = kwargs
        return {
        }


def SerializedTypeLoader(clsname):  # pylint: disable=invalid-name
    """SerializedTypeLoader

    Args:
        clsname : type class to use SerializedTypeLoader 

    Returns:
        _type_: generated type class
    """
    (mname, cname) = clsname.rsplit('/', 1)
    if mname.find('/msg') == -1:
        clsname = ''.join([mname, '/msg/', cname])
    ttype = type(clsname+'_meta',
                 (GenericTypeSuperMeta,),
                 {'_CREATE_ROS_MESSAGE': _rosextpy_pybind11.create_ros_message_serialized_msg,
                     '_CONVERT_FROM_PY':  _rosextpy_pybind11.convert_from_py_serialized_msg,
                     '_CONVERT_TO_PY': _rosextpy_pybind11.convert_to_py_serialized_msg,
                     '_DESTROY_ROS_MESSAGE': _rosextpy_pybind11.destroy_ros_message_serialized_msg,
                     '_TYPE_SUPPORT': _rosextpy_pybind11.get_type_support(clsname)
                  })

    class TempClass(metaclass=ttype):     # pylint: disable=missing-class-docstring, too-few-public-methods
        pass
    return TempClass

# for sequnce<uint8>
# in ROS2 , type of sequnce is 'array.array'


def is_ros_obj(obj) -> bool:
    """is_ros_obj

    Args:
        obj (Any): target object

    Returns:
        bool: it returns true if target object is ros
    """
    return hasattr(obj, 'get_fields_and_field_types')


def ros_to_text_dict(obj: Any) -> Any:
    """ros_to_text_dict

    Args:
        obj (Any):  target object

    Returns:
        Any: any object(list, binary, text, primitive) converted from ros object
    """
    if hasattr(obj, 'get_fields_and_field_types'):
        members: dict = obj.get_fields_and_field_types()
        results = {}
        for name in members:
            results[name] = ros_to_text_dict(getattr(obj, name))
        return results
    if isinstance(obj, array.array):
        # if obj.typecode in ('b', 'B', 'c'):
        #     return pybase64.b64encode(obj.tobytes()).decode()
        return obj.tolist()  # for compatibility with rosbridge
    if isinstance(obj, numpy.ndarray):
        return obj.tolist()
    if isinstance(obj, bytes):
        return pybase64.b64encode(obj).decode()
    if isinstance(obj, list):
        outlist = []
        for item in obj:
            outlist.append(ros_to_text_dict(item))
        return outlist

    return obj

# for ROS2

# pylint: disable=too-many-return-statements


def ros_from_text_dict(data: Any, obj: Any) -> Any:
    """ros_from_text_dict

    Args:
        data (Any): Any object in which properties of ROS object is encoded
        obj (Any): target ROS object

    Returns:
        Any: ROS object set from dictionary
    """
    try:
        if isinstance(obj, ROSTime):
            if 'nsecs' in data:  # if data has nsecs it must be ROS1
                sec = data.get('secs', 0)
                nanosec = data.get('nsecs', 0)
            else:
                sec = data.get('sec', 0)
                nanosec = data.get('nanosec', 0)
            return ROSTime(sec=sec, nanosec=nanosec)
        if hasattr(obj, 'get_fields_and_field_types'):
            members: dict = obj.get_fields_and_field_types()
            for name, ntype in members.items():
                field_item = getattr(obj, name)
                if isinstance(data, dict):
                    _val = data.get(name, None)
                    if _val is not None:
                        if isinstance(field_item, list):  # can be ros message list
                            item_cls = TypeLoader(get_ros_list_type(ntype))
                            setattr(obj, name, ros_from_text_list(
                                data[name], item_cls))
                        else:
                            setattr(obj, name, ros_from_text_dict(
                                data[name], field_item))
                    else:
                        mlogger.warning('%s of %s not found',
                                        name, obj.__class__.__name__)
            return obj
        if isinstance(obj, array.array):
            # if obj.typecode in ('b', 'B', 'c'):
            #     obj.frombytes(pybase64.b64decode(data))
            # else:
            obj.fromlist(data)  # for compatibility with rosbridge
            return obj
        if isinstance(obj, float):
            return float(data)
        if isinstance(obj, numpy.ndarray):
            return numpy.array(data)
        if isinstance(obj, bytes):
            return pybase64.b64decode(data)
        obj = data
        return obj
    except Exception as ex:
        mlogger.debug('ros_from_text_dict : %s ', str(ex))
        raise


def get_ros_list_type(typestr: str) -> str:
    """get_ros_list_type

    Args:
        typestr (str): long name of class type

    Returns:
        str: short name of class type
    """
    return typestr.split("<")[1].split('>')[0]


def get_ros_type_name(obj: Any) -> str:
    """get_ros_type_name

    Args:
        obj (Any): ROS object

    Returns:
        str: type name of the ROS object
    """
    if hasattr(obj, 'get_fields_and_field_types'):
        _tn = obj.__class__.__module__.split('.')
        _tn.pop()
        _tn.append(obj.__class__.__name__)
        return '/'.join(_tn)
    return obj.__class__.__name__


def ros_from_text_list(data: List[Dict], cls: Any) -> List[Any]:
    """ros_from_text_list

    Args:
        data (List[Dict]): list of text dictionary in which properties of ROS object is encoded
        cls (Any): class of target 

    Returns:
        List[Any]: List of decoded ROS object
    """
    out = []
    for item in data:
        out.append(ros_from_text_dict(item, cls()))
    return out


def ros_from_bin_list(data: List[Dict], cls: Any) -> List[Any]:
    """ros_from_bin_list

    Args:
        data (List[Dict]): list of binary dictionary in which properties of ROS object is encoded
        cls (Any): class of target 

    Returns:
        List[Any]: List of decoded ROS object
    """
    out = []
    for item in data:
        out.append(ros_from_bin_dict(item, cls()))
    return out

# pylint: disable=too-many-return-statements


def ros_from_bin_dict(data: Any, obj: Any) -> Any:
    """ros_from_bin_dict

    Args:
        data (Any): any object in which properties of ROS object is encoded
        obj (Any): target ROS object

    Returns:
        Any: ROS object set from dictionary
    """
    try:
        if isinstance(obj, ROSTime):
            if 'nsecs' in data:  # if data has nsecs it must be ROS1
                sec = data.get('secs')
                nanosec = data.get('nsecs')
            else:
                sec = data.get('sec')
                nanosec = data.get('nanosec')
            return ROSTime(sec=sec, nanosec=nanosec)
        elif hasattr(obj, 'get_fields_and_field_types'):
            members: dict = obj.get_fields_and_field_types()
            for name, ntype in members.items():
                field_item = getattr(obj, name)
                if isinstance(field_item, list):  # can be ros message list
                    item_cls = TypeLoader(get_ros_list_type(ntype))
                    setattr(obj, name, ros_from_bin_list(data[name], item_cls))
                else:
                    setattr(obj, name, ros_from_bin_dict(
                        data[name], field_item))
            return obj
        elif isinstance(obj, float):
            return float(data)
        elif isinstance(obj, array.array):
            obj.frombytes(data)
            return obj
        elif isinstance(obj, numpy.ndarray):
            return numpy.frombuffer(data)
        else:
            obj = data
            return obj
    except Exception as ex:
        mlogger.debug('ros_from_bin_dict exception %s', ex)
        raise


def ros_to_bin_dict(obj: Any) -> Any:
    """ros_to_bin_dict

    Args:
        obj (Any): target object to be encoded

    Returns:
        Any: encoded binary object
    """
    if hasattr(obj, 'get_fields_and_field_types'):
        members: dict = obj.get_fields_and_field_types()
        results = {}
        for name in members:
            results[name] = ros_to_bin_dict(getattr(obj, name))
        return results
    elif isinstance(obj, array.array):
        return obj.tobytes()
    elif isinstance(obj, numpy.ndarray):
        return obj.tobytes()
    elif isinstance(obj, list):
        outlist = []
        for item in obj:
            outlist.append(ros_to_bin_dict(item))
        return outlist
    else:
        return obj


def ros_serialize(obj: Any) -> bytes:
    """ros_serialize

    Args:
        obj (Any): target object to be serialized

    Returns:
        bytes: serialized binary data of ROS object
    """
    return serialize_message(obj)


def ros_deserialize(data: bytes, cls_type: Any) -> Any:
    """ros_deserialize

    Args:
        data (bytes): serialized binary data of ROS object
        cls_type (Any): target class of object to be deserialized

    Returns:
        Any: deserialized ROS object
    """
    return deserialize_message(data, cls_type)


def ros_to_compress(obj: Any) -> bytes:
    """ros_to_compress

    Args:
        obj (Any): target object to be compressed

    Returns:
        bytes: compressed data
    """
    return Compressor.compress(cbor.dumps(ros_to_bin_dict(obj)))


def ros_from_compress(data: bytes, obj: Any) -> Any:
    """ros_from_compress

    Args:
        data (bytes): compressed data
        obj (Any): target object to be decompressed

    Returns:
        Any: target object decompressed from data
    """
    return ros_from_bin_dict(cbor.loads(Compressor.decompress(data)), obj)


class TypeModuleError(Exception):
    """TypeModuleError"""

    def __init__(self, errorstr):
        self.errorstr = errorstr

    def __str__(self):
        return ''.join(['Cannot find modules for the type "', self.errorstr, '"'])


# pylint: disable=invalid-name
def TypeLoader(clsname: str) -> Any:
    """TypeLoader

    Args:
        clsname (str): name string of the class to load

    Raises:
        TypeModuleError: illegal class name 

    Returns:
        Any: ROS object class
    """
    try:
        (mname, cname) = clsname.rsplit('/', 1)
        mname = mname.replace('/', '.')
        if mname.find('.msg') == -1:
            mname = ''.join([mname, '.msg'])
        mod = importlib.import_module(mname)
        clmod = getattr(mod, cname)
        return clmod
    except ValueError:
        (mname, cname) = clsname.rsplit('.', 1)
        if mname.find('.msg') == -1:
            mname = ''.join([mname, '.msg'])
        mod = importlib.import_module(mname)
        clmod = getattr(mod, cname)
        return clmod
    except AttributeError as exc:
        raise TypeModuleError(clsname) from exc
    except Exception as ex2:
        raise TypeModuleError(clsname) from ex2

# pylint: disable=invalid-name


def SrvTypeLoader(clsname: str) -> Any:
    """SrvTypeLoader

    Args:
        clsname (str): name string of the service class to load

    Raises:
        TypeModuleError: illegal class name 

    Returns:
        Any: ROS object class
    """
    try:
        (mname, cname) = clsname.rsplit('/', 1)  # sensor_msgs/srv/SetCameraInfo
        mname = mname.replace('/', '.')
        if mname.find('.srv') == -1:
            mname = ''.join([mname, '.srv'])
        mod = importlib.import_module(mname)
        clmod = getattr(mod, cname)
        return clmod
    except ValueError:
        (mname, cname) = clsname.rsplit('.', 1)  # sensor_msgs.srv.SetCameraInfo
        if mname.find('.srv') == -1:
            mname = ''.join([mname, '.srv'])
        mod = importlib.import_module(mname)
        clmod = getattr(mod, cname)
        return clmod
    except Exception as exc:
        raise TypeModuleError(clsname) from exc

# pylint: disable=invalid-name


def ActionTypeLoader(clsname: str) -> Any:
    """ActionTypeLoader

    Args:
        clsname (str): name string of the service class to load

    Raises:
        TypeModuleError: illegal class name 

    Returns:
        Any: ROS object class
    """
    try:
        # ex: action_tutorials_interfaces/action/Fibonacci
        (mname, cname) = clsname.rsplit('/', 1)
        mname = mname.replace('/', '.')
        if mname.find('.action') == -1:
            mname = ''.join([mname, '.action'])
        mod = importlib.import_module(mname)
        clmod = getattr(mod, cname)
        return clmod
    except ValueError:
        # ex: action_tutorials_interfaces.action.Fibonacci
        (mname, cname) = clsname.rsplit('.', 1)
        if mname.find('.action') == -1:
            mname = ''.join([mname, '.action'])
        mod = importlib.import_module(mname)
        clmod = getattr(mod, cname)
        return clmod
    except Exception as exc:
        raise TypeModuleError(clsname) from exc


# usage:
#   get_ros_value(rosObj, 'aaa.bbb.ccc')
def get_ros_value(obj: Any, attrname: str) -> Any:
    """get_ros_value

    Args:
        obj (Any): ros object
        attrname (str): target attribute name to get

    Returns:
        Any: attribute value
    """
    try:
        names = attrname.split('/', 1)
        if len(names) == 1:
            return getattr(obj, names[0])
        else:
            return get_ros_value(getattr(obj, names[0]), names[1])
    except AttributeError:
        return None


def set_ros_value(obj: Any, targetpath: str, value: Any) -> Any:
    """set_ros_value

    Args:
        obj (Any): ros object
        targetpath (str): target attribute path , ex) "head.sub.tail"
        value (Any): value to set

    Returns:
        Any: ros object set with the passed value
    """
    if targetpath == "":
        ros_from_text_dict(value, obj)
    else:
        names = targetpath.split('.', 1)
        if len(names) == 1:  # final path
            setattr(obj, names[0], value)
        else:
            obj_m = getattr(obj, names[0])
            setattr(obj, names[0], set_ros_value(obj_m, names[1], value))
    return obj


def get_json_value(obj: Dict, attrname: str) -> Any:
    """get_json_value

    Args:
        obj (Dict):  target JSON dict
        attrname (str): target attribute path , ex) "head/sub/tail"

    Returns:
        Any: value of the object 
    """
    try:
        if isinstance(obj, str):
            obj = json.loads(obj)
        names = attrname.split('/', 1)
        if len(names) == 1:
            return obj.get(names[0], None)
        return get_json_value(obj[names[0]], names[1])
    except AttributeError:
        return None


def get_hash_code(head: str, tokens: List[str]):
    """get_hash_code"""
    _val = [head]
    _val.extend(tokens)
    _utxt = '<'.join(str(_val))
    _ho = hashlib.sha256(_utxt.encode("utf-8"))
    _ukey = _ho.hexdigest()
    return _ukey


# serialized srv loader  ## We have to add serialization helper function for support srv
# def SerializedSrvTypeLoader(clsname: str): # pylint: disable=invalid-name
#     (mname, cname) = clsname.rsplit('/', 1)
#     if mname.find('/srv') == -1:
#         clsname = ''.join([mname, '/srv/', cname])
#     ttype = type(clsname+'_meta',
#                  (GenericTypeSuperMeta,),
#                  {
#                     '_TYPE_SUPPORT': _rosextpy_pybind11.get_type_support(clsname)
#                   })
#     class TempClass(metaclass=ttype):     # pylint: disable=missing-class-docstring, too-few-public-methods
#         Request = SerializedTypeLoader('_'.join([clsname,'Request']))
#         Response = SerializedTypeLoader('_'.join([clsname,'Response']))
#         pass
#     return TempClass

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

# rosextpy.ros_rpc_utils (ros-ws-gateway)
# Author: ByoungYoul Song(paraby@gmail.com)
"""ros_rpc_utils
"""
import logging
import os
import re
from typing import Dict, Any, List

mlogger = logging.getLogger('ros_rpc_utils')
# mlogger.setLevel(logging.DEBUG)

# pylint: disable=broad-exception-caught
# pylint: disable=too-many-arguments
# pylint: disable=too-many-instance-attributes


class RPCUtilsException(Exception):
    """RPCUtilsException """

    def __init__(self, msg: str = ""):
        super().__init__("RPCUtils :"+msg)


def replace_env_in_string(input_str):
    """replace_env_in_string"""
    parts = input_str.split('${')
    result = parts[0]

    for part in parts[1:]:
        var_name, _, rest = part.partition('}')
        var_value = os.environ.get(var_name, '')
        result += var_value + rest
    return result


def process_header_rule(content_type, headers):
    """process_headers"""
    if not isinstance(headers, dict):
        return None
    rq_headers = {"Content-Type": content_type}
    for key, val in headers.items():
        rq_headers[key] = replace_env_in_string(val)
    return rq_headers


BODY_RULE_TOKEN_TYPES = [
    ('ONLYNAME', r'[a-zA-Z_]\w*'),
    ('ARRNUMBER', r'\d+'),
    ('LBRACKET', r'\['),
    ('RBRACKET', r'\]'),
    ('SUBMEMBER', r'\.'),
    ('WHITESPACE', r'\s+'),
]


# 토큰 생성 함수
def tokenize(text, rule):
    """tokenize"""
    tokens = []
    while text:
        for token_type, pattern in rule:
            match = re.match(pattern, text)
            if match:
                value = match.group(0)
                if token_type != 'WHITESPACE':
                    tokens.append((token_type, value))
                text = text[len(value):]
                break
        else:
            raise ValueError(f"Unexpected character: {text[0]}")
    return tokens


def set_obj_with_path(body: Dict, path: str, value: Any) -> Dict:
    """set_obj_with_path"""
    tokens = tokenize(path, BODY_RULE_TOKEN_TYPES)
    if len(tokens) == 0:
        raise ValueError(f"illegal path: {path}")
    if tokens[0][0] != 'ONLYNAME':  # first member is to be ONLYNAME
        raise ValueError(f"illegal path: {path}")
    if len(tokens) == 1:  # final path
        body[tokens[0][1]] = value
    else:
        body[tokens[0][1]] = _set_obj_sub(
            body.get(tokens[0][1]), tokens[1:], value)
    return body


def _set_obj_sub(b_obj, tokens, val):
    """_set_obj_sub"""
    if tokens[0][0] == 'SUBMEMBER':  # submembers
        if len(tokens) < 2 or tokens[1][0] != 'ONLYNAME':
            raise ValueError(f"illegal path: {tokens}")
        if b_obj is None:
            b_obj = {}
        if len(tokens) == 2:
            b_obj[tokens[1][1]] = val
        else:
            b_obj[tokens[1][1]] = _set_obj_sub(
                b_obj.get(tokens[1][1]), tokens[2:], val)
    elif tokens[0][0] == 'LBRACKET':  # array start
        if len(tokens) < 2:
            raise ValueError(f"illegal path: {tokens}")
        if tokens[1][0] == 'ARRNUMBER':
            if len(tokens) < 3 or tokens[2][0] != 'RBRACKET':
                raise ValueError(f"illegal path: {tokens}")
            arr_idx = int(tokens[1][1])
            if b_obj is None:
                b_obj = []
            if len(b_obj) < (arr_idx + 1):
                for i in range((arr_idx + 1) - len(b_obj)):
                    _ = i
                    b_obj.append({})
            if len(tokens) == 3:
                b_obj[arr_idx] = val
            else:
                b_obj[arr_idx] = _set_obj_sub(b_obj[arr_idx], tokens[3:], val)
        elif tokens[1][0] == 'RBRACKET':
            if b_obj is not None and isinstance(b_obj, list):
                for i_obj in b_obj:
                    if len(tokens) == 2:
                        i_obj = val
                    else:
                        i_obj = _set_obj_sub(i_obj, tokens[2:], val)
        else:
            raise ValueError(f"illegal path: {tokens}")
    else:
        raise ValueError(f"illegal path: {tokens}")

    return b_obj


def get_obj_with_path(body: Dict, path: str) -> Any:
    """get_obj_with_path"""
    tokens = tokenize(path, BODY_RULE_TOKEN_TYPES)
    if len(tokens) == 0:
        raise ValueError(f"illegal path: {path}")
    if tokens[0][0] != 'ONLYNAME':  # first member is to be ONLYNAME
        raise ValueError(f"illegal path: {path}")

    t_obj = body.get(tokens[0][1])

    if t_obj is None or len(tokens) == 1:
        return t_obj

    return _get_obj_sub(t_obj, tokens[1:])


def _get_obj_sub(b_obj: Any, tokens: List) -> Any:
    """_get_obj_sub"""
    if b_obj is None:
        return None
    if tokens[0][0] == 'SUBMEMBER':  # submembers
        if len(tokens) < 2 or tokens[1][0] != 'ONLYNAME':
            raise ValueError(f"illegal path: {tokens}")
        if isinstance(b_obj, dict) is False:
            raise ValueError(f"illegal object (not dict): {b_obj}")
        if len(tokens) == 2:
            return b_obj[tokens[1][1]]
        return _get_obj_sub(b_obj.get(tokens[1][1]), tokens[2:])
    if tokens[0][0] == 'LBRACKET':  # array start
        if isinstance(b_obj, list) is False:
            raise ValueError(f"illegal object (not list): {b_obj}")
        if len(tokens) < 2:
            raise ValueError(f"illegal path: {tokens}")
        if tokens[1][0] == 'ARRNUMBER':
            if len(tokens) < 3 or tokens[2][0] != 'RBRACKET':
                raise ValueError(f"illegal path: {tokens}")
            arr_idx = int(tokens[1][1])
            if len(b_obj) < (arr_idx + 1):
                raise ValueError(f"illegal object (list length): {tokens}")
            if len(tokens) == 3:
                return b_obj[arr_idx]
            return _get_obj_sub(b_obj[arr_idx], tokens[3:])
        if tokens[1][0] == 'RBRACKET':
            if b_obj is not None and isinstance(b_obj, list):
                r_obj = []
                for i_obj in b_obj:
                    if len(tokens) == 2:
                        r_obj.append(i_obj)
                    else:
                        r_obj.append(_get_obj_sub(i_obj, tokens[2:]))
                return r_obj
            raise ValueError(f"illegal object (list obj): {tokens}")

    raise ValueError(f"illegal path: {tokens}")

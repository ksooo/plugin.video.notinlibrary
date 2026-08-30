# -*- coding: utf-8 -*-
#
#  Copyright (C) 2026 ksooo
#  This file is part of Not in Library
#
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt for more information.
#
"""Minimal wrapper around Kodi's built-in JSON-RPC interface."""

import json

import xbmc

from . import addon


def execute(method, params=None):
    """Execute a JSON-RPC method.

    Returns the "result" member of the response, or None if the call failed.
    An empty result is returned as an empty dict, so callers can distinguish
    "nothing found" from "call failed".
    """
    request = {'jsonrpc': '2.0', 'id': 1, 'method': method}
    if params is not None:
        request['params'] = params

    raw_response = xbmc.executeJSONRPC(json.dumps(request))
    try:
        response = json.loads(raw_response)
    except ValueError:
        addon.log_error('{}: response is not valid JSON: {}'.format(method, raw_response))
        return None

    error = response.get('error')
    if error is not None:
        # Unreachable or non-existing paths are reported as InvalidParams. This is
        # an expected condition while walking sources, hence no error level here.
        addon.log('{} failed: {}'.format(method, error))
        return None

    return response.get('result', {})

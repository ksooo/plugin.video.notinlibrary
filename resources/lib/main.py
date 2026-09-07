# -*- coding: utf-8 -*-
#
#  Copyright (C) 2026 ksooo
#  This file is part of Not in Library
#
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt for more information.
#
"""Entry point of the Not in Library add-on."""

from .router import Router


def run(argv):
    """Dispatch the plugin call described by argv."""
    Router(argv).dispatch()

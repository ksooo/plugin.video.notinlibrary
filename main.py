# -*- coding: utf-8 -*-
#
#  Copyright (C) 2026 ksooo
#  This file is part of Not in Library
#
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt for more information.
#
"""Entry point of the Not in Library add-on."""

import sys

from resources.lib.router import Router

if __name__ == '__main__':
    Router(sys.argv).dispatch()

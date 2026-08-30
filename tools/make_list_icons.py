#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#  Copyright (C) 2026 ksooo
#  This file is part of Not in Library
#
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt for more information.
#
"""Generate the icons of the two top level entries.

They are a plus and a cross, deliberately built from the same geometry so that
they read as a pair. The measurements are taken from Kodi's own
DefaultAddSource.png (256x256, bars 122 long and 28 thick), so the plus matches
what skins use for "add" while the cross keeps the exact same weight - which no
stock Default*.png offers.

Usage: python3 tools/make_list_icons.py [output directory]
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pngwriter import render, write_png  # noqa: E402

SIZE = 256
CENTRE = SIZE / 2.0

#: Taken from DefaultAddSource.png, see the module docstring.
BAR_LENGTH = 122.0
BAR_THICKNESS = 28.0

#: The cross has to fill the same square as the plus. A bar turned by 45
#: degrees spans (length + thickness) / sqrt(2), because its corners stick out
#: past the ends - so the thickness has to come off the diagonal length again.
DIAGONAL_BAR_LENGTH = BAR_LENGTH * math.sqrt(2.0) - BAR_THICKNESS

WHITE = (255, 255, 255)
TRANSPARENT = (0, 0, 0, 0)


def in_bar(x, y, length, thickness, angle):
    """Return whether the point lies inside a bar centred on the image."""
    delta_x = x - CENTRE
    delta_y = y - CENTRE
    cosine = math.cos(angle)
    sine = math.sin(angle)
    along = delta_x * cosine + delta_y * sine
    across = -delta_x * sine + delta_y * cosine
    return abs(along) <= length / 2.0 and abs(across) <= thickness / 2.0


def make_sample(angles, length):
    """Return a sample function drawing bars at the given angles."""
    def sample(x, y):
        if any(in_bar(x, y, length, BAR_THICKNESS, angle) for angle in angles):
            return WHITE[0], WHITE[1], WHITE[2], 255
        return TRANSPARENT
    return sample


def main():
    if len(sys.argv) > 1:
        directory = sys.argv[1]
    else:
        directory = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                 'resources', 'media')

    if not os.path.isdir(directory):
        os.makedirs(directory)

    icons = {
        # A plus, matching Kodi's DefaultAddSource.png.
        'not-imported.png': ((0.0, math.pi / 2.0), BAR_LENGTH),
        # The same plus turned by 45 degrees, filling the same square.
        'excluded.png': ((math.pi / 4.0, -math.pi / 4.0), DIAGONAL_BAR_LENGTH),
    }

    for file_name, (angles, length) in icons.items():
        path = os.path.join(directory, file_name)
        write_png(path, SIZE, SIZE, render(SIZE, SIZE, make_sample(angles, length)))
        print('wrote {} ({}x{})'.format(path, SIZE, SIZE))


if __name__ == '__main__':
    main()

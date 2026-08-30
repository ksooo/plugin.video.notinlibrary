#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#  Copyright (C) 2026 ksooo
#  This file is part of Not in Library
#
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt for more information.
#
"""Generate the add-on icon.

The icon shows a film strip behind a magnifying glass with a plus sign in it:
find videos and add them to the library. Everything is drawn from primitives
and written out as a PNG, so no third party imaging library is needed.

Usage: python3 tools/make_icon.py [output.png]
"""

import os
import struct
import sys
import zlib

SIZE = 512
SAMPLES_PER_AXIS = 4  # supersampling factor per axis, for anti-aliased edges

# Colours.
BACKGROUND_TOP = (0x1B, 0x27, 0x33)
BACKGROUND_BOTTOM = (0x0E, 0x16, 0x20)
STRIP = (0xEE, 0xF4, 0xF9)
FRAME = (0x22, 0x30, 0x3D)
ACCENT = (0x11, 0xE5, 0xFF)
GLASS = (0xFF, 0xFF, 0xFF)
GLASS_ALPHA = 0.12

# Film strip.
STRIP_LEFT, STRIP_RIGHT = 56.0, 456.0
STRIP_TOP, STRIP_BOTTOM = 150.0, 362.0
STRIP_RADIUS = 14.0
FRAME_TOP, FRAME_BOTTOM = 204.0, 308.0
PERFORATION_COUNT = 6
PERFORATION_WIDTH, PERFORATION_HEIGHT = 34.0, 30.0
PERFORATION_RADIUS = 7.0
PERFORATION_FIRST_LEFT = 72.0
PERFORATION_SPACING = 64.0
PERFORATION_TOP_Y = 162.0
PERFORATION_BOTTOM_Y = 320.0

# Magnifying glass.
GLASS_CENTRE_X, GLASS_CENTRE_Y = 300.0, 296.0
GLASS_INNER_RADIUS = 92.0
GLASS_OUTER_RADIUS = 118.0
HANDLE_START = (383.0, 379.0)
HANDLE_END = (446.0, 442.0)
HANDLE_RADIUS = 17.0
PLUS_ARM_LENGTH = 46.0
PLUS_ARM_WIDTH = 11.0


def in_rounded_rect(x, y, left, top, right, bottom, radius):
    """Return whether the point lies inside the given rounded rectangle."""
    if x < left or x > right or y < top or y > bottom:
        return False

    corner_x = min(max(x, left + radius), right - radius)
    corner_y = min(max(y, top + radius), bottom - radius)
    delta_x = x - corner_x
    delta_y = y - corner_y
    return delta_x * delta_x + delta_y * delta_y <= radius * radius


def in_circle(x, y, centre_x, centre_y, radius):
    """Return whether the point lies inside the given circle."""
    delta_x = x - centre_x
    delta_y = y - centre_y
    return delta_x * delta_x + delta_y * delta_y <= radius * radius


def in_capsule(x, y, start, end, radius):
    """Return whether the point lies inside the given round capped line."""
    span_x = end[0] - start[0]
    span_y = end[1] - start[1]
    length_squared = span_x * span_x + span_y * span_y
    position = ((x - start[0]) * span_x + (y - start[1]) * span_y) / length_squared
    position = min(1.0, max(0.0, position))
    delta_x = x - (start[0] + position * span_x)
    delta_y = y - (start[1] + position * span_y)
    return delta_x * delta_x + delta_y * delta_y <= radius * radius


def in_perforation(x, y):
    """Return whether the point lies inside one of the film strip sprocket holes."""
    for row_top in (PERFORATION_TOP_Y, PERFORATION_BOTTOM_Y):
        if not row_top <= y <= row_top + PERFORATION_HEIGHT:
            continue
        for index in range(PERFORATION_COUNT):
            left = PERFORATION_FIRST_LEFT + index * PERFORATION_SPACING
            if in_rounded_rect(x, y, left, row_top, left + PERFORATION_WIDTH,
                               row_top + PERFORATION_HEIGHT, PERFORATION_RADIUS):
                return True
    return False


def background_colour(y):
    """Return the vertical gradient colour of the background plate."""
    position = y / SIZE
    return tuple(int(round(top + (bottom - top) * position))
                 for top, bottom in zip(BACKGROUND_TOP, BACKGROUND_BOTTOM))


def blend(base, overlay, alpha):
    """Blend an opaque overlay colour onto an opaque base colour."""
    return tuple(int(round(base[i] + (overlay[i] - base[i]) * alpha)) for i in range(3))


def sample(x, y):
    """Return the RGBA colour of the icon at the given point."""
    # Square corners on purpose: add-on icons fill their tile, and Kodi rounds
    # them itself where a skin asks for it.
    colour = background_colour(y)

    # Film strip, with the sprocket holes punched back to the background.
    if in_rounded_rect(x, y, STRIP_LEFT, STRIP_TOP, STRIP_RIGHT, STRIP_BOTTOM, STRIP_RADIUS):
        if FRAME_TOP <= y <= FRAME_BOTTOM:
            colour = FRAME
        elif not in_perforation(x, y):
            colour = STRIP

    # Magnifying glass.
    if in_circle(x, y, GLASS_CENTRE_X, GLASS_CENTRE_Y, GLASS_OUTER_RADIUS):
        if in_circle(x, y, GLASS_CENTRE_X, GLASS_CENTRE_Y, GLASS_INNER_RADIUS):
            colour = blend(colour, GLASS, GLASS_ALPHA)
            in_horizontal_arm = (abs(x - GLASS_CENTRE_X) <= PLUS_ARM_LENGTH and
                                 abs(y - GLASS_CENTRE_Y) <= PLUS_ARM_WIDTH)
            in_vertical_arm = (abs(x - GLASS_CENTRE_X) <= PLUS_ARM_WIDTH and
                               abs(y - GLASS_CENTRE_Y) <= PLUS_ARM_LENGTH)
            if in_horizontal_arm or in_vertical_arm:
                colour = ACCENT
        else:
            colour = ACCENT
    elif in_capsule(x, y, HANDLE_START, HANDLE_END, HANDLE_RADIUS):
        colour = ACCENT

    return colour[0], colour[1], colour[2], 255


def render():
    """Render the icon and return it as a list of RGBA scan lines."""
    step = 1.0 / SAMPLES_PER_AXIS
    offset = step / 2.0
    sample_count = SAMPLES_PER_AXIS * SAMPLES_PER_AXIS

    rows = []
    for pixel_y in range(SIZE):
        row = bytearray()
        for pixel_x in range(SIZE):
            red = green = blue = alpha = 0
            for sub_y in range(SAMPLES_PER_AXIS):
                y = pixel_y + offset + sub_y * step
                for sub_x in range(SAMPLES_PER_AXIS):
                    x = pixel_x + offset + sub_x * step
                    sample_red, sample_green, sample_blue, sample_alpha = sample(x, y)
                    # Premultiplied, so that transparent samples do not darken the edge.
                    weight = sample_alpha / 255.0
                    red += sample_red * weight
                    green += sample_green * weight
                    blue += sample_blue * weight
                    alpha += sample_alpha

            if alpha == 0:
                row += b'\x00\x00\x00\x00'
                continue

            coverage = alpha / (sample_count * 255.0)
            row.append(min(255, int(round(red / sample_count / coverage))))
            row.append(min(255, int(round(green / sample_count / coverage))))
            row.append(min(255, int(round(blue / sample_count / coverage))))
            row.append(min(255, int(round(alpha / sample_count))))
        rows.append(bytes(row))
    return rows


def write_png(path, rows):
    """Write the given RGBA scan lines as an 8 bit truecolour PNG with alpha."""
    def chunk(tag, data):
        payload = tag + data
        return (struct.pack('>I', len(data)) + payload +
                struct.pack('>I', zlib.crc32(payload) & 0xFFFFFFFF))

    # Filter type 0 (none) in front of every scan line.
    raw = b''.join(b'\x00' + row for row in rows)

    with open(path, 'wb') as png:
        png.write(b'\x89PNG\r\n\x1a\n')
        png.write(chunk(b'IHDR', struct.pack('>IIBBBBB', SIZE, SIZE, 8, 6, 0, 0, 0)))
        png.write(chunk(b'IDAT', zlib.compress(raw, 9)))
        png.write(chunk(b'IEND', b''))


def main():
    if len(sys.argv) > 1:
        output_path = sys.argv[1]
    else:
        output_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                   'icon.png')

    write_png(output_path, render())
    print('wrote {} ({}x{})'.format(output_path, SIZE, SIZE))


if __name__ == '__main__':
    main()

# -*- coding: utf-8 -*-
#
#  Copyright (C) 2026 ksooo
#  This file is part of Not in Library
#
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt for more information.
#
"""Writing 8 bit RGBA PNGs without any third party imaging library."""

import struct
import zlib


def write_png(path, width, height, rows):
    """Write the given RGBA scan lines as an 8 bit truecolour PNG with alpha."""
    def chunk(tag, data):
        payload = tag + data
        return (struct.pack('>I', len(data)) + payload +
                struct.pack('>I', zlib.crc32(payload) & 0xFFFFFFFF))

    # Filter type 0 (none) in front of every scan line.
    raw = b''.join(b'\x00' + row for row in rows)

    with open(path, 'wb') as png:
        png.write(b'\x89PNG\r\n\x1a\n')
        png.write(chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)))
        png.write(chunk(b'IDAT', zlib.compress(raw, 9)))
        png.write(chunk(b'IEND', b''))


def render(width, height, sample, samples_per_axis=4):
    """Render an image by supersampling the given sample(x, y) -> (r, g, b, a).

    Returns a list of RGBA scan lines. Sampling several times per pixel is what
    gives the shapes smooth edges.
    """
    step = 1.0 / samples_per_axis
    offset = step / 2.0
    sample_count = samples_per_axis * samples_per_axis

    rows = []
    for pixel_y in range(height):
        row = bytearray()
        for pixel_x in range(width):
            red = green = blue = alpha = 0
            for sub_y in range(samples_per_axis):
                y = pixel_y + offset + sub_y * step
                for sub_x in range(samples_per_axis):
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

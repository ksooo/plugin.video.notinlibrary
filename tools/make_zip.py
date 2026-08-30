#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#  Copyright (C) 2026 ksooo
#  This file is part of Not in Library
#
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt for more information.
#
"""Build the installable add-on zip next to the add-on directory.

Kodi expects an archive holding a single top level directory named exactly like
the add-on id, so that is what the paths inside the archive look like.

Usage: python3 tools/make_zip.py
"""

import os
import sys
import xml.etree.ElementTree as ElementTree
import zipfile

#: Directories that are development material rather than part of the add-on.
EXCLUDED_DIRECTORIES = frozenset((
    '.git',
    '__pycache__',
    'tests',
    'tools',
))

#: Files that have no business in an installable add-on.
EXCLUDED_FILES = frozenset((
    '.DS_Store',
    '.gitignore',
))

#: Suffixes that have no business in an installable add-on.
EXCLUDED_SUFFIXES = ('.pyc', '.pyo', '.tmp')


def is_excluded(relative_path):
    """Return whether the given add-on relative path stays out of the archive."""
    parts = relative_path.split(os.sep)
    if any(part in EXCLUDED_DIRECTORIES for part in parts[:-1]):
        return True

    name = parts[-1]
    return name in EXCLUDED_FILES or name.endswith(EXCLUDED_SUFFIXES)


def collect(addon_directory):
    """Return the add-on relative paths of everything belonging into the archive."""
    collected = []
    for root, directories, files in os.walk(addon_directory):
        # Pruning here keeps os.walk out of the excluded trees entirely.
        directories[:] = sorted(d for d in directories if d not in EXCLUDED_DIRECTORIES)

        for name in sorted(files):
            relative_path = os.path.relpath(os.path.join(root, name), addon_directory)
            if not is_excluded(relative_path):
                collected.append(relative_path)
    return collected


def read_version(addon_directory):
    """Return the add-on version from addon.xml."""
    tree = ElementTree.parse(os.path.join(addon_directory, 'addon.xml'))
    version = tree.getroot().get('version')
    if not version:
        raise SystemExit('addon.xml has no version attribute')
    return version


def main():
    addon_directory = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    addon_id = os.path.basename(addon_directory)
    archive_path = os.path.join(os.path.dirname(addon_directory),
                                '{}-{}.zip'.format(addon_id, read_version(addon_directory)))

    paths = collect(addon_directory)
    with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as archive:
        for relative_path in paths:
            archive.write(os.path.join(addon_directory, relative_path),
                          os.path.join(addon_id, relative_path))

    print('wrote {} ({} files)'.format(archive_path, len(paths)))
    return 0


if __name__ == '__main__':
    sys.exit(main())

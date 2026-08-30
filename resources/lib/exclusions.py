# -*- coding: utf-8 -*-
#
#  Copyright (C) 2026 ksooo
#  This file is part of Not in Library
#
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt for more information.
#
"""Persistent list of videos that shall never enter the video library.

Both single files and whole directories can be excluded; excluding a directory
covers everything below it. The list is stored per profile, in the add-on data
directory of the profile that is active when the add-on runs. Paths are
compared verbatim, because that is exactly the form Kodi reports them in.
"""

import json
import os

import xbmcvfs

from . import addon
from . import library
from . import scanner

FILE_NAME = 'exclusions.json'

#: Bumped whenever the on disk layout changes in an incompatible way.
#: Version 1 knew only files, stored in a flat "paths" list.
FORMAT_VERSION = 2


#: Defined in scanner, where the path helpers live.
as_directory = scanner.as_directory


class ExclusionList:
    """The excluded files and directories of one profile."""

    def __init__(self, files=None, directories=None):
        self.files = set(files or ())
        self.directories = set(directories or ())

    def __bool__(self):
        return bool(self.files or self.directories)

    def __eq__(self, other):
        return (isinstance(other, ExclusionList) and self.files == other.files
                and self.directories == other.directories)

    def __repr__(self):
        return 'ExclusionList(files={!r}, directories={!r})'.format(
            sorted(self.files), sorted(self.directories))

    def contains(self, path):
        """Return whether the given file or directory is excluded.

        True either when the path was excluded itself, or when any of its
        parent directories was.
        """
        if path in self.files:
            return True

        # Comparing the directory form of the path covers three cases at once:
        # the path is an excluded directory, it lies below one, or it is a file
        # below one.
        candidate = as_directory(path)
        return any(candidate.startswith(directory) for directory in self.directories)

    def drop_covered_by(self, directory):
        """Remove all entries that the given directory now covers anyway."""
        self.files = {path for path in self.files if not path.startswith(directory)}
        self.directories = {path for path in self.directories
                            if path == directory or not path.startswith(directory)}

    def find_covering_directory(self, path):
        """Return the excluded directory that covers the given path, if any.

        The path itself being excluded does not count as being covered.
        """
        candidate = as_directory(path)
        covering = [directory for directory in self.directories
                    if candidate.startswith(directory) and directory != candidate]
        # There should only ever be one, see drop_covered_by(), but the most
        # specific one is the right answer in any case.
        return max(covering, key=len) if covering else None

    def has_entries_below(self, path):
        """Return whether anything at or below the given path is excluded."""
        prefix = as_directory(path)
        return (any(entry.startswith(prefix) for entry in self.files)
                or any(entry.startswith(prefix) for entry in self.directories))

    def children_of(self, parent):
        """Return the direct children of parent that lead to an exclusion.

        The result is a (directories, files) pair. directories maps a path to
        whether that directory is excluded itself; the ones mapping to False are
        merely the intermediate directories on the way to an exclusion further
        down. files is a list of (name, path) pairs.

        This rebuilds the directory structure purely from the stored paths, so
        browsing the exclusions needs no directory listings at all.
        """
        prefix = as_directory(parent)
        directories = {}
        files = []

        for path in self.files:
            if not path.startswith(prefix):
                continue
            name, separator, _ = path[len(prefix):].partition('/')
            if separator:
                directories.setdefault(prefix + name + '/', False)
            else:
                files.append((name, path))

        for path in self.directories:
            if path == prefix or not path.startswith(prefix):
                continue
            name, _, remainder = path[len(prefix):].partition('/')
            if remainder:
                directories.setdefault(prefix + name + '/', False)
            else:
                # The child is excluded itself, which outranks being a mere
                # intermediate directory.
                directories[prefix + name + '/'] = True

        return directories, files


def get_directory():
    """Return the add-on data directory of the active profile."""
    return xbmcvfs.translatePath(addon.ADDON.getAddonInfo('profile'))


def get_file_path():
    """Return the full path of the file holding the exclusions."""
    return os.path.join(get_directory(), FILE_NAME)


def load():
    """Return the stored exclusions.

    A missing or unreadable file yields an empty list, so a damaged file never
    keeps the add-on from working.
    """
    file_path = get_file_path()
    if not os.path.isfile(file_path):
        return ExclusionList()

    try:
        with open(file_path, 'r', encoding='utf-8') as stream:
            content = json.load(stream)
    except (OSError, ValueError) as error:
        addon.log_error('could not read {}: {}'.format(file_path, error))
        return ExclusionList()

    if not isinstance(content, dict):
        addon.log_error('unsupported content in {}'.format(file_path))
        return ExclusionList()

    version = content.get('version')
    if version == 1:
        return ExclusionList(files=content.get('paths'))
    if version == FORMAT_VERSION:
        return ExclusionList(files=content.get('files'),
                             directories=content.get('directories'))

    addon.log_error('unsupported format version {} in {}'.format(version, file_path))
    return ExclusionList()


def save(exclusion_list):
    """Persist the given exclusions. Returns whether that succeeded."""
    file_path = get_file_path()
    content = {'version': FORMAT_VERSION,
               'files': sorted(exclusion_list.files),
               'directories': sorted(exclusion_list.directories)}

    try:
        directory = get_directory()
        if not os.path.isdir(directory):
            os.makedirs(directory)

        # Write to a temporary file and move it into place, so an interrupted
        # write cannot leave a truncated list behind.
        temporary_path = file_path + '.tmp'
        with open(temporary_path, 'w', encoding='utf-8') as stream:
            json.dump(content, stream, indent=2)
        os.replace(temporary_path, file_path)
    except OSError as error:
        addon.log_error('could not write {}: {}'.format(file_path, error))
        return False

    return True


def add_file(path):
    """Exclude the given file. Returns whether that succeeded."""
    current = load()
    if current.contains(path):
        return True

    current.files.add(path)
    return save(current)


def add_directory(path):
    """Exclude the given directory and everything below it.

    Returns whether that succeeded.
    """
    current = load()
    directory = as_directory(path)
    if directory in current.directories:
        return True

    current.directories.add(directory)
    # Entries below the new directory would only clutter the listing now.
    current.drop_covered_by(directory)
    return save(current)


def remove(path):
    """Allow the given file or directory to be imported again.

    Returns whether that succeeded.
    """
    current = load()
    directory = as_directory(path)

    # The straightforward case: the path is in the list itself.
    if path in current.files or directory in current.directories:
        current.files.discard(path)
        current.directories.discard(directory)
        return save(current)

    # The path is covered by an excluded parent directory. That exclusion has
    # to be dissolved so that everything except this path stays excluded.
    ancestor = current.find_covering_directory(path)
    if ancestor is not None:
        if not _dissolve(current, ancestor, path):
            return False
        return save(current)

    # An intermediate directory on the way to exclusions further down: undoing
    # it frees the whole subtree, mirroring how excluding a directory works.
    if current.has_entries_below(path):
        current.drop_covered_by(directory)
        current.directories.discard(directory)
        return save(current)

    return True


def _dissolve(exclusion_list, ancestor, target):
    """Replace the exclusion of ancestor by explicit exclusions of everything
    beside the path leading down to target.

    Returns whether every directory on the way could be read.
    """
    exclusion_list.directories.discard(ancestor)
    known = library.load()

    current_directory = ancestor
    remainder = target[len(ancestor):]
    while remainder:
        name, separator, remainder = remainder.partition('/')
        child = current_directory + name + separator

        entries = scanner.list_directory(current_directory, known)
        if entries is None:
            addon.log_error('could not read {} while dissolving the exclusion of {}'.format(
                current_directory, ancestor))
            return False

        for entry in entries:
            if as_directory(entry.path) == as_directory(child):
                continue
            # Files that already are in the video library never show up as
            # missing anyway, so excluding them would only clutter the list.
            # For a directory the flag means something else entirely, see
            # scanner.LIBRARY_DIRECTORY_TYPES, so it must not be skipped.
            if not entry.is_folder and entry.in_library:
                continue

            if entry.is_folder:
                exclusion_list.directories.add(as_directory(entry.path))
            else:
                exclusion_list.files.add(entry.path)

        current_directory = child

    return True

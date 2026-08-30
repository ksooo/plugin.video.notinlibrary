# -*- coding: utf-8 -*-
#
#  Copyright (C) 2026 ksooo
#  This file is part of Not in Library
#
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt for more information.
#
"""The set of file paths that the video library knows about.

Fetched once per invocation, see scanner for why not per item.
"""

from . import jsonrpc
from . import scanner

#: The library methods to ask, with the member holding their result.
METHODS = (
    ('VideoLibrary.GetMovies', 'movies'),
    ('VideoLibrary.GetEpisodes', 'episodes'),
    ('VideoLibrary.GetMusicVideos', 'musicvideos'),
)

STACK_PREFIX = 'stack://'

#: Separator between the parts of a stack path, see CStackDirectory::GetPaths().
STACK_SEPARATOR = ' , '


def split_stack(path):
    """Return the files a stack path is made of, or the path itself.

    A stacked movie is one library entry spanning several files, and every one
    of them has to count as known.
    """
    if not path.startswith(STACK_PREFIX):
        return [path]

    # Commas inside a path are doubled, which is what makes " , " usable as
    # the separator in the first place.
    return [part.replace(',,', ',')
            for part in path[len(STACK_PREFIX):].split(STACK_SEPARATOR) if part]


class VideoLibrary:
    """The file paths that have a video library entry."""

    def __init__(self, paths=None):
        self.paths = set(paths or ())

    def __len__(self):
        return len(self.paths)

    def contains(self, path):
        """Return whether the given file is part of the video library."""
        return path in self.paths

    def has_entry_below(self, directory):
        """Return whether any library entry lives at or below the given directory.

        Used for disc folders, where the entry is a file deep inside the folder
        rather than the folder itself.
        """
        prefix = scanner.as_directory(directory)
        return any(path.startswith(prefix) for path in self.paths)


def load():
    """Return the paths of every movie, episode and music video."""
    paths = set()
    for method, member in METHODS:
        result = jsonrpc.execute(method, {'properties': ['file']})
        if result is None:
            continue

        for item in result.get(member) or []:
            path = item.get('file')
            if path:
                paths.update(split_stack(path))

    return VideoLibrary(paths)

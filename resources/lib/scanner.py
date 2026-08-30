# -*- coding: utf-8 -*-
#
#  Copyright (C) 2026 ksooo
#  This file is part of Not in Library
#
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt for more information.
#
"""Discovery of video files that have no entry in the video library.

Directories are listed with media "files". The obvious choice, media "video",
cannot be used: it resolves every item against the video database, and since
CVideoDatabase::GetMovieId() falls back to "any movie whose file lives in this
path" for a directory, Kodi replaces a folder holding an imported movie by that
movie. The folder and everything below it then never appear in the answer.

Extension filtering and library matching therefore happen here, see library.py.
"""

import collections
import re

import xbmc

from . import addon
from . import jsonrpc

#: Subdirectories that turn their parent into a single medium rather than a
#: directory holding videos.
DISC_STRUCTURE_NAMES = frozenset(('bdmv', 'video_ts'))

#: Protocols that can never be scanned into the video library.
#:
#: "plugin" is deliberately absent: an add-on can declare medialibraryscanpath
#: in its addon.xml, and Kodi then does scan its paths - see
#: CPluginDirectory::IsMediaLibraryScanningAllowed(). Plugin sources are
#: therefore walked like any other.
NON_SCANNABLE_PROTOCOLS = frozenset((
    'addons',
    'androidapp',
    'bluray',
    'cdda',
    'dvd',
    'favourites',
    'image',
    'library',
    'musicdb',
    'pvr',
    'resource',
    'rss',
    'script',
    'sources',
    'upnp',
    'videodb',
))

#: Paths of pseudo sources Kodi adds by itself. They hold playlists rather than
#: media files, but playlist extensions are part of the video extensions, so
#: they cannot be told apart by protocol alone. Stored without a trailing
#: slash, see normalize_path().
NON_SCANNABLE_PATHS = frozenset((
    'special://musicplaylists',
    'special://videoplaylists',
))

#: Protocols addressing something on the machine Kodi runs on. Everything else
#: that carries a protocol is treated as remote, mirroring URIUtils::IsRemote().
LOCAL_PROTOCOLS = frozenset((
    'file',
    'resource',
    'special',
    'win-lib',
))

#: Icons Kodi shows for sources of these protocols, see
#: CSourcesDirectory::GetDirectory(). Everything else is decided by whether the
#: path is local or remote.
SOURCE_ICONS_BY_PROTOCOL = {
    'bluray': 'DefaultBluray.png',
    'cdda': 'DefaultCDDA.png',
    'dvd': 'DefaultDVDFull.png',
    'iso9660': 'DefaultDVDRom.png',
    'plugin': 'DefaultFolder.png',
    'udf': 'DefaultDVDRom.png',
}

#: Safety net against pathologically deep or cyclic directory trees.
MAX_DEPTH = 32

_PROTOCOL_PATTERN = re.compile(r'^([A-Za-z][A-Za-z0-9+.\-]*)://')

#: Filled on first use, see get_video_extensions().
_video_extensions = None

#: A single item of a directory listing.
#:
#: label      - the display name as determined by Kodi
#: path       - the full path of the item
#: is_folder  - whether the item is a directory
#: in_library - whether the item has a matching video library entry
DirectoryEntry = collections.namedtuple(
    'DirectoryEntry', ('label', 'path', 'is_folder', 'in_library'))


def as_directory(path):
    """Return the path in the trailing separator form Kodi uses for directories.

    The trailing separator is what makes a prefix comparison safe: without it,
    ".../movies" would also match ".../movies extra".
    """
    return path if path.endswith(('/', '\\')) else path + '/'


def get_video_extensions():
    """Return the file extensions Kodi counts as video.

    Same source Files.GetDirectory uses for media "video", so the listing holds
    exactly the files Kodi would have offered.
    """
    global _video_extensions
    if _video_extensions is None:
        _video_extensions = frozenset(
            extension for extension in xbmc.getSupportedMedia('video').split('|') if extension)
    return _video_extensions


def has_video_extension(path):
    """Return whether the given file is a video by its extension."""
    name = get_file_name(path)
    separator = name.rfind('.')
    return separator >= 0 and name[separator:].lower() in get_video_extensions()


def get_file_name(path):
    """Return the last segment of the given path."""
    return path.rstrip('/\\').replace('\\', '/').rpartition('/')[2]


def is_disc_folder(entries):
    """Return whether the given listing is that of a DVD or Blu-ray folder."""
    return any(entry.is_folder and get_file_name(entry.path).lower() in DISC_STRUCTURE_NAMES
               for entry in entries)


def get_protocol(path):
    """Return the protocol of the given path, or an empty string for local paths."""
    match = _PROTOCOL_PATTERN.match(path)
    return match.group(1).lower() if match else ''


def normalize_path(path):
    """Return a path in a form suitable for comparing two paths."""
    return path.rstrip('/\\').lower()


def is_scannable(path):
    """Return whether the given path can end up in the video library at all."""
    if get_protocol(path) in NON_SCANNABLE_PROTOCOLS:
        return False
    return normalize_path(path) not in NON_SCANNABLE_PATHS


def get_source_icon(path):
    """Return the icon Kodi shows for a source with the given path.

    Files.GetSources reports no artwork, so the choice CSourcesDirectory makes
    is reproduced here to keep the sources looking the way they do everywhere
    else in Kodi.
    """
    protocol = get_protocol(path)
    if protocol in SOURCE_ICONS_BY_PROTOCOL:
        return SOURCE_ICONS_BY_PROTOCOL[protocol]

    if not protocol or protocol in LOCAL_PROTOCOLS:
        return 'DefaultHardDisk.png'

    return 'DefaultNetwork.png'


def get_video_sources():
    """Return the video sources of the active profile as a list of DirectoryEntry.

    Returns None if the sources could not be retrieved.
    """
    result = jsonrpc.execute('Files.GetSources', {'media': 'video'})
    if result is None:
        return None

    sources = []
    for source in result.get('sources') or []:
        path = source.get('file')
        if not path:
            continue
        sources.append(DirectoryEntry(label=source.get('label') or path,
                                      path=path,
                                      is_folder=True,
                                      in_library=False))
    return sources


def find_source_for(path):
    """Return the video source the given path lies in, or None.

    Needed to name the source in a breadcrumb: its name is an alias chosen by
    the user and cannot be derived from the path itself.
    """
    sources = get_video_sources()
    if not sources:
        return None

    candidate = normalize_path(path)
    matches = []
    for source in sources:
        prefix = normalize_path(source.path)
        # The separator keeps ".../videos" from matching ".../videos extra".
        if candidate == prefix or candidate.startswith(prefix + '/'):
            matches.append(source)

    return max(matches, key=lambda source: len(source.path)) if matches else None


def list_directory(path, library):
    """Return the contents of the given directory as a list of DirectoryEntry.

    Only directories and video files are returned. Returns None if the
    directory could not be read.
    """
    params = {
        'directory': path,
        'media': 'files',
        'properties': ['file'],
        'sort': {'method': 'label', 'order': 'ascending', 'ignorearticle': False},
    }
    result = jsonrpc.execute('Files.GetDirectory', params)
    if result is None:
        return None

    entries = []
    for item in result.get('files') or []:
        item_path = item.get('file')
        if not item_path:
            continue

        is_folder = item.get('filetype') == 'directory'
        if not is_folder and not has_video_extension(item_path):
            continue

        entries.append(DirectoryEntry(label=item.get('label') or item_path,
                                      path=item_path,
                                      is_folder=is_folder,
                                      in_library=library.contains(item_path)))

    return entries


def has_missing_videos(path, context):
    """Return whether the directory tree below the given path holds any video
    that is missing from the video library and is not excluded by the user.

    The descent stops at the first hit, so this is cheap for trees that do
    contain missing videos and expensive only for those that do not.
    """
    return _descend(path, context, set(), 0)


def _descend(path, context, visited, depth):
    """Recursive worker of has_missing_videos()."""
    if depth > MAX_DEPTH:
        addon.log('maximum depth reached at {}'.format(path))
        return False

    if context.is_cancelled():
        return False

    # Guard against directory loops created by symbolic links.
    marker = normalize_path(path)
    if marker in visited:
        return False
    visited.add(marker)

    context.report(path)

    entries = list_directory(path, context.library)
    if entries is None:
        return False

    if is_disc_folder(entries):
        # One medium, not a directory holding videos. Descending would offer
        # up its VOB and IFO files as missing videos one by one. The library
        # entry is a file deep inside the folder, hence has_entry_below().
        return not context.library.has_entry_below(path)

    subdirectories = []
    for entry in entries:
        if context.is_excluded(entry.path):
            continue

        if entry.is_folder:
            if is_scannable(entry.path):
                subdirectories.append(entry)
        elif not entry.in_library:
            return True

    for entry in subdirectories:
        if _descend(entry.path, context, visited, depth + 1):
            return True

    return False

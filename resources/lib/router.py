# -*- coding: utf-8 -*-
#
#  Copyright (C) 2026 ksooo
#  This file is part of Not in Library
#
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt for more information.
#
"""Routing of plugin calls and assembly of the directory listings.

The add-on has two sides, both browsed the same way: the videos that are
missing from the video library, and the ones the user excluded from being
imported. The top level offers one entry per side, below each of them come the
video sources, and below those the directory structure.
"""

from urllib.parse import parse_qsl
from urllib.parse import urlencode

import xbmc
import xbmcgui
import xbmcplugin

from . import addon
from . import exclusions
from . import library
from . import scanner
from .scancontext import ScanContext

#: Show a listing. Parameters: mode, path. Without a mode the two sides are
#: listed, with a mode but no path the video sources of that side.
ACTION_LIST = 'list'
#: Exclude a single video from library import. Parameter: path.
ACTION_EXCLUDE_FILE = 'exclude'
#: Exclude a directory and everything below it. Parameter: path.
ACTION_EXCLUDE_DIRECTORY = 'excludedir'
#: Allow a previously excluded video or directory to be imported again. Parameter: path.
ACTION_INCLUDE = 'include'

#: The videos that have no video library entry yet.
MODE_MISSING = 'missing'
#: The videos the user excluded from library import.
MODE_EXCLUDED = 'excluded'

#: Icons for the entries below source level. Sources get the icon Kodi itself
#: uses for them, see scanner.get_source_icon().
FOLDER_ICON = 'DefaultFolder.png'
VIDEO_ICON = 'DefaultVideo.png'

#: Content of a listing whose entries carry an icon of their own. Skins only
#: draw ListItem.Icon when no content type is set - Estuary ties its icon
#: layout to "Container.Content()" - and Kodi leaves the video root empty for
#: exactly that reason. Anything else here would hide the source icons.
CONTENT_NONE = ''
CONTENT_VIDEOS = 'videos'

#: Separator between the breadcrumb parts, matching the one Kodi puts between
#: "Videos", the add-on name and the plugin category.
BREADCRUMB_SEPARATOR = ' / '

#: Appended to a directory that is excluded itself, telling it apart from one
#: that merely leads to excluded entries further down.
EXCLUDED_MARKER = ' (X)'


class Router:
    """Dispatches a single plugin invocation."""

    def __init__(self, argv):
        self._base_url = argv[0]
        self._handle = int(argv[1])
        self._params = dict(parse_qsl(argv[2].lstrip('?')))

    def dispatch(self):
        """Execute the action requested by the caller."""
        action = self._params.get('action', ACTION_LIST)
        path = self._params.get('path', '')

        if action == ACTION_LIST:
            self._list(self._params.get('mode', ''), path)
        elif action == ACTION_EXCLUDE_FILE:
            self._change_exclusions(path, exclusions.add_file, 30024)
        elif action == ACTION_EXCLUDE_DIRECTORY:
            self._change_exclusions(path, exclusions.add_directory, 30024)
        elif action == ACTION_INCLUDE:
            self._change_exclusions(path, exclusions.remove, 30027)
        else:
            addon.log_error('unknown action: {}'.format(action))
            xbmcplugin.endOfDirectory(self._handle, succeeded=False)

    # -- actions ------------------------------------------------------------

    def _list(self, mode, path):
        """Show the requested level of the requested side."""
        if mode == MODE_MISSING:
            self._list_missing(path)
        elif mode == MODE_EXCLUDED:
            self._list_excluded(path)
        elif not mode:
            self._list_modes()
        else:
            addon.log_error('unknown mode: {}'.format(mode))
            xbmcplugin.endOfDirectory(self._handle, succeeded=False)

    def _change_exclusions(self, path, change, error_label_id):
        """Apply the given change to the exclusion list and refresh the listing."""
        if not path:
            addon.log_error('exclusion change requested without a path')
            return

        addon.log('{} {}'.format(change.__name__, path))
        if not change(path):
            addon.notify(addon.localize(error_label_id))
            return

        # The item has to disappear from the listing it was invoked from.
        xbmc.executebuiltin('Container.Refresh')

    # -- top level ----------------------------------------------------------

    def _list_modes(self):
        """Show the two sides of the add-on."""
        items = [
            self._make_mode_item(MODE_MISSING, 30026, addon.media_path('not-imported.png')),
            self._make_mode_item(MODE_EXCLUDED, 30022, addon.media_path('excluded.png')),
        ]
        self._finish(items, CONTENT_NONE, addon.ADDON_NAME)

    # -- videos missing from the library ------------------------------------

    def _list_missing(self, path):
        """Show the sources or the directory contents of the missing side."""
        show_progress = addon.get_bool_setting(addon.SETTING_SHOW_PROGRESS)

        with ScanContext(addon.localize(30011), show_progress,
                         exclusions.load(), library.load()) as context:
            if path:
                self._list_missing_directory(path, context)
            else:
                self._list_missing_sources(context)

    def _list_missing_sources(self, context):
        """Show the video sources that hold videos missing from the library."""
        sources = scanner.get_video_sources()
        if not sources:
            addon.show_message(addon.localize(30012), addon.localize(30013))
            xbmcplugin.endOfDirectory(self._handle, succeeded=False)
            return

        sources = [source for source in sources
                   if scanner.is_scannable(source.path) and not context.is_excluded(source.path)]

        items = []
        for index, source in enumerate(sources):
            if context.is_cancelled():
                break
            context.set_progress(index, len(sources))
            if scanner.has_missing_videos(source.path, context):
                items.append(self._make_missing_directory_item(
                    source, scanner.get_source_icon(source.path)))


        if context.cancelled:
            addon.notify(addon.localize(30018))
        elif not items:
            # Nothing to show. Reporting failure keeps Kodi where it is instead
            # of opening an empty listing.
            addon.notify(addon.localize(30014))
            xbmcplugin.endOfDirectory(self._handle, succeeded=False)
            return

        self._finish(items, CONTENT_NONE, addon.localize(30026))

    def _list_missing_directory(self, path, context):
        """Show the missing videos and the interesting subdirectories of a directory."""
        entries = scanner.list_directory(path, context.library)
        if entries is None:
            addon.notify(path, addon.localize(30017))
            xbmcplugin.endOfDirectory(self._handle, succeeded=False)
            return

        # Only has_missing_videos() can tell whether a directory holds anything,
        # and only after looking inside.
        candidates = [entry for entry in entries
                      if entry.is_folder
                      and not context.is_excluded(entry.path)
                      and scanner.is_scannable(entry.path)]

        directory_items = []
        for index, entry in enumerate(candidates):
            if context.is_cancelled():
                break
            context.set_progress(index, len(candidates))
            if scanner.has_missing_videos(entry.path, context):
                directory_items.append(self._make_missing_directory_item(entry))

        file_items = [self._make_missing_file_item(entry) for entry in entries
                      if not entry.is_folder and not entry.in_library
                      and not context.is_excluded(entry.path)]

        if context.cancelled:
            addon.notify(addon.localize(30018))

        self._finish(directory_items + file_items, CONTENT_VIDEOS,
                     self._build_breadcrumb(30026, path))

    # -- videos excluded from library import --------------------------------

    def _list_excluded(self, path):
        """Show the sources or the directory contents of the excluded side."""
        excluded = exclusions.load()
        if not path:
            self._list_excluded_sources(excluded)
        elif excluded.contains(path):
            self._list_inside_excluded_directory(path)
        else:
            self._list_excluded_directory(path, excluded)

    def _list_excluded_sources(self, excluded):
        """Show the video sources that hold excluded entries."""
        sources = scanner.get_video_sources()
        if not sources:
            addon.show_message(addon.localize(30012), addon.localize(30013))
            xbmcplugin.endOfDirectory(self._handle, succeeded=False)
            return

        items = [self._make_excluded_directory_item(source.path, source.label,
                                                    scanner.get_source_icon(source.path),
                                                    excluded.contains(source.path))
                 for source in sources if excluded.has_entries_below(source.path)]
        if not items:
            addon.notify(addon.localize(30023))
            xbmcplugin.endOfDirectory(self._handle, succeeded=False)
            return

        self._finish(items, CONTENT_NONE, addon.localize(30022))

    def _list_excluded_directory(self, path, excluded):
        """Show the excluded entries below the given directory.

        The structure comes from the stored paths alone, so this needs no
        directory listing and works even while the source is offline.
        """
        directories, files = excluded.children_of(path)

        items = [self._make_excluded_directory_item(child, child.rstrip('/').rpartition('/')[2],
                                                    excluded_itself=is_excluded)
                 for child, is_excluded in sorted(directories.items())]
        items += [self._make_excluded_file_item(name, child) for name, child in sorted(files)]

        self._finish(items, CONTENT_VIDEOS, self._build_breadcrumb(30022, path))

    def _list_inside_excluded_directory(self, path):
        """Show the real contents of an excluded directory.

        Everything below an excluded directory is excluded along with it, so
        the plain listing is what has to be shown. Undoing the exclusion of one
        of these entries dissolves the exclusion of the directory carrying it,
        see exclusions.remove().
        """
        # The library status is irrelevant here, everything below an excluded
        # directory is excluded regardless.
        entries = scanner.list_directory(path, library.VideoLibrary())
        if entries is None:
            addon.notify(path, addon.localize(30017))
            xbmcplugin.endOfDirectory(self._handle, succeeded=False)
            return

        items = [self._make_excluded_directory_item(entry.path, entry.label)
                 for entry in entries if entry.is_folder]
        items += [self._make_excluded_file_item(entry.label, entry.path)
                  for entry in entries if not entry.is_folder]

        self._finish(items, CONTENT_VIDEOS, self._build_breadcrumb(30022, path))

    def _build_breadcrumb(self, mode_label_id, path):
        """Build the breadcrumb of a directory level.

        Kodi puts "Videos / <add-on name> /" in front of it, so what is added
        here is the side, the source and every directory below it. The source
        has to be looked up because its name is an alias, not part of the path.
        """
        parts = [addon.localize(mode_label_id)]

        source = scanner.find_source_for(path)
        if source is None:
            # Should not happen, but showing the raw path beats showing nothing.
            parts.append(path)
            return BREADCRUMB_SEPARATOR.join(parts)

        parts.append(source.label)
        # Sliced by length rather than by prefix, since the source path and the
        # path may differ in case while addressing the very same directory.
        prefix = source.path if source.path.endswith(('/', '\\')) else source.path + '/'
        parts.extend(segment for segment in path[len(prefix):].split('/') if segment)

        return BREADCRUMB_SEPARATOR.join(parts)

    def _finish(self, items, content, category):
        """Hand the assembled listing over to Kodi."""
        xbmcplugin.setPluginCategory(self._handle, category)
        if content:
            xbmcplugin.setContent(self._handle, content)
        xbmcplugin.addDirectoryItems(self._handle, items, len(items))
        xbmcplugin.addSortMethod(self._handle, xbmcplugin.SORT_METHOD_UNSORTED)
        xbmcplugin.addSortMethod(self._handle, xbmcplugin.SORT_METHOD_LABEL)
        xbmcplugin.addSortMethod(self._handle, xbmcplugin.SORT_METHOD_FILE)
        # The listing is built from a live scan, so it must not be reused.
        xbmcplugin.endOfDirectory(self._handle, cacheToDisc=False)

    # -- list items ---------------------------------------------------------

    def _make_mode_item(self, mode, label_id, icon):
        """Build the listing tuple for one of the two sides."""
        list_item = xbmcgui.ListItem(label=addon.localize(label_id))
        list_item.setIsFolder(True)
        list_item.setArt({'icon': icon})

        return self._build_url(action=ACTION_LIST, mode=mode), list_item, True

    def _make_missing_directory_item(self, entry, icon=FOLDER_ICON):
        """Build the listing tuple for a source or subdirectory holding missing videos."""
        list_item = xbmcgui.ListItem(label=entry.label)
        list_item.setIsFolder(True)
        list_item.setArt({'icon': icon})
        list_item.addContextMenuItems(
            [self._make_context_menu_item(30020, ACTION_EXCLUDE_DIRECTORY, entry.path)])

        url = self._build_url(action=ACTION_LIST, mode=MODE_MISSING, path=entry.path)
        return url, list_item, True

    def _make_missing_file_item(self, entry):
        """Build the listing tuple for a video file that is missing from the library.

        Importing it is left to Kodi's own "Information" context menu entry,
        which scrapes exactly the selected file. The file items carry the real
        file path, so that entry finds the scraper configured for it.
        """
        list_item = self._make_video_list_item(entry.label, entry.path)
        list_item.addContextMenuItems(
            [self._make_context_menu_item(30020, ACTION_EXCLUDE_FILE, entry.path)])

        return entry.path, list_item, False

    def _make_excluded_directory_item(self, path, label, icon=FOLDER_ICON,
                                      excluded_itself=False):
        """Build the listing tuple for a directory on the excluded side.

        excluded_itself marks the directories that carry an exclusion of their
        own; the others are only on the way to one further down.
        """
        list_item = xbmcgui.ListItem(
            label=(label or path) + (EXCLUDED_MARKER if excluded_itself else ''))
        list_item.setIsFolder(True)
        list_item.setArt({'icon': icon})
        list_item.addContextMenuItems(
            [self._make_context_menu_item(30021, ACTION_INCLUDE, path)])

        url = self._build_url(action=ACTION_LIST, mode=MODE_EXCLUDED, path=path)
        return url, list_item, True

    def _make_excluded_file_item(self, label, path):
        """Build the listing tuple for a video file on the excluded side."""
        list_item = self._make_video_list_item(label, path)
        list_item.addContextMenuItems(
            [self._make_context_menu_item(30021, ACTION_INCLUDE, path)])

        return path, list_item, False

    def _make_video_list_item(self, label, path):
        """Build a playable list item for the video file at the given path."""
        list_item = xbmcgui.ListItem(label=label)
        list_item.setIsFolder(False)
        list_item.setProperty('IsPlayable', 'true')
        list_item.setArt({'icon': VIDEO_ICON})

        # Path only: a media type would hide Kodi's "Information" entry, and a
        # title would make ProcessItemByVideoInfoTag() match an episode by that
        # title instead of parsing the file name. The path keeps the tag
        # non-empty, which IsVisible() requires.
        info_tag = list_item.getVideoInfoTag()
        info_tag.setFilenameAndPath(path)

        return list_item

    def _make_context_menu_item(self, label_id, action, path):
        """Build a context menu entry running the given action on the given path."""
        url = self._build_url(action=action, path=path)
        return addon.localize(label_id), 'RunPlugin({})'.format(url)

    def _build_url(self, **kwargs):
        """Build a plugin url for the given parameters."""
        return '{}?{}'.format(self._base_url, urlencode(kwargs))

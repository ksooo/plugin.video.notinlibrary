# -*- coding: utf-8 -*-
#
#  Copyright (C) 2026 ksooo
#  This file is part of Not in Library
#
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt for more information.
#
"""State shared by all directory walks of a single add-on invocation."""

import time

import xbmc
import xbmcgui


class ScanContext:
    """Progress reporting, cancellation and policy for a directory walk.

    Meant to be used as a context manager so the progress dialogue is closed
    even if the walk is interrupted by an exception.
    """

    #: Minimum time between two progress dialogue updates, in seconds.
    UPDATE_INTERVAL = 0.25

    def __init__(self, heading, show_progress, excluded, library):
        self._heading = heading
        self._show_progress = show_progress
        self._excluded = excluded
        #: The video library paths, read by scanner.list_directory().
        self.library = library
        self._monitor = xbmc.Monitor()
        self._dialog = None
        self._percent = 0
        self._last_update = 0.0
        self._cancelled = False

    def __enter__(self):
        if self._show_progress:
            self._dialog = xbmcgui.DialogProgressBG()
            self._dialog.create(self._heading)
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        if self._dialog is not None:
            self._dialog.close()
            self._dialog = None
        return False

    @property
    def cancelled(self):
        """Whether the walk was cancelled. Only meaningful after the walk."""
        return self._cancelled

    def is_cancelled(self):
        """Return whether Kodi asked the add-on to stop."""
        if not self._cancelled and self._monitor.abortRequested():
            self._cancelled = True
        return self._cancelled

    def set_progress(self, done, total):
        """Set the overall progress, given as a fraction of completed items."""
        self._percent = int(done * 100 / total) if total > 0 else 0

    def report(self, path):
        """Show the directory that is currently being examined."""
        if self._dialog is None:
            return

        # Throttled, otherwise the dialogue update dominates the walk.
        now = time.monotonic()
        if now - self._last_update < self.UPDATE_INTERVAL:
            return
        self._last_update = now

        self._dialog.update(self._percent, self._heading, path)

    def is_excluded(self, path):
        """Return whether the user excluded the given file or directory."""
        return self._excluded.contains(path)

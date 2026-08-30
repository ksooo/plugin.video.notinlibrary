# -*- coding: utf-8 -*-
#
#  Copyright (C) 2026 ksooo
#  This file is part of Not in Library
#
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt for more information.
#
"""Thin convenience layer around the Kodi add-on API."""

import os

import xbmc
import xbmcaddon
import xbmcgui

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')
ADDON_NAME = ADDON.getAddonInfo('name')
ADDON_ICON = ADDON.getAddonInfo('icon')
ADDON_PATH = ADDON.getAddonInfo('path')

# Setting identifiers, must match resources/settings.xml.
SETTING_SHOW_PROGRESS = 'show_progress'


def localize(string_id):
    """Return the localised string with the given identifier."""
    return ADDON.getLocalizedString(string_id)


def media_path(file_name):
    """Return the full path of an image shipped with the add-on."""
    return os.path.join(ADDON_PATH, 'resources', 'media', file_name)


def get_bool_setting(setting_id):
    """Return the value of a boolean add-on setting."""
    return ADDON.getSettingBool(setting_id)


def log(message, level=xbmc.LOGDEBUG):
    """Write a message prefixed with the add-on id to the Kodi log."""
    xbmc.log('[{}] {}'.format(ADDON_ID, message), level)


def log_error(message):
    """Write an error message to the Kodi log."""
    log(message, xbmc.LOGERROR)


def notify(message, heading=None, time=5000):
    """Show a notification toast."""
    xbmcgui.Dialog().notification(heading or ADDON_NAME, message, ADDON_ICON, time)


def show_message(heading, message):
    """Show a modal dialogue with an OK button."""
    xbmcgui.Dialog().ok(heading, message)

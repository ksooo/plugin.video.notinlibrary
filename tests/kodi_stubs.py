"""Minimal xbmc* module stubs so the add-on can be exercised outside Kodi."""

import json
import os
import sys
import tempfile
import types

LOG = []
NOTIFICATIONS = []
MESSAGES = []
PLUGIN_ITEMS = []
PLUGIN_STATE = {}
BUILTINS = []
JSONRPC_CALLS = []
CONFIRMATIONS = []
CONFIRM_ANSWER = [True]
SETTINGS = {
    'show_progress': True,
}

# The simulated file tree. Key = directory path, value = list of item dicts as
# returned by Files.GetDirectory with media "files".
TREE = {}
SOURCES = []

# Paths the video library knows about, as returned by VideoLibrary.GetMovies
# and friends. Keyed by the member name of the respective result.
LIBRARY = {'movies': [], 'episodes': [], 'musicvideos': []}

# Extensions xbmc.getSupportedMedia('video') reports.
VIDEO_EXTENSIONS = '.mkv|.mp4|.avi|.strm|.iso|.webm|.ifo|.vob|.m3u|.xsp'


def _make_module(name):
    module = types.ModuleType(name)
    sys.modules[name] = module
    return module


# -- xbmc ---------------------------------------------------------------------

xbmc = _make_module('xbmc')
xbmc.LOGDEBUG, xbmc.LOGINFO, xbmc.LOGWARNING, xbmc.LOGERROR = 0, 1, 2, 3
xbmc.log = lambda message, level=0: LOG.append((level, message))
xbmc.executebuiltin = lambda command: BUILTINS.append(command)
xbmc.getSupportedMedia = lambda media_type: VIDEO_EXTENSIONS if media_type == 'video' else ''


class Monitor:
    def abortRequested(self):
        return False


xbmc.Monitor = Monitor


def _execute_jsonrpc(request_string):
    request = json.loads(request_string)
    method = request['method']
    params = request.get('params', {})
    JSONRPC_CALLS.append((method, params.get('directory', '')))

    if method == 'Files.GetSources':
        return json.dumps({'jsonrpc': '2.0', 'id': 1, 'result': {'sources': SOURCES}})

    if method == 'Files.GetDirectory':
        assert params.get('media') == 'files', 'media "video" mangles directories'
        directory = params['directory']
        if directory not in TREE:
            return json.dumps({'jsonrpc': '2.0', 'id': 1,
                               'error': {'code': -32602, 'message': 'Invalid params.'}})
        return json.dumps({'jsonrpc': '2.0', 'id': 1, 'result': {'files': TREE[directory]}})

    for library_method, member in (('VideoLibrary.GetMovies', 'movies'),
                                   ('VideoLibrary.GetEpisodes', 'episodes'),
                                   ('VideoLibrary.GetMusicVideos', 'musicvideos')):
        if method == library_method:
            return json.dumps({'jsonrpc': '2.0', 'id': 1,
                               'result': {member: [{'file': path} for path in LIBRARY[member]]}})

    raise AssertionError('unexpected method ' + method)


xbmc.executeJSONRPC = _execute_jsonrpc

# -- xbmcaddon ----------------------------------------------------------------

xbmcaddon = _make_module('xbmcaddon')


ADDON_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROFILE_DIR = os.path.join(tempfile.gettempdir(), 'vlih-test-profile')


class Addon:
    _INFO = {'id': 'plugin.video.notinlibrary',
             'name': 'Not in Library',
             'icon': 'icon.png',
             'profile': 'special://profile/addon_data/plugin.video.notinlibrary/',
             'path': ADDON_DIR}

    def getAddonInfo(self, key):
        return self._INFO[key]

    def getLocalizedString(self, string_id):
        return 'L{}'.format(string_id)

    def getSettingBool(self, setting_id):
        return SETTINGS[setting_id]


xbmcaddon.Addon = Addon

# -- xbmcgui ------------------------------------------------------------------

xbmcgui = _make_module('xbmcgui')


class InfoTagVideo:
    def __init__(self):
        self.values = {}

    def setMediaType(self, value):
        self.values['mediatype'] = value

    def setTitle(self, value):
        self.values['title'] = value

    def setFilenameAndPath(self, value):
        self.values['filenameandpath'] = value


class ListItem:
    def __init__(self, label='', label2='', path='', offscreen=False):
        self.label = label
        self.label2 = label2
        self.is_folder = False
        self.art = {}
        self.properties = {}
        self.context_menu = []
        self.info_tag = InfoTagVideo()

    def setIsFolder(self, is_folder):
        self.is_folder = is_folder

    def setLabel2(self, label2):
        self.label2 = label2

    def setArt(self, art):
        self.art.update(art)

    def setProperty(self, key, value):
        self.properties[key] = value

    def addContextMenuItems(self, items, replaceItems=False):
        self.context_menu.extend(items)

    def getVideoInfoTag(self):
        return self.info_tag


class Dialog:
    def notification(self, heading, message, icon=None, time=5000, sound=True):
        NOTIFICATIONS.append((heading, message))

    def ok(self, heading, message):
        MESSAGES.append((heading, message))
        return True

    def yesno(self, heading, message, *args, **kwargs):
        CONFIRMATIONS.append((heading, message))
        return CONFIRM_ANSWER[0]


class DialogProgressBG:
    def create(self, heading, message=''):
        PLUGIN_STATE.setdefault('progress', []).append(('create', heading))

    def update(self, percent=0, heading='', message=''):
        PLUGIN_STATE.setdefault('progress', []).append(('update', percent, message))

    def close(self):
        PLUGIN_STATE.setdefault('progress', []).append(('close',))


xbmcgui.ListItem = ListItem
xbmcgui.Dialog = Dialog
xbmcgui.DialogProgressBG = DialogProgressBG

# -- xbmcvfs ------------------------------------------------------------------

xbmcvfs = _make_module('xbmcvfs')
xbmcvfs.translatePath = lambda path: PROFILE_DIR

# -- xbmcplugin ---------------------------------------------------------------

xbmcplugin = _make_module('xbmcplugin')
xbmcplugin.SORT_METHOD_UNSORTED = 0
xbmcplugin.SORT_METHOD_LABEL = 1
xbmcplugin.SORT_METHOD_FILE = 18
xbmcplugin.setPluginCategory = lambda handle, category: PLUGIN_STATE.__setitem__('category', category)
xbmcplugin.setContent = lambda handle, content: PLUGIN_STATE.__setitem__('content', content)
xbmcplugin.addSortMethod = lambda handle, method, *args, **kwargs: None


def _add_directory_items(handle, items, total=0):
    PLUGIN_ITEMS.extend(items)
    return True


def _end_of_directory(handle, succeeded=True, updateListing=False, cacheToDisc=True):
    PLUGIN_STATE['succeeded'] = succeeded
    PLUGIN_STATE['cacheToDisc'] = cacheToDisc


xbmcplugin.addDirectoryItems = _add_directory_items
xbmcplugin.endOfDirectory = _end_of_directory


def reset_library():
    for member in LIBRARY:
        LIBRARY[member] = []


def reset():
    del LOG[:], NOTIFICATIONS[:], MESSAGES[:], PLUGIN_ITEMS[:], BUILTINS[:]
    del JSONRPC_CALLS[:], CONFIRMATIONS[:]
    CONFIRM_ANSWER[0] = True
    PLUGIN_STATE.clear()

"""A simulated Kodi for the tests: xbmc* stubs, a file tree and a base case.

Importing this module installs the stubs, so it has to come before any import
of resources.lib.
"""

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


# The add-on modules must not be imported before the stubs above are in place.
import os  # noqa: E402
import shutil  # noqa: E402
import sys  # noqa: E402
import unittest  # noqa: E402
from urllib.parse import urlencode  # noqa: E402

sys.path.insert(0, ADDON_DIR)

from resources.lib.router import Router  # noqa: E402

BASE_URL = 'plugin://plugin.video.notinlibrary/'


def directory(path):
    """Return a directory item as Files.GetDirectory reports it."""
    return {'label': path.rstrip('/').rsplit('/', 1)[-1], 'file': path,
            'filetype': 'directory'}


def video(path):
    """Return a video file item as Files.GetDirectory reports it."""
    return {'label': path.rsplit('/', 1)[-1], 'file': path, 'filetype': 'file'}


def imported(path, member='movies'):
    """Mark the path as known to the video library and return its file item."""
    LIBRARY[member].append(path)
    return video(path)


def build_tree():
    """Fill the simulated sources and directories."""
    reset_library()
    SOURCES[:] = [
        {'label': 'Video Playlists', 'file': 'special://videoplaylists/'},
        {'label': 'Movies', 'file': 'smb://nas/movies/'},
        {'label': 'TV Shows', 'file': 'smb://nas/tv/'},
        {'label': 'Complete', 'file': 'smb://nas/complete/'},
        {'label': 'Some Add-on', 'file': 'plugin://plugin.video.whatever/'},
    ]
    TREE.clear()
    TREE.update({
        # Kodi's own playlists pseudo source. Playlist extensions are part of
        # the video extensions, so without the path filter this would show up.
        'special://videoplaylists/': [
            video('special://videoplaylists/Unwatched.xsp'),
        ],
        'smb://nas/movies/': [
            directory('smb://nas/movies/Known Film (1999)/'),
            directory('smb://nas/movies/New Film (2020)/'),
            directory('smb://nas/movies/Disc Film (2001)/'),
            directory('smb://nas/movies/Mixed/'),
            directory('smb://nas/movies/New Disc/'),
            imported('smb://nas/movies/Loose Known.mkv'),
            video('smb://nas/movies/Loose Unknown.mkv'),
            # Not a video, must never be listed.
            {'label': 'poster.jpg', 'file': 'smb://nas/movies/poster.jpg',
             'filetype': 'file'},
        ],
        'smb://nas/movies/Known Film (1999)/': [
            imported('smb://nas/movies/Known Film (1999)/movie.mkv'),
        ],
        'smb://nas/movies/New Film (2020)/': [
            video('smb://nas/movies/New Film (2020)/movie.mkv'),
        ],
        # A disc folder that is in the library: one medium, must stay hidden
        # instead of offering its VOB and IFO files as missing videos.
        'smb://nas/movies/Disc Film (2001)/': [
            directory('smb://nas/movies/Disc Film (2001)/VIDEO_TS/'),
        ],
        'smb://nas/movies/Disc Film (2001)/VIDEO_TS/': [
            imported('smb://nas/movies/Disc Film (2001)/VIDEO_TS/VIDEO_TS.IFO'),
            video('smb://nas/movies/Disc Film (2001)/VIDEO_TS/VTS_01_1.VOB'),
        ],
        # The same, but not in the library: has to show up as one entry.
        'smb://nas/movies/New Disc/': [
            directory('smb://nas/movies/New Disc/VIDEO_TS/'),
        ],
        'smb://nas/movies/New Disc/VIDEO_TS/': [
            video('smb://nas/movies/New Disc/VIDEO_TS/VIDEO_TS.IFO'),
            video('smb://nas/movies/New Disc/VIDEO_TS/VTS_01_1.VOB'),
        ],
        # A folder holding an imported movie next to a newly copied one.
        'smb://nas/movies/Mixed/': [
            imported('smb://nas/movies/Mixed/Imported.mkv'),
            video('smb://nas/movies/Mixed/Minions and Monsters.mkv'),
        ],
        # TV: one episode is imported, the other is not.
        'smb://nas/tv/': [
            directory('smb://nas/tv/Some Show/'),
        ],
        'smb://nas/tv/Some Show/': [
            directory('smb://nas/tv/Some Show/Season 01/'),
        ],
        'smb://nas/tv/Some Show/Season 01/': [
            imported('smb://nas/tv/Some Show/Season 01/S01E01.mkv', 'episodes'),
            video('smb://nas/tv/Some Show/Season 01/S01E02.mkv'),
        ],
        'plugin://plugin.video.whatever/': [
            video('plugin://plugin.video.whatever/clip.mkv'),
        ],
        # Readable, but part of no source at all.
        'smb://elsewhere/stuff/': [
            video('smb://elsewhere/stuff/orphan.mkv'),
        ],
        # Fully scanned source, must not show up at all.
        'smb://nas/complete/': [
            directory('smb://nas/complete/Sub/'),
        ],
        'smb://nas/complete/Sub/': [
            imported('smb://nas/complete/Sub/done.mkv'),
        ],
    })


class AddonTestCase(unittest.TestCase):
    """Gives every test a fresh file tree, an empty profile and clean stubs."""

    def setUp(self):
        shutil.rmtree(PROFILE_DIR, ignore_errors=True)
        build_tree()
        reset()

    def tearDown(self):
        shutil.rmtree(PROFILE_DIR, ignore_errors=True)

    # -- driving the add-on -------------------------------------------------

    def dispatch(self, **params):
        """Run the plugin with the given parameters and return its items.

        Each item is a (url, label, is_folder) triple.
        """
        reset()
        query = '?' + urlencode(params) if params else ''
        Router([BASE_URL, '1', query]).dispatch()
        return [(item[0], item[1].label, item[2]) for item in PLUGIN_ITEMS]

    def act(self, action, path):
        """Run a plugin action, the way a context menu entry does."""
        reset()
        Router([BASE_URL, '-1',
                '?' + urlencode({'action': action, 'path': path})]).dispatch()

    def top_level(self):
        return self.dispatch()

    def missing(self, path=''):
        return self._listing('missing', path)

    def excluded(self, path=''):
        return self._listing('excluded', path)

    def _listing(self, mode, path):
        params = {'action': 'list', 'mode': mode}
        if path:
            params['path'] = path
        return self.dispatch(**params)

    # -- reading what came back ---------------------------------------------

    @staticmethod
    def labels(items):
        return [label for _, label, _ in items]

    @staticmethod
    def list_items():
        """The ListItem objects of the last listing, for art and context menus."""
        return [item[1] for item in PLUGIN_ITEMS]

    @staticmethod
    def profile_path(name):
        return os.path.join(PROFILE_DIR, name)

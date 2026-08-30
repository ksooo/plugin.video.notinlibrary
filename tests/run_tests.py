"""Exercise the add-on logic against a simulated Kodi file tree.

Run with: python3 tests/run_tests.py

Needs no Kodi and no dependencies beyond the standard library: kodi_stubs
installs stand-ins for the xbmc* modules, so routing, scanning and the
exclusion handling run exactly as they would inside Kodi.
"""

import json
import os
import shutil
import sys
from urllib.parse import urlencode

TESTS_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
ADDON_DIRECTORY = os.path.dirname(TESTS_DIRECTORY)

sys.path.insert(0, TESTS_DIRECTORY)
sys.path.insert(0, ADDON_DIRECTORY)

import kodi_stubs as stubs  # noqa: E402  installs the xbmc* stub modules

from resources.lib import exclusions  # noqa: E402
from resources.lib import library  # noqa: E402
from resources.lib import scanner  # noqa: E402
from resources.lib.router import Router  # noqa: E402

BASE_URL = 'plugin://plugin.video.notinlibrary/'


def directory(path):
    return {'label': path.rstrip('/').rsplit('/', 1)[-1], 'file': path,
            'filetype': 'directory'}


def video(path):
    return {'label': path.rsplit('/', 1)[-1], 'file': path, 'filetype': 'file'}


def imported(path, member='movies'):
    """Mark the path as known to the video library and return its file item."""
    stubs.LIBRARY[member].append(path)
    return video(path)


def build_tree():
    stubs.reset_library()
    stubs.SOURCES[:] = [
        {'label': 'Video Playlists', 'file': 'special://videoplaylists/'},
        {'label': 'Movies', 'file': 'smb://nas/movies/'},
        {'label': 'TV Shows', 'file': 'smb://nas/tv/'},
        {'label': 'Complete', 'file': 'smb://nas/complete/'},
        {'label': 'Some Add-on', 'file': 'plugin://plugin.video.whatever/'},
    ]
    stubs.TREE.clear()
    stubs.TREE.update({
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
        # The regression: a folder holding an imported movie next to a newly
        # copied one. Listing it with media "video" would have replaced the
        # whole folder by the imported movie.
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
        # An add-on source holding a missing video, to check the skip setting.
        'plugin://plugin.video.whatever/': [
            video('plugin://plugin.video.whatever/clip.mkv'),
        ],
        # Readable, but part of no source at all - only used to check the
        # breadcrumb fallback.
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


def _dispatch(params):
    stubs.reset()
    Router([BASE_URL, '1', '?' + urlencode(params) if params else '']).dispatch()
    return [(item[0], item[1].label, item[2]) for item in stubs.PLUGIN_ITEMS]


def top_level():
    return _dispatch({})


def listing(path='', label='', mode='missing'):
    params = {'action': 'list', 'mode': mode}
    if path:
        params['path'] = path
    return _dispatch(params)


def excluded_listing(path='', label=''):
    return listing(path, label, mode='excluded')


def _scan_confirmations(path):
    stubs.reset()
    Router([BASE_URL, '-1', '?' + urlencode({'action': 'scan', 'path': path})]).dispatch()
    return stubs.CONFIRMATIONS


def check(description, actual, expected):
    status = 'PASS' if actual == expected else 'FAIL'
    print('{} {}'.format(status, description))
    if status == 'FAIL':
        print('     expected: {!r}'.format(expected))
        print('     actual:   {!r}'.format(actual))
    return status == 'PASS'


def main():
    # Leftovers from an earlier run would falsify every listing below.
    shutil.rmtree(stubs.PROFILE_DIR, ignore_errors=True)
    build_tree()
    results = []

    # -- helpers ---------------------------------------------------------------
    results.append(check('protocol of smb path',
                         scanner.get_protocol('smb://nas/movies/'), 'smb'))
    results.append(check('protocol of local path',
                         scanner.get_protocol('/Volumes/Media/movies/'), ''))
    # An add-on can declare medialibraryscanpath, so plugin sources are walked.
    results.append(check('plugin sources are scannable',
                         scanner.is_scannable('plugin://plugin.video.x/'), True))
    results.append(check('a plugin source gets the folder icon Kodi uses',
                         scanner.get_source_icon('plugin://plugin.video.x/'),
                         'DefaultFolder.png'))
    results.append(check('smb source is scannable',
                         scanner.is_scannable('smb://nas/movies/'), True))
    results.append(check('playlists pseudo source is not scannable',
                         scanner.is_scannable('special://videoplaylists/'), False))
    results.append(check('playlists path matches without trailing slash',
                         scanner.is_scannable('special://videoplaylists'), False))
    results.append(check('other special paths stay scannable',
                         scanner.is_scannable('special://profile/media/'), True))

    results.append(check('a network source gets the network icon',
                         scanner.get_source_icon('smb://nas/movies/'), 'DefaultNetwork.png'))
    results.append(check('a plain local path gets the hard disk icon',
                         scanner.get_source_icon('/Volumes/Media/movies/'), 'DefaultHardDisk.png'))
    results.append(check('file:// counts as local',
                         scanner.get_source_icon('file:///Volumes/Media/'), 'DefaultHardDisk.png'))
    results.append(check('an optical source gets its own icon',
                         scanner.get_source_icon('iso9660://'), 'DefaultDVDRom.png'))

    # -- library matching ------------------------------------------------------
    results.append(check('a plain path is no stack',
                         library.split_stack('smb://nas/movies/a.mkv'),
                         ['smb://nas/movies/a.mkv']))
    results.append(check('a stack is split into its parts',
                         library.split_stack('stack://smb://nas/a-cd1.mkv , smb://nas/a-cd2.mkv'),
                         ['smb://nas/a-cd1.mkv', 'smb://nas/a-cd2.mkv']))
    results.append(check('doubled commas are unescaped',
                         library.split_stack('stack://smb://nas/a,,b-cd1.mkv , smb://nas/c.mkv'),
                         ['smb://nas/a,b-cd1.mkv', 'smb://nas/c.mkv']))
    results.append(check('every part of a stack counts as known',
                         library.VideoLibrary(
                             library.split_stack('stack://a.mkv , b.mkv')).contains('b.mkv'),
                         True))
    results.append(check('the library reports entries below a disc folder',
                         library.load().has_entry_below('smb://nas/movies/Disc Film (2001)/'),
                         True))
    results.append(check('and none below one outside the library',
                         library.load().has_entry_below('smb://nas/movies/New Disc/'), False))
    results.append(check('has_entry_below needs the separator',
                         library.VideoLibrary(['smb://nas/movies extra/x.mkv'])
                         .has_entry_below('smb://nas/movies'), False))

    # -- root listing ----------------------------------------------------------
    root = listing()
    results.append(check('root lists only sources with missing videos',
                         [label for _, label, _ in root],
                         ['Movies', 'TV Shows', 'Some Add-on']))
    results.append(check('root items are folders',
                         all(is_folder for _, _, is_folder in root), True))
    top_level()
    results.append(check('the two top level entries set no content either',
                         stubs.PLUGIN_STATE.get('content'), None))
    results.append(check('the top level uses the icons shipped with the add-on',
                         [os.path.basename(item[1].art['icon']) for item in stubs.PLUGIN_ITEMS],
                         ['not-imported.png', 'excluded.png']))
    results.append(check('those icons actually exist',
                         [os.path.isfile(item[1].art['icon']) for item in stubs.PLUGIN_ITEMS],
                         [True, True]))

    root = listing()
    results.append(check('sources carry the icon Kodi uses for them',
                         [item[1].art['icon'] for item in stubs.PLUGIN_ITEMS],
                         ['DefaultNetwork.png', 'DefaultNetwork.png', 'DefaultFolder.png']))
    results.append(check('source level sets no content, so skins draw the icons',
                         stubs.PLUGIN_STATE.get('content'), None))
    results.append(check('listing is not cached', stubs.PLUGIN_STATE.get('cacheToDisc'), False))

    # -- movies source ---------------------------------------------------------
    movies = listing('smb://nas/movies/', 'Movies')
    results.append(check('movies level hides scanned dirs, in-library discs and known files',
                         [label for _, label, _ in movies],
                         ['New Film (2020)', 'Mixed', 'New Disc', 'Loose Unknown.mkv']))
    results.append(check('missing file is a leaf item',
                         [is_folder for _, _, is_folder in movies],
                         [True, True, True, False]))
    results.append(check('missing file url is the plain path',
                         movies[-1][0], 'smb://nas/movies/Loose Unknown.mkv'))

    # The regression: listing with media "video" made Kodi replace a folder
    # holding an imported movie by that movie, hiding the folder and every new
    # file in it. The stubs now reject media "video" outright.
    results.append(check('a folder holding an imported movie is still listed',
                         'Mixed' in [label for _, label, _ in movies], True))
    results.append(check('non-video files are filtered out',
                         'poster.jpg' in [label for _, label, _ in movies], False))
    results.append(check('only the new file inside it is listed',
                         [label for _, label, _ in listing('smb://nas/movies/Mixed/')],
                         ['Minions and Monsters.mkv']))
    results.append(check('an in-library disc folder stays hidden, VOBs and all',
                         'Disc Film (2001)' in [label for _, label, _ in movies], False))
    results.append(check('a disc folder outside the library is one single entry',
                         [label for _, label, _ in listing('smb://nas/movies/New Disc/')],
                         ['VIDEO_TS']))
    results.append(check('is_disc_folder spots the disc structure',
                         scanner.is_disc_folder(
                             scanner.list_directory('smb://nas/movies/New Disc/', library.load())), True))
    results.append(check('a plain folder is no disc folder',
                         scanner.is_disc_folder(
                             scanner.list_directory('smb://nas/movies/Mixed/', library.load())), False))
    # The checks above listed other directories, so restore the movies level
    # before looking at the container state it left behind.
    movies = listing('smb://nas/movies/', 'Movies')
    results.append(check('movies content type', stubs.PLUGIN_STATE.get('content'), 'videos'))
    results.append(check('below source level the plain folder icon is used',
                         sorted(set(item[1].art['icon'] for item in stubs.PLUGIN_ITEMS)),
                         ['DefaultFolder.png', 'DefaultVideo.png']))

    # -- tv show, the tvshow-directory nuance ----------------------------------
    tv = listing('smb://nas/tv/', 'TV Shows')
    results.append(check('tvshow directory is descended into despite library entry',
                         [label for _, label, _ in tv], ['Some Show']))
    season_parent = listing('smb://nas/tv/Some Show/', 'Some Show')
    results.append(check('season directory with a missing episode shows up',
                         [label for _, label, _ in season_parent], ['Season 01']))
    season = listing('smb://nas/tv/Some Show/Season 01/', 'Season 01')
    results.append(check('only the missing episode is listed',
                         [label for _, label, _ in season], ['S01E02.mkv']))

    # -- breadcrumb ------------------------------------------------------------
    listing('smb://nas/tv/Some Show/Season 01/')
    results.append(check('the breadcrumb names side, source and every folder',
                         stubs.PLUGIN_STATE.get('category'),
                         'L30026 / TV Shows / Some Show / Season 01'))
    listing('smb://nas/tv/')
    results.append(check('at source level it ends with the source',
                         stubs.PLUGIN_STATE.get('category'), 'L30026 / TV Shows'))
    listing()
    results.append(check('the source level itself shows just the side',
                         stubs.PLUGIN_STATE.get('category'), 'L30026'))
    top_level()
    results.append(check('the top level shows the add-on name',
                         stubs.PLUGIN_STATE.get('category'), 'Not in Library'))
    listing('smb://elsewhere/stuff/')
    results.append(check('a path outside every source falls back to the path',
                         stubs.PLUGIN_STATE.get('category'), 'L30026 / smb://elsewhere/stuff/'))

    results.append(check('a longer source wins over a shorter matching one',
                         scanner.find_source_for('smb://nas/tv/Some Show/').label, 'TV Shows'))

    # -- context menu ----------------------------------------------------------
    file_item = stubs.PLUGIN_ITEMS[0][1]
    results.append(check('a file offers only the exclusion, importing is left to Kodi',
                         [entry[0] for entry in file_item.context_menu], ['L30020']))
    results.append(check('file item is playable',
                         file_item.properties.get('IsPlayable'), 'true'))

    listing('smb://nas/movies/', 'Movies')
    results.append(check('a directory offers only the exclusion, no tree-wide scan',
                         [entry[0] for entry in stubs.PLUGIN_ITEMS[0][1].context_menu],
                         ['L30020']))
    results.append(check('the exclusion entry runs through the plugin',
                         stubs.PLUGIN_ITEMS[0][1].context_menu[0][1].startswith('RunPlugin('),
                         True))

    # -- exclusions ------------------------------------------------------------
    build_tree()
    shutil.rmtree(stubs.PROFILE_DIR, ignore_errors=True)
    results.append(check('nothing is excluded initially',
                         exclusions.load(), exclusions.ExclusionList()))

    missing_episode = 'smb://nas/tv/Some Show/Season 01/S01E02.mkv'
    stubs.reset()
    Router([BASE_URL, '-1',
            '?' + urlencode({'action': 'exclude', 'path': missing_episode})]).dispatch()
    results.append(check('excluding persists the path',
                         exclusions.load(), exclusions.ExclusionList(files=[missing_episode])))
    results.append(check('excluding refreshes the container',
                         stubs.BUILTINS, ['Container.Refresh']))
    results.append(check('exclusion file is written to the profile directory',
                         os.path.isfile(os.path.join(stubs.PROFILE_DIR, 'exclusions.json')),
                         True))

    results.append(check('excluded file no longer shows up in its directory',
                         [label for _, label, _ in
                          listing('smb://nas/tv/Some Show/Season 01/', 'Season 01')],
                         []))
    results.append(check('directory holding only excluded videos disappears',
                         [label for _, label, _ in listing('smb://nas/tv/Some Show/', 'Some Show')],
                         []))
    results.append(check('source holding only excluded videos disappears',
                         [label for _, label, _ in listing()], ['Movies', 'Some Add-on']))
    results.append(check('the top level always offers exactly the two sides',
                         [label for _, label, _ in top_level()], ['L30026', 'L30022']))

    # The excluded side mirrors the structure of the missing side.
    results.append(check('excluded side lists the source holding the exclusion',
                         [label for _, label, _ in excluded_listing()], ['TV Shows']))
    results.append(check('intermediate directory is rebuilt from the stored path',
                         [label for _, label, _ in
                          excluded_listing('smb://nas/tv/', 'TV Shows')], ['Some Show']))
    results.append(check('an intermediate directory offers the undo too',
                         stubs.PLUGIN_ITEMS[0][1].context_menu[0][0], 'L30021'))
    results.append(check('next level down is rebuilt as well',
                         [label for _, label, _ in
                          excluded_listing('smb://nas/tv/Some Show/', 'Some Show')],
                         ['Season 01']))
    leaf = excluded_listing('smb://nas/tv/Some Show/Season 01/', 'Season 01')
    results.append(check('the excluded file is the leaf',
                         [label for _, label, _ in leaf], ['S01E02.mkv']))
    results.append(check('the excluded file keeps its real path', leaf[0][0], missing_episode))
    results.append(check('the excluded file offers to allow the import again',
                         stubs.PLUGIN_ITEMS[0][1].context_menu[0][0], 'L30021'))
    results.append(check('rebuilding the structure needs no directory listing',
                         [method for method, _ in stubs.JSONRPC_CALLS
                          if method == 'Files.GetDirectory'], []))

    stubs.reset()
    Router([BASE_URL, '-1',
            '?' + urlencode({'action': 'include', 'path': missing_episode})]).dispatch()
    results.append(check('including removes the path again',
                         exclusions.load(), exclusions.ExclusionList()))
    results.append(check('the file is back in its directory',
                         [label for _, label, _ in
                          listing('smb://nas/tv/Some Show/Season 01/', 'Season 01')],
                         ['S01E02.mkv']))
    results.append(check('both sides remain even with nothing excluded',
                         [label for _, label, _ in top_level()], ['L30026', 'L30022']))
    results.append(check('the empty excluded side reports itself',
                         [label for _, label, _ in excluded_listing()], []))
    shutil.rmtree(stubs.PROFILE_DIR, ignore_errors=True)

    # -- excluding whole directories -------------------------------------------
    build_tree()
    results.append(check('prefix match needs the trailing separator',
                         exclusions.ExclusionList(directories=['smb://nas/movies/'])
                         .contains('smb://nas/movies extra/film.mkv'), False))
    results.append(check('a file below an excluded directory is excluded',
                         exclusions.ExclusionList(directories=['smb://nas/movies/'])
                         .contains('smb://nas/movies/New Film (2020)/movie.mkv'), True))
    results.append(check('the excluded directory itself is excluded',
                         exclusions.ExclusionList(directories=['smb://nas/movies/'])
                         .contains('smb://nas/movies/'), True))

    new_film = 'smb://nas/movies/New Film (2020)/'
    stubs.reset()
    Router([BASE_URL, '-1',
            '?' + urlencode({'action': 'excludedir', 'path': new_film})]).dispatch()
    results.append(check('excluding a directory persists it as a directory',
                         exclusions.load(), exclusions.ExclusionList(directories=[new_film])))
    results.append(check('the excluded directory is gone from its parent',
                         [label for _, label, _ in listing('smb://nas/movies/', 'Movies')],
                         ['Mixed', 'New Disc', 'Loose Unknown.mkv']))
    results.append(check('the excluded directory shows up on the excluded side',
                         [label for _, label, _ in
                          excluded_listing('smb://nas/movies/', 'Movies')],
                         ['New Film (2020) (X)']))

    # A directory excluded itself is marked; one that merely leads to an
    # excluded file further down is not.
    exclusions.add_file('smb://nas/movies/Mixed/Minions and Monsters.mkv')
    results.append(check('only the self-excluded directory carries the marker',
                         [label for _, label, _ in
                          excluded_listing('smb://nas/movies/', 'Movies')],
                         ['Mixed', 'New Film (2020) (X)']))
    exclusions.remove('smb://nas/movies/Mixed/Minions and Monsters.mkv')
    results.append(check('an excluded directory offers the undo',
                         stubs.PLUGIN_ITEMS[0][1].context_menu[0][0], 'L30021'))

    # Excluding the whole source has to swallow the entry below it.
    stubs.reset()
    Router([BASE_URL, '-1',
            '?' + urlencode({'action': 'excludedir', 'path': 'smb://nas/movies/'})]).dispatch()
    results.append(check('a covered entry is dropped as redundant',
                         exclusions.load(),
                         exclusions.ExclusionList(directories=['smb://nas/movies/'])))
    results.append(check('the excluded source is gone from the missing side',
                         [label for _, label, _ in listing()], ['TV Shows', 'Some Add-on']))

    sources = excluded_listing()
    results.append(check('an excluded source keeps its label and is marked',
                         [label for _, label, _ in sources], ['Movies (X)']))
    results.append(check('the excluded source is a folder', sources[0][2], True))
    results.append(check('the excluded source carries the source icon',
                         stubs.PLUGIN_ITEMS[0][1].art['icon'], 'DefaultNetwork.png'))
    results.append(check('opening an excluded directory shows what it hides',
                         [label for _, label, _ in
                          excluded_listing('smb://nas/movies/', 'Movies')],
                         ['Known Film (1999)', 'New Film (2020)', 'Disc Film (2001)',
                          'Mixed', 'New Disc', 'Loose Known.mkv', 'Loose Unknown.mkv']))
    results.append(check('inherited entries offer the undo as well',
                         [item[1].context_menu[0][0] for item in stubs.PLUGIN_ITEMS],
                         ['L30021'] * 7))

    # Undoing an inherited entry has to dissolve the exclusion of its ancestor:
    # everything except that entry stays excluded.
    stubs.reset()
    Router([BASE_URL, '-1', '?' + urlencode(
        {'action': 'include', 'path': 'smb://nas/movies/Loose Unknown.mkv'})]).dispatch()
    # Every sibling directory has to be excluded, even the ones Kodi resolves
    # to a movie - only files may be skipped for already being in the library.
    results.append(check('dissolving replaces the ancestor by its siblings',
                         exclusions.load(),
                         exclusions.ExclusionList(
                             directories=['smb://nas/movies/Disc Film (2001)/',
                                          'smb://nas/movies/Known Film (1999)/',
                                          'smb://nas/movies/Mixed/',
                                          'smb://nas/movies/New Disc/',
                                          'smb://nas/movies/New Film (2020)/'])))
    results.append(check('the freed file is back on the missing side',
                         [label for _, label, _ in listing('smb://nas/movies/', 'Movies')],
                         ['Loose Unknown.mkv']))
    # Dissolving across two levels walks every directory on the way down.
    shutil.rmtree(stubs.PROFILE_DIR, ignore_errors=True)
    exclusions.save(exclusions.ExclusionList(directories=['smb://nas/tv/']))
    stubs.reset()
    Router([BASE_URL, '-1', '?' + urlencode(
        {'action': 'include',
         'path': 'smb://nas/tv/Some Show/Season 01/S01E02.mkv'})]).dispatch()
    results.append(check('dissolving walks down every level',
                         exclusions.load(), exclusions.ExclusionList()))
    results.append(check('the deeply freed file is back on the missing side',
                         [label for _, label, _ in
                          listing('smb://nas/tv/Some Show/Season 01/', 'Season 01')],
                         ['S01E02.mkv']))

    # An unreadable directory must not silently produce a wrong list.
    shutil.rmtree(stubs.PROFILE_DIR, ignore_errors=True)
    exclusions.save(exclusions.ExclusionList(directories=['smb://nas/gone/']))
    stubs.reset()
    Router([BASE_URL, '-1', '?' + urlencode(
        {'action': 'include', 'path': 'smb://nas/gone/film.mkv'})]).dispatch()
    results.append(check('a failed dissolve keeps the list untouched',
                         exclusions.load(),
                         exclusions.ExclusionList(directories=['smb://nas/gone/'])))
    results.append(check('a failed dissolve is reported',
                         [message for _, message in stubs.NOTIFICATIONS], ['L30027']))
    results.append(check('a failed dissolve does not refresh', stubs.BUILTINS, []))

    shutil.rmtree(stubs.PROFILE_DIR, ignore_errors=True)
    exclusions.save(exclusions.ExclusionList(directories=['smb://nas/movies/']))

    stubs.reset()
    Router([BASE_URL, '-1',
            '?' + urlencode({'action': 'include', 'path': 'smb://nas/movies/'})]).dispatch()
    results.append(check('a directory exclusion can be taken back',
                         exclusions.load(), exclusions.ExclusionList()))
    shutil.rmtree(stubs.PROFILE_DIR, ignore_errors=True)

    # -- format migration ------------------------------------------------------
    os.makedirs(stubs.PROFILE_DIR, exist_ok=True)
    with open(os.path.join(stubs.PROFILE_DIR, 'exclusions.json'), 'w', encoding='utf-8') as f:
        json.dump({'version': 1, 'paths': ['smb://nas/movies/Loose Unknown.mkv']}, f)
    results.append(check('a version 1 file is migrated to files',
                         exclusions.load(),
                         exclusions.ExclusionList(files=['smb://nas/movies/Loose Unknown.mkv'])))
    with open(os.path.join(stubs.PROFILE_DIR, 'exclusions.json'), 'w', encoding='utf-8') as f:
        f.write('{ this is not json')
    results.append(check('a damaged file yields an empty list',
                         exclusions.load(), exclusions.ExclusionList()))
    shutil.rmtree(stubs.PROFILE_DIR, ignore_errors=True)

    # -- non-scannable sources -------------------------------------------------
    build_tree()
    results.append(check('the playlists pseudo source is always filtered out',
                         'Video Playlists' in [label for _, label, _ in listing()], False))
    results.append(check('a source without anything missing is never listed',
                         'Complete' in [label for _, label, _ in listing()], False))

    # -- nothing to show -------------------------------------------------------
    # Both sides report emptiness the same way: a toast, and no success, so
    # Kodi stays where it is instead of opening an empty listing.
    stubs.SOURCES[:] = [{'label': 'Complete', 'file': 'smb://nas/complete/'}]
    shutil.rmtree(stubs.PROFILE_DIR, ignore_errors=True)

    listing()
    results.append(check('an empty missing side reports by toast, not by dialogue',
                         ([message for _, message in stubs.NOTIFICATIONS], stubs.MESSAGES),
                         (['L30014'], [])))
    results.append(check('and does not claim success',
                         stubs.PLUGIN_STATE.get('succeeded'), False))

    excluded_listing()
    results.append(check('an empty excluded side reports the same way',
                         ([message for _, message in stubs.NOTIFICATIONS], stubs.MESSAGES),
                         (['L30023'], [])))
    results.append(check('and does not claim success either',
                         stubs.PLUGIN_STATE.get('succeeded'), False))

    # Missing sources are a setup problem, so that one stays a modal dialogue.
    stubs.SOURCES[:] = []
    listing()
    results.append(check('missing sources still warrant a modal dialogue',
                         ([heading for heading, _ in stubs.MESSAGES], stubs.NOTIFICATIONS),
                         (['L30012'], [])))

    print('\n{}/{} checks passed'.format(sum(results), len(results)))
    return 0 if all(results) else 1


if __name__ == '__main__':
    sys.exit(main())

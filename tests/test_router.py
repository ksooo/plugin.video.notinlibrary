# -*- coding: utf-8 -*-
#
#  Copyright (C) 2026 ksooo
#  This file is part of Not in Library
#
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt for more information.
#
"""Tests for resources.lib.router, driving the add-on as Kodi would."""

import os

# Importing support installs the xbmc* stubs, so it has to come first.
from tests import support
from tests.support import AddonTestCase

from resources.lib import exclusions


class TopLevelTest(AddonTestCase):

    def test_it_offers_exactly_the_two_sides(self):
        self.assertEqual(self.labels(self.top_level()), ['L30026', 'L30022'])

    def test_it_still_does_so_with_nothing_excluded(self):
        self.assertEqual(exclusions.load(), exclusions.ExclusionList())
        self.assertEqual(self.labels(self.top_level()), ['L30026', 'L30022'])

    def test_it_uses_the_icons_shipped_with_the_add_on(self):
        self.top_level()
        self.assertEqual([os.path.basename(item.art['icon']) for item in self.list_items()],
                         ['not-imported.png', 'excluded.png'])

    def test_those_icons_exist(self):
        self.top_level()
        for item in self.list_items():
            self.assertTrue(os.path.isfile(item.art['icon']), item.art['icon'])

    def test_it_sets_no_content_so_skins_draw_the_icons(self):
        self.top_level()
        self.assertIsNone(support.PLUGIN_STATE.get('content'))

    def test_the_breadcrumb_is_the_add_on_name(self):
        self.top_level()
        self.assertEqual(support.PLUGIN_STATE.get('category'), 'Not in Library')


class MissingSourcesTest(AddonTestCase):

    def test_only_sources_holding_missing_videos_are_listed(self):
        self.assertEqual(self.labels(self.missing()),
                         ['Movies', 'TV Shows', 'Some Add-on'])

    def test_a_fully_imported_source_is_never_listed(self):
        self.assertNotIn('Complete', self.labels(self.missing()))

    def test_the_playlists_pseudo_source_is_always_filtered_out(self):
        self.assertNotIn('Video Playlists', self.labels(self.missing()))

    def test_they_are_folders(self):
        self.assertTrue(all(is_folder for _, _, is_folder in self.missing()))

    def test_they_carry_the_icon_kodi_uses_for_them(self):
        self.missing()
        self.assertEqual([item.art['icon'] for item in self.list_items()],
                         ['DefaultNetwork.png', 'DefaultNetwork.png', 'DefaultFolder.png'])

    def test_the_level_sets_no_content(self):
        self.missing()
        self.assertIsNone(support.PLUGIN_STATE.get('content'))

    def test_the_listing_is_not_cached(self):
        self.missing()
        self.assertFalse(support.PLUGIN_STATE.get('cacheToDisc'))


class MissingDirectoryTest(AddonTestCase):

    def test_scanned_dirs_in_library_discs_and_known_files_are_hidden(self):
        self.assertEqual(self.labels(self.missing('smb://nas/movies/')),
                         ['New Film (2020)', 'Mixed', 'New Disc', 'Loose Unknown.mkv'])

    def test_a_folder_holding_an_imported_movie_is_still_listed(self):
        self.assertIn('Mixed', self.labels(self.missing('smb://nas/movies/')))

    def test_only_the_missing_file_inside_it_is_listed(self):
        self.assertEqual(self.labels(self.missing('smb://nas/movies/Mixed/')),
                         ['Minions and Monsters.mkv'])

    def test_non_video_files_are_filtered_out(self):
        self.assertNotIn('poster.jpg', self.labels(self.missing('smb://nas/movies/')))

    def test_an_in_library_disc_folder_stays_hidden(self):
        self.assertNotIn('Disc Film (2001)', self.labels(self.missing('smb://nas/movies/')))

    def test_a_disc_folder_outside_the_library_is_one_entry(self):
        self.assertEqual(self.labels(self.missing('smb://nas/movies/New Disc/')), ['VIDEO_TS'])

    def test_directories_come_before_files(self):
        items = self.missing('smb://nas/movies/')
        self.assertEqual([is_folder for _, _, is_folder in items], [True, True, True, False])

    def test_a_file_keeps_its_plain_path_as_url(self):
        items = self.missing('smb://nas/movies/')
        self.assertEqual(items[-1][0], 'smb://nas/movies/Loose Unknown.mkv')

    def test_the_level_holds_videos(self):
        self.missing('smb://nas/movies/')
        self.assertEqual(support.PLUGIN_STATE.get('content'), 'videos')

    def test_below_source_level_the_plain_folder_icon_is_used(self):
        self.missing('smb://nas/movies/')
        self.assertEqual(sorted({item.art['icon'] for item in self.list_items()}),
                         ['DefaultFolder.png', 'DefaultVideo.png'])

    def test_an_unreadable_directory_is_reported(self):
        self.missing('smb://nas/gone/')
        self.assertEqual([heading for heading, _ in support.NOTIFICATIONS], ['L30017'])
        self.assertFalse(support.PLUGIN_STATE.get('succeeded'))


class TvShowTest(AddonTestCase):
    """A show directory is in the library, yet an episode below it is missing."""

    def test_the_show_directory_is_descended_into(self):
        self.assertEqual(self.labels(self.missing('smb://nas/tv/')), ['Some Show'])

    def test_the_season_directory_shows_up(self):
        self.assertEqual(self.labels(self.missing('smb://nas/tv/Some Show/')), ['Season 01'])

    def test_only_the_missing_episode_is_listed(self):
        self.assertEqual(self.labels(self.missing('smb://nas/tv/Some Show/Season 01/')),
                         ['S01E02.mkv'])


class BreadcrumbTest(AddonTestCase):

    def breadcrumb(self):
        return support.PLUGIN_STATE.get('category')

    def test_it_names_side_source_and_every_folder(self):
        self.missing('smb://nas/tv/Some Show/Season 01/')
        self.assertEqual(self.breadcrumb(), 'L30026 / TV Shows / Some Show / Season 01')

    def test_at_source_level_it_ends_with_the_source(self):
        self.missing('smb://nas/tv/')
        self.assertEqual(self.breadcrumb(), 'L30026 / TV Shows')

    def test_the_source_level_shows_just_the_side(self):
        self.missing()
        self.assertEqual(self.breadcrumb(), 'L30026')

    def test_a_path_outside_every_source_falls_back_to_the_path(self):
        self.missing('smb://elsewhere/stuff/')
        self.assertEqual(self.breadcrumb(), 'L30026 / smb://elsewhere/stuff/')


class ContextMenuTest(AddonTestCase):

    def test_a_file_offers_only_the_exclusion(self):
        # Importing a single file is left to Kodi's own "Information" entry.
        self.missing('smb://nas/tv/Some Show/Season 01/')
        self.assertEqual([entry[0] for entry in self.list_items()[0].context_menu],
                         ['L30020'])

    def test_a_file_is_playable(self):
        self.missing('smb://nas/tv/Some Show/Season 01/')
        self.assertEqual(self.list_items()[0].properties.get('IsPlayable'), 'true')

    def test_the_info_tag_carries_the_path_and_nothing_else(self):
        # A title would make ProcessItemByVideoInfoTag() match an episode by
        # that title instead of parsing the file name, and a media type would
        # hide Kodi's "Information" entry. Both broke importing once.
        self.missing('smb://nas/tv/Some Show/Season 01/')
        self.assertEqual(
            self.list_items()[0].info_tag.values,
            {'filenameandpath': 'smb://nas/tv/Some Show/Season 01/S01E02.mkv'})

    def test_a_directory_offers_only_the_exclusion(self):
        self.missing('smb://nas/movies/')
        self.assertEqual([entry[0] for entry in self.list_items()[0].context_menu],
                         ['L30020'])

    def test_the_entry_runs_through_the_plugin(self):
        self.missing('smb://nas/movies/')
        self.assertTrue(self.list_items()[0].context_menu[0][1].startswith('RunPlugin('))


class ExcludingTest(AddonTestCase):

    MISSING_EPISODE = 'smb://nas/tv/Some Show/Season 01/S01E02.mkv'

    def test_it_refreshes_the_container(self):
        self.act('exclude', self.MISSING_EPISODE)
        self.assertEqual(support.BUILTINS, ['Container.Refresh'])

    def test_the_file_disappears_from_its_directory(self):
        self.act('exclude', self.MISSING_EPISODE)
        self.assertEqual(self.labels(self.missing('smb://nas/tv/Some Show/Season 01/')), [])

    def test_a_directory_holding_only_excluded_videos_disappears(self):
        self.act('exclude', self.MISSING_EPISODE)
        self.assertEqual(self.labels(self.missing('smb://nas/tv/Some Show/')), [])

    def test_a_source_holding_only_excluded_videos_disappears(self):
        self.act('exclude', self.MISSING_EPISODE)
        self.assertEqual(self.labels(self.missing()), ['Movies', 'Some Add-on'])

    def test_an_excluded_directory_is_gone_from_its_parent(self):
        self.act('excludedir', 'smb://nas/movies/New Film (2020)/')
        self.assertEqual(self.labels(self.missing('smb://nas/movies/')),
                         ['Mixed', 'New Disc', 'Loose Unknown.mkv'])

    def test_an_excluded_source_is_gone_from_the_missing_side(self):
        self.act('excludedir', 'smb://nas/movies/')
        self.assertEqual(self.labels(self.missing()), ['TV Shows', 'Some Add-on'])

    def test_including_brings_the_file_back(self):
        self.act('exclude', self.MISSING_EPISODE)
        self.act('include', self.MISSING_EPISODE)
        self.assertEqual(self.labels(self.missing('smb://nas/tv/Some Show/Season 01/')),
                         ['S01E02.mkv'])

    def test_a_failed_undo_is_reported_and_does_not_refresh(self):
        exclusions.add_directory('smb://nas/gone/')
        self.act('include', 'smb://nas/gone/film.mkv')
        self.assertEqual([message for _, message in support.NOTIFICATIONS], ['L30027'])
        self.assertEqual(support.BUILTINS, [])


class ExcludedSideTest(AddonTestCase):
    """The excluded side mirrors the structure of the missing one."""

    MISSING_EPISODE = 'smb://nas/tv/Some Show/Season 01/S01E02.mkv'

    def setUp(self):
        super().setUp()
        exclusions.add_file(self.MISSING_EPISODE)

    def test_it_lists_the_source_holding_the_exclusion(self):
        self.assertEqual(self.labels(self.excluded()), ['TV Shows'])

    def test_an_intermediate_directory_is_rebuilt_from_the_stored_path(self):
        self.assertEqual(self.labels(self.excluded('smb://nas/tv/')), ['Some Show'])

    def test_the_next_level_down_is_rebuilt_as_well(self):
        self.assertEqual(self.labels(self.excluded('smb://nas/tv/Some Show/')), ['Season 01'])

    def test_the_excluded_file_is_the_leaf(self):
        items = self.excluded('smb://nas/tv/Some Show/Season 01/')
        self.assertEqual(self.labels(items), ['S01E02.mkv'])
        self.assertEqual(items[0][0], self.MISSING_EPISODE)

    def test_every_entry_offers_the_undo(self):
        self.excluded('smb://nas/tv/')
        self.assertEqual(self.list_items()[0].context_menu[0][0], 'L30021')

    def test_rebuilding_the_structure_needs_no_directory_listing(self):
        self.excluded('smb://nas/tv/Some Show/')
        self.assertEqual([method for method, _ in support.JSONRPC_CALLS
                          if method == 'Files.GetDirectory'], [])


class ExcludedMarkerTest(AddonTestCase):
    """A directory excluded itself is marked, one merely leading to one is not."""

    def test_a_self_excluded_directory_carries_the_marker(self):
        exclusions.add_directory('smb://nas/movies/New Film (2020)/')
        self.assertEqual(self.labels(self.excluded('smb://nas/movies/')),
                         ['New Film (2020) (X)'])

    def test_only_the_self_excluded_one_is_marked(self):
        exclusions.add_directory('smb://nas/movies/New Film (2020)/')
        exclusions.add_file('smb://nas/movies/Mixed/Minions and Monsters.mkv')
        self.assertEqual(self.labels(self.excluded('smb://nas/movies/')),
                         ['Mixed', 'New Film (2020) (X)'])

    def test_an_excluded_source_keeps_its_label_and_is_marked(self):
        exclusions.add_directory('smb://nas/movies/')
        items = self.excluded()
        self.assertEqual(self.labels(items), ['Movies (X)'])
        self.assertTrue(items[0][2])
        self.assertEqual(self.list_items()[0].art['icon'], 'DefaultNetwork.png')


class InsideAnExcludedDirectoryTest(AddonTestCase):

    def setUp(self):
        super().setUp()
        exclusions.add_directory('smb://nas/movies/')

    def test_opening_it_shows_what_the_exclusion_hides(self):
        self.assertEqual(self.labels(self.excluded('smb://nas/movies/')),
                         ['Known Film (1999)', 'New Film (2020)', 'Disc Film (2001)',
                          'Mixed', 'New Disc', 'Loose Known.mkv', 'Loose Unknown.mkv'])

    def test_the_inherited_entries_offer_the_undo_as_well(self):
        self.excluded('smb://nas/movies/')
        self.assertEqual([item.context_menu[0][0] for item in self.list_items()],
                         ['L30021'] * 7)

    def test_undoing_an_inherited_file_frees_only_that_file(self):
        self.act('include', 'smb://nas/movies/Loose Unknown.mkv')
        self.assertEqual(self.labels(self.missing('smb://nas/movies/')),
                         ['Loose Unknown.mkv'])


class NothingToShowTest(AddonTestCase):
    """Both sides report emptiness the same way: a toast, and no success."""

    def setUp(self):
        super().setUp()
        support.SOURCES[:] = [{'label': 'Complete', 'file': 'smb://nas/complete/'}]

    def test_the_missing_side_reports_by_toast_not_by_dialogue(self):
        self.missing()
        self.assertEqual([message for _, message in support.NOTIFICATIONS], ['L30014'])
        self.assertEqual(support.MESSAGES, [])
        self.assertFalse(support.PLUGIN_STATE.get('succeeded'))

    def test_the_excluded_side_reports_the_same_way(self):
        self.excluded()
        self.assertEqual([message for _, message in support.NOTIFICATIONS], ['L30023'])
        self.assertEqual(support.MESSAGES, [])
        self.assertFalse(support.PLUGIN_STATE.get('succeeded'))

    def test_missing_sources_warrant_a_modal_dialogue(self):
        # A setup problem with an instruction attached, not a "nothing found".
        support.SOURCES[:] = []
        self.missing()
        self.assertEqual([heading for heading, _ in support.MESSAGES], ['L30012'])
        self.assertEqual(support.NOTIFICATIONS, [])

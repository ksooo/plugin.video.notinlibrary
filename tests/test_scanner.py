# -*- coding: utf-8 -*-
#
#  Copyright (C) 2026 ksooo
#  This file is part of Not in Library
#
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt for more information.
#
"""Tests for resources.lib.scanner."""

import unittest

# Importing support installs the xbmc* stubs, so it has to come first.
from tests.support import AddonTestCase

from resources.lib import library
from resources.lib import scanner


class ProtocolTest(unittest.TestCase):

    def test_protocol_of_a_remote_path(self):
        self.assertEqual(scanner.get_protocol('smb://nas/movies/'), 'smb')

    def test_a_local_path_has_no_protocol(self):
        self.assertEqual(scanner.get_protocol('/Volumes/Media/movies/'), '')


class ScannableTest(unittest.TestCase):

    def test_a_remote_source_is_scannable(self):
        self.assertTrue(scanner.is_scannable('smb://nas/movies/'))

    def test_plugin_sources_are_scannable(self):
        # An add-on can declare medialibraryscanpath, so its paths are walked.
        self.assertTrue(scanner.is_scannable('plugin://plugin.video.x/'))

    def test_the_playlists_pseudo_source_is_not(self):
        self.assertFalse(scanner.is_scannable('special://videoplaylists/'))

    def test_the_playlists_path_matches_without_trailing_slash(self):
        self.assertFalse(scanner.is_scannable('special://videoplaylists'))

    def test_other_special_paths_stay_scannable(self):
        self.assertTrue(scanner.is_scannable('special://profile/media/'))


class SourceIconTest(unittest.TestCase):

    def test_a_remote_source_gets_the_network_icon(self):
        self.assertEqual(scanner.get_source_icon('smb://nas/movies/'), 'DefaultNetwork.png')

    def test_a_plain_local_path_gets_the_hard_disk_icon(self):
        self.assertEqual(scanner.get_source_icon('/Volumes/Media/movies/'),
                         'DefaultHardDisk.png')

    def test_file_protocol_counts_as_local(self):
        self.assertEqual(scanner.get_source_icon('file:///Volumes/Media/'),
                         'DefaultHardDisk.png')

    def test_an_optical_source_gets_its_own_icon(self):
        self.assertEqual(scanner.get_source_icon('iso9660://'), 'DefaultDVDRom.png')

    def test_a_plugin_source_gets_the_folder_icon_kodi_uses(self):
        self.assertEqual(scanner.get_source_icon('plugin://plugin.video.x/'),
                         'DefaultFolder.png')


class ListDirectoryTest(AddonTestCase):

    def test_non_video_files_are_filtered_out(self):
        entries = scanner.list_directory('smb://nas/movies/', library.load())
        self.assertNotIn('poster.jpg', [entry.label for entry in entries])

    def test_an_unreadable_directory_yields_none(self):
        self.assertIsNone(scanner.list_directory('smb://nas/gone/', library.load()))


class DiscFolderTest(AddonTestCase):

    def test_a_disc_structure_is_spotted(self):
        entries = scanner.list_directory('smb://nas/movies/New Disc/', library.load())
        self.assertTrue(scanner.is_disc_folder(entries))

    def test_a_plain_folder_is_no_disc_folder(self):
        entries = scanner.list_directory('smb://nas/movies/Mixed/', library.load())
        self.assertFalse(scanner.is_disc_folder(entries))


class FindSourceTest(AddonTestCase):

    def test_a_longer_source_wins_over_a_shorter_matching_one(self):
        self.assertEqual(scanner.find_source_for('smb://nas/tv/Some Show/').label, 'TV Shows')

    def test_a_path_outside_every_source_has_none(self):
        self.assertIsNone(scanner.find_source_for('smb://elsewhere/stuff/'))

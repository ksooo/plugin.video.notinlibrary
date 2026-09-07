# -*- coding: utf-8 -*-
#
#  Copyright (C) 2026 ksooo
#  This file is part of Not in Library
#
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt for more information.
#
"""Tests for resources.lib.library."""

import unittest

# Importing support installs the xbmc* stubs, so it has to come first.
from tests.support import AddonTestCase

from resources.lib import library


class SplitStackTest(unittest.TestCase):

    def test_a_plain_path_is_no_stack(self):
        self.assertEqual(library.split_stack('smb://nas/movies/a.mkv'),
                         ['smb://nas/movies/a.mkv'])

    def test_a_stack_is_split_into_its_parts(self):
        self.assertEqual(
            library.split_stack('stack://smb://nas/a-cd1.mkv , smb://nas/a-cd2.mkv'),
            ['smb://nas/a-cd1.mkv', 'smb://nas/a-cd2.mkv'])

    def test_doubled_commas_are_unescaped(self):
        self.assertEqual(
            library.split_stack('stack://smb://nas/a,,b-cd1.mkv , smb://nas/c.mkv'),
            ['smb://nas/a,b-cd1.mkv', 'smb://nas/c.mkv'])


class VideoLibraryTest(unittest.TestCase):

    def test_every_part_of_a_stack_counts_as_known(self):
        known = library.VideoLibrary(library.split_stack('stack://a.mkv , b.mkv'))
        self.assertTrue(known.contains('b.mkv'))

    def test_has_entry_below_needs_the_separator(self):
        known = library.VideoLibrary(['smb://nas/movies extra/x.mkv'])
        self.assertFalse(known.has_entry_below('smb://nas/movies'))


class LoadTest(AddonTestCase):

    def test_entries_below_a_disc_folder_are_reported(self):
        self.assertTrue(
            library.load().has_entry_below('smb://nas/movies/Disc Film (2001)/'))

    def test_a_disc_folder_outside_the_library_has_none(self):
        self.assertFalse(library.load().has_entry_below('smb://nas/movies/New Disc/'))

    def test_episodes_and_movies_both_land_in_the_set(self):
        known = library.load()
        self.assertTrue(known.contains('smb://nas/movies/Loose Known.mkv'))
        self.assertTrue(known.contains('smb://nas/tv/Some Show/Season 01/S01E01.mkv'))

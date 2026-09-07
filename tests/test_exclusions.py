# -*- coding: utf-8 -*-
#
#  Copyright (C) 2026 ksooo
#  This file is part of Not in Library
#
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt for more information.
#
"""Tests for resources.lib.exclusions."""

import json
import os
import unittest

# Importing support installs the xbmc* stubs, so it has to come first.
from tests.support import AddonTestCase

from resources.lib import exclusions


class ExclusionListTest(unittest.TestCase):

    def test_prefix_match_needs_the_trailing_separator(self):
        excluded = exclusions.ExclusionList(directories=['smb://nas/movies/'])
        self.assertFalse(excluded.contains('smb://nas/movies extra/film.mkv'))

    def test_a_file_below_an_excluded_directory_is_excluded(self):
        excluded = exclusions.ExclusionList(directories=['smb://nas/movies/'])
        self.assertTrue(excluded.contains('smb://nas/movies/New Film (2020)/movie.mkv'))

    def test_the_excluded_directory_itself_is_excluded(self):
        excluded = exclusions.ExclusionList(directories=['smb://nas/movies/'])
        self.assertTrue(excluded.contains('smb://nas/movies/'))


class PersistenceTest(AddonTestCase):

    def test_nothing_is_excluded_initially(self):
        self.assertEqual(exclusions.load(), exclusions.ExclusionList())

    def test_a_file_is_stored_as_a_file(self):
        path = 'smb://nas/movies/Loose Unknown.mkv'
        exclusions.add_file(path)
        self.assertEqual(exclusions.load(), exclusions.ExclusionList(files=[path]))

    def test_a_directory_is_stored_as_a_directory(self):
        path = 'smb://nas/movies/New Film (2020)/'
        exclusions.add_directory(path)
        self.assertEqual(exclusions.load(), exclusions.ExclusionList(directories=[path]))

    def test_the_list_lands_in_the_profile_directory(self):
        exclusions.add_file('smb://nas/movies/Loose Unknown.mkv')
        self.assertTrue(os.path.isfile(self.profile_path('exclusions.json')))

    def test_a_covered_entry_is_dropped_as_redundant(self):
        exclusions.add_file('smb://nas/movies/Loose Unknown.mkv')
        exclusions.add_directory('smb://nas/movies/')
        self.assertEqual(exclusions.load(),
                         exclusions.ExclusionList(directories=['smb://nas/movies/']))

    def test_a_directory_exclusion_can_be_taken_back(self):
        exclusions.add_directory('smb://nas/movies/')
        exclusions.remove('smb://nas/movies/')
        self.assertEqual(exclusions.load(), exclusions.ExclusionList())


class DissolveTest(AddonTestCase):
    """Undoing an entry below an excluded directory dissolves that exclusion."""

    def test_the_ancestor_is_replaced_by_its_siblings(self):
        exclusions.add_directory('smb://nas/movies/')
        exclusions.remove('smb://nas/movies/Loose Unknown.mkv')
        # Every sibling directory has to be excluded, even the ones holding an
        # imported movie. Only files may be skipped for already being known.
        self.assertEqual(
            exclusions.load(),
            exclusions.ExclusionList(directories=['smb://nas/movies/Disc Film (2001)/',
                                                  'smb://nas/movies/Known Film (1999)/',
                                                  'smb://nas/movies/Mixed/',
                                                  'smb://nas/movies/New Disc/',
                                                  'smb://nas/movies/New Film (2020)/']))

    def test_it_walks_down_every_level(self):
        exclusions.add_directory('smb://nas/tv/')
        exclusions.remove('smb://nas/tv/Some Show/Season 01/S01E02.mkv')
        # Nothing else lives along that path, so the whole exclusion is gone.
        self.assertEqual(exclusions.load(), exclusions.ExclusionList())

    def test_an_unreadable_directory_leaves_the_list_untouched(self):
        exclusions.add_directory('smb://nas/gone/')
        self.assertFalse(exclusions.remove('smb://nas/gone/film.mkv'))
        self.assertEqual(exclusions.load(),
                         exclusions.ExclusionList(directories=['smb://nas/gone/']))


class FileFormatTest(AddonTestCase):

    def write_raw(self, content):
        os.makedirs(self.profile_path(''), exist_ok=True)
        with open(self.profile_path('exclusions.json'), 'w', encoding='utf-8') as stream:
            stream.write(content)

    def test_a_version_1_file_is_migrated_to_files(self):
        path = 'smb://nas/movies/Loose Unknown.mkv'
        self.write_raw(json.dumps({'version': 1, 'paths': [path]}))
        self.assertEqual(exclusions.load(), exclusions.ExclusionList(files=[path]))

    def test_a_damaged_file_yields_an_empty_list(self):
        self.write_raw('{ this is not json')
        self.assertEqual(exclusions.load(), exclusions.ExclusionList())

    def test_an_unknown_version_yields_an_empty_list(self):
        self.write_raw(json.dumps({'version': 99, 'files': ['smb://nas/x.mkv']}))
        self.assertEqual(exclusions.load(), exclusions.ExclusionList())


class ChildrenOfTest(unittest.TestCase):

    def test_an_intermediate_directory_is_rebuilt_from_a_stored_file(self):
        excluded = exclusions.ExclusionList(files=['smb://nas/tv/Show/Season 01/ep.mkv'])
        directories, files = excluded.children_of('smb://nas/tv/')
        self.assertEqual(directories, {'smb://nas/tv/Show/': False})
        self.assertEqual(files, [])

    def test_a_directory_excluded_itself_is_marked(self):
        excluded = exclusions.ExclusionList(directories=['smb://nas/tv/Show/'])
        directories, _ = excluded.children_of('smb://nas/tv/')
        self.assertEqual(directories, {'smb://nas/tv/Show/': True})

    def test_a_file_directly_below_is_returned_as_a_file(self):
        excluded = exclusions.ExclusionList(files=['smb://nas/tv/ep.mkv'])
        directories, files = excluded.children_of('smb://nas/tv/')
        self.assertEqual((directories, files), ({}, [('ep.mkv', 'smb://nas/tv/ep.mkv')]))

# Not in Library

A Kodi video add-on that finds the videos in your sources which have no entry in the video library.

## What it does

The add-on walks through all video sources of the active Kodi profile and lists every video file
that Kodi has no video library entry for.

The top level has two entries, **Missing** and **Excluded**. Both are browsed the same way, and both
preserve the original folder structure:

* **Below each of them** — your video sources
* **Below those** — only the directories that actually lead somewhere
* **Leaf level** — the files themselves

Files can be played straight from the list.

This makes it easy to spot media that was never picked up by the scraper — because of a naming
issue, a missing content setting, or simply because the library scan was never run for that folder.

The add-on only reads your media. It never moves, renames or deletes anything.

## Getting things into the library

The add-on brings no import entry of its own — Kodi's context menu entry **Information** already
does the right thing. It scrapes exactly the selected file and adds it to the library, and it works
here because the file items of this add-on carry the real file path, so Kodi picks the scraper
configured for that path.

There is deliberately nothing for importing a whole directory either, because Kodi has no mechanism
for importing one selectively:

* `UpdateLibrary(video,<path>)` always scans the **whole tree** below the path, and it knows nothing
  about this add-on's exclusions — it would happily import everything you excluded.
* `OnItemInfo()` on a folder does something else entirely: it takes the first video file in it and
  scrapes the folder as *one single movie*.

So a directory is imported one file at a time, or through Kodi's own *Scan for new content* in the
file view if importing the whole tree really is what you want.

Either way, scraping only does something for paths that have a content type set. That is the single
most common reason for a video to be missing from the library in the first place.

## Excluding videos

Not everything that is missing from the library is supposed to be there — trailers, home videos,
sample files. The context menu entry **Exclude from library import** takes care of that, both on a
single file and on a directory or a whole source, where it covers everything below it.

Excluded entries disappear from the *Missing* side, and so do directories and sources that
hold nothing but excluded videos. Excluding a directory also drops the entries below it from the
list, since they are covered anyway.

The *Excluded* side shows the same structure, rebuilt from the stored paths alone — it needs no
directory listings and works even while a source is offline. Opening an excluded directory shows
what the exclusion hides.

A directory that carries an exclusion of its own is marked with a trailing **(X)**. Without the
marker it is merely on the way to an excluded file further down, and undoing it would free that
whole subtree rather than one entry.

The context menu entry **Allow library import** undoes an exclusion, and it is available on every
entry of that side:

* on an entry that is excluded itself, it is simply removed from the list
* on an entry **below** an excluded directory, that directory's exclusion is dissolved: it is
  replaced by explicit exclusions of everything beside the path leading down to the chosen entry,
  so only that entry becomes importable again. Entries that already are in the video library are
  left out, since they never show up as missing anyway. This reads every directory on the way down;
  if one of them cannot be read, nothing is changed at all.
* on an intermediate directory, the whole subtree below it becomes importable again — mirroring how
  excluding a directory works

The list lives in `special://profile/addon_data/plugin.video.notinlibrary/exclusions.json`,
so it belongs to the profile it was created in. It is written via a temporary file, so an
interrupted write cannot truncate it, and a damaged file is treated as an empty list rather than
breaking the add-on. Excluding something has no effect on Kodi itself — it changes nothing about how
Kodi scans, it only filters this add-on's listings.

Both sides are reachable directly, as
`plugin://plugin.video.notinlibrary/?action=list&mode=missing` and `…&mode=excluded`. Add
either as a favourite or as a video source to get to it straight from the video window.

## How it decides what is missing

Directories are listed with `Files.GetDirectory` using `media: "files"`, and the video library is
fetched once per invocation via `VideoLibrary.GetMovies`, `GetEpisodes` and `GetMusicVideos` with the
`file` property. A file counts as missing when its path is not in that set.

The obvious choice, `media: "video"`, **cannot** be used here. It resolves every item against the
video database, and `CVideoDatabase::GetMovieId()` falls back to *"any movie whose file lives in this
path"* for a directory. Kodi therefore replaces a folder holding an imported movie by that movie —
`FillFileItem()` calls `SetFromVideoInfoTag()`, which overwrites label, path and the folder flag. The
folder and everything below it are then absent from the answer, so newly added files in it can never
be found. This is not something the caller can filter around; the information is gone.

Doing the matching here means two things have to be done by hand:

* **Video extensions** come from `xbmc.getSupportedMedia('video')` — the very same source
  `Files.GetDirectory` uses for `media: "video"`, so the result is identical.
* **Stacked files** are split apart the way `CStackDirectory::GetPaths()` does it, since every part
  of a stack belongs to one library entry.

What is *not* applied any more are the exclude regular expressions from `advancedsettings.xml`.
Files that Kodi would hide from a video listing can therefore show up here.

Two more things worth knowing:

* A folder containing `VIDEO_TS` or `BDMV` is treated as one medium rather than a directory of
  videos — otherwise its VOB and IFO files would be offered as missing videos one by one. It counts
  as imported when any library entry lives below it.
* A directory that is a TV show in the library is still descended into, so missing episodes of an
  already known show do show up.

## Settings

| Setting | Default | Effect |
| --- | --- | --- |
| Show progress while searching | on | Show a progress dialogue with the directory currently being examined. |

Sources that can never end up in the video library are always skipped — the playlists folder, and
anything addressed through `videodb://`, `library://`, `pvr://`, `upnp://`, `addons://` and the
like. Add-on sources are **not** among them: an add-on can declare `medialibraryscanpath` in its
`addon.xml`, and Kodi then does scan its paths, so `plugin://` sources are walked like any other.

Only directories that actually contain something missing are listed, which means looking ahead into
every subdirectory. The descent stops at the first hit, so this is cheap for directories that do
hold missing videos and costs a full walk only for those that do not.

The search is done live on every navigation step; nothing is cached. It can be interrupted at any
time by shutting Kodi down or by leaving the add-on.

## Requirements

Kodi 20 (Nexus) or later — the add-on uses the `xbmc.python` 3.0.0 API.

## Installation

Copy or symlink this directory into your Kodi `addons` folder, for example:

```sh
ln -s "$PWD" ~/.kodi/addons/plugin.video.notinlibrary
```

On macOS the add-on folder is `~/Library/Application Support/Kodi/addons`.

## Development

### Tests

The add-on logic runs without Kodi. `tests/support.py` installs minimal stand-ins for the `xbmc*`
modules — including a simulated Kodi file tree and a fake JSON-RPC endpoint — so routing, scanning,
the breadcrumbs and the exclusion handling behave as they would inside Kodi:

```sh
python3 -m unittest discover -s tests -t .
```

Plain `unittest`, no dependencies beyond the standard library. Every test starts from a fresh tree
and an empty profile, so they can run in any order.

The simulated tree in `support.build_tree()` covers the cases that are easy to get wrong: a movie
already in the library next to one that is not, a disc folder that is a library entry of its own, a
TV show whose folder is in the library while an episode is missing, a fully scanned source, Kodi's
playlists pseudo source, and a path belonging to no source at all.

What the tests cannot cover: the real JSON-RPC replies, playback, and anything the skin does — the
`Container.Content()` dependency of the icons, for instance, only shows up in a running Kodi.

### Building

```sh
python3 tools/make_zip.py
```

Writes `../plugin.video.notinlibrary-<version>.zip`, taking the version from `addon.xml`. The
archive holds only what Kodi runs: `tests/` and `tools/` stay out, as do the usual `.git`,
`__pycache__` and `.pyc` noise.

### Images

The images are generated, not hand drawn:

```sh
python3 tools/make_icon.py        # icon.png, the add-on icon
python3 tools/make_list_icons.py  # resources/media/, the two top level icons
```

The top level icons are a plus and a cross built from the same geometry, measured off Kodi's own
`DefaultAddSource.png` (256×256, bars 122 long and 28 thick) so that the plus matches what skins use
for "add". They ship with the add-on because no stock `Default*.png` offers a cross of matching
weight — `DefaultVideoDeleted.png` is a film camera with a badge, not a plain cross.

Note that skins only draw `ListItem.Icon` when the listing sets no content type. Estuary ties its
icon layout to `Container.Content()`, and Kodi leaves the video root empty for the same reason, so
the listings whose entries carry an icon set no content either.

## Licence

GPL-2.0-or-later. See [LICENSE.txt](LICENSE.txt).

# Keeping up with Kodi

What this add-on gets from Kodi, what it rebuilds on its own, and where a Kodi
change would show — loudly or not.

## Read live - nothing to maintain

Everything about your media is asked of Kodi at the moment it is needed, over
JSON-RPC:

| Method | Used for |
| --- | --- |
| `Files.GetSources` | the video sources of the active profile |
| `Files.GetDirectory` with `media: "files"` | the contents of one directory |
| `VideoLibrary.GetMovies` / `GetEpisodes` / `GetMusicVideos` | the paths the library knows |

These are public API. Nothing here caches, so there is no stale state to
maintain — restart the add-on and it sees today's Kodi.

## Reimplemented - keep an eye on this

### Breaks loudly

A renamed or removed JSON-RPC method. Listings turn up empty and `jsonrpc.py`
logs the error it got back. Hard to miss, quick to find.

### Breaks quietly

These mirror Kodi behaviour that lives in C++ and cannot be asked for over the
API. When Kodi changes them, nothing errors out — the listing is simply wrong.

* **Stack splitting**, `library.split_stack()`, mirrors
  `CStackDirectory::GetPaths()`: strip `stack://`, split on `" , "`, undouble
  the commas. If that format ever changes, the parts of a stacked movie stop
  matching the library and the movie shows up as missing.
* **Disc folders**, `scanner.is_disc_folder()`, recognised by a `VIDEO_TS` or
  `BDMV` subdirectory. A new disc layout would make the add-on walk into it and
  offer its individual streams as missing videos.
* **The protocol list** in `scanner.is_scannable()` is hand-kept. A new Kodi
  protocol is treated as scannable and gets walked; one that Kodi teaches to
  scan stays hidden until the list is updated. Note that `plugin` is
  deliberately absent — see `CPluginDirectory::IsMediaLibraryScanningAllowed()`.
* **Source icons**, `scanner.get_source_icon()`, mirror
  `CSourcesDirectory::GetDirectory()`. Purely visual, but a source that looks
  different here than everywhere else in Kodi is confusing.
* **Exclude regular expressions** from `advancedsettings.xml` are *not*
  applied. `media: "files"` does not apply them, and they are not reachable
  over the API. Files Kodi hides from a video listing can show up here.

The video extension filter is the exception that needs no watching:
`xbmc.getSupportedMedia('video')` is the same source `Files.GetDirectory` uses
for `media: "video"`, so it cannot drift apart.

### Cosmetic

* **Item icons only appear while a listing sets no content type.** Estuary ties
  its icon layout to `Container.Content()`, which is why the two top level
  entries and both source levels deliberately set none. Another skin may draw
  them differently, or not at all.
* The breadcrumb separator `" / "` matches what Kodi puts between "Videos", the
  add-on name and the plugin category.

## Kodi internals this leans on

Three findings that cost an evening each. They are load-bearing, and none of
them is obvious from the outside.

* **`Files.GetDirectory` with `media: "video"` cannot be used to walk a tree.**
  It resolves every item against the video database, and for a *directory*
  `CVideoDatabase::GetMovieId()` falls back to "any movie whose file lives in
  this path". `FillFileItem()` then replaces the folder with that movie —
  label, path and folder flag — so the folder and everything below it are
  absent from the answer. Hence `media: "files"` plus a separate library
  lookup.
* **A file item's info tag carries the path and nothing else.** A media type
  hides Kodi's own *Information* entry, because `CVideoInfo::IsVisible()`
  expects `MediaTypeNone` for an item still to be scraped. A title makes
  `CVideoInfoScanner::ProcessItemByVideoInfoTag()` match an episode by that
  title instead of parsing season and episode out of the file name — and a file
  name never matches an episode title. The path alone keeps the tag non-empty,
  which `IsVisible()` also requires. A test guards this.
* **Cancelling works through `xbmc.Monitor().abortRequested()`.** Kodi sets
  that event not only when shutting down but also when the user cancels the
  busy dialogue of a running plugin call, via `CPythonInvoker::stop()`. That is
  what makes a long look-ahead interruptible.

## Tried against one installation only

Kodi 22 on macOS, Estuary, a MySQL video library, NFS sources. Everything else
— other skins, SQLite libraries, SMB or local sources, Windows paths with
backslashes — is reasoned about but untested. The path helpers in `scanner.py`
handle both separators, which is the most likely place for a surprise.

## Tests

The add-on logic runs without Kodi. `tests/support.py` installs stand-ins for
the `xbmc*` modules — a simulated file tree and a fake JSON-RPC endpoint — so
routing, scanning, the breadcrumbs and the exclusion handling behave as they
would inside Kodi:

```sh
python3 -m unittest discover -s tests -t .
```

Plain `unittest`, nothing beyond the standard library. Every test starts from a
fresh tree and an empty profile, so they run in any order.

The tree in `support.build_tree()` covers the cases that are easy to get wrong:
a movie already in the library next to one that is not, a disc folder that is a
library entry of its own, a TV show whose folder is in the library while an
episode is missing, a fully scanned source, Kodi's playlists pseudo source, and
a path belonging to no source at all.

Out of reach of the tests: the real JSON-RPC replies, playback, and everything
the skin does.

## Images

The images are generated, not hand drawn:

```sh
python3 tools/make_icon.py        # resources/icon.png, the add-on icon
python3 tools/make_list_icons.py  # resources/media/, the two top level icons
```

The top level icons are a plus and a cross built from the same geometry,
measured off Kodi's own `DefaultAddSource.png` (256×256, bars 122 long and 28
thick) so that the plus matches what skins use for "add". They ship with the
add-on because no stock `Default*.png` offers a cross of matching weight —
`DefaultVideoDeleted.png` is a film camera with a badge, not a plain cross.

## Checking a real install

Changes to `.py` files take effect the next time the add-on is opened — Kodi
gives every plugin call a fresh sub-interpreter. Changes to `addon.xml`,
`resources/settings.xml` and the `strings.po` files need a Kodi restart, a
changed `resources/icon.png` also a cleared texture cache.

Worth a look in `kodi.log` after a change: entries prefixed with
`[plugin.video.notinlibrary]` are this add-on's own. Failed JSON-RPC calls are
logged at debug level, so debug logging has to be on to see them.

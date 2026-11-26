# YouTube Music Downloader

A lightweight CLI tool for downloading audio from YouTube Music playlists and individual tracks.

## Features

- Download YouTube Music playlists and individual tracks
- MP3, Opus, FLAC, WAV, or M4A output
- Source mode that keeps the original stream without re-encoding
- Embed title, artist, album, and track number
- Embed YouTube thumbnails as album artwork
- Report source and output codec, bitrate, and copy/transcode mode
- Search and save lyrics as `.lrc` files
- Multiple lyrics providers with automatic fallback
- Validate lyrics matches using title, artist, album, and duration
- Prefer synchronized lyrics when available
- Automatically skip existing tracks
- Automatic browser cookie detection
- Select a specific browser for YouTube cookies
- Inspect detected browsers and cookie availability
- Support custom output directories
- Support Unicode filenames
- Simple download summary
- Optional PySide6 desktop interface (preview)

## Requirements

- Python 3.14+
- [uv](https://docs.astral.sh/uv/)
- FFmpeg
- [Deno](https://deno.com/)

Deno is required by current `yt-dlp` versions for YouTube JavaScript challenge solving.

FFmpeg is required for audio conversion, remuxing, metadata processing, and audio format conversion.

## Installation

Clone the repository:

```bash
git clone https://github.com/JunWei2769/youtube-music-downloader.git
cd youtube-music-downloader
```

Install the CLI:

```bash
uv tool install .
```

After installation, `ytmusic-dl` is available directly from your terminal:

```bash
ytmusic-dl --help
```

## System Dependencies

Make sure FFmpeg and Deno are installed before downloading.

### Fedora

```bash
sudo dnf install ffmpeg deno
```

### Ubuntu / Debian

Install FFmpeg:

```bash
sudo apt install ffmpeg
```

Install Deno:

```bash
curl -fsSL https://deno.land/install.sh | sh
```

Restart your terminal or reload your shell configuration after installing Deno.

### Windows

Install FFmpeg and make sure it is available in your `PATH`.

Install FFmpeg:

```powershell
winget install Gyan.FFmpeg.Shared
```

Install Deno:

```powershell
irm https://deno.land/install.ps1 | iex
```

Restart your terminal after installing Deno.

Verify both dependencies:

```powershell
ffmpeg -version
deno --version
```

### macOS

Using Homebrew:

```bash
brew install ffmpeg deno
```

Verify both dependencies:

```bash
ffmpeg -version
deno --version
```

Deno must be available in your `PATH` so that `yt-dlp` can use it.

## Usage

`ytmusic-dl` supports both YouTube Music playlists and individual tracks.

Examples:

- Playlist URL:

  ```text
  https://music.youtube.com/playlist?list=...
  ```

- Individual track URL:

  ```text
  https://music.youtube.com/watch?v=...
  ```

### Download a playlist

```bash
ytmusic-dl "PLAYLIST_URL"
```

### Download a single track

```bash
ytmusic-dl "TRACK_URL"
```

Example:

```bash
ytmusic-dl \
  "https://music.youtube.com/watch?v=VIDEO_ID" \
  --audio-format opus
```

Single track downloads use the same processing pipeline as playlists:

- Audio conversion
- Metadata embedding
- Thumbnail embedding
- Lyrics downloading
- Browser cookie handling

By default, audio is downloaded as MP3 into:

```text
downloads/
```

The downloader automatically looks for a browser profile containing usable YouTube cookies when they are needed.

### Audio Formats

The downloader supports five output formats plus a source-preserving mode:

- MP3
- Opus
- FLAC
- WAV
- M4A
- Source (no re-encoding)

Converted formats are processed through FFmpeg and receive the same metadata and thumbnail pipeline. Source mode keeps the original stream as `yt-dlp` downloaded it.

### Download as MP3

MP3 is the default format:

```bash
ytmusic-dl \
  "PLAYLIST_URL" \
  --audio-format mp3
```

### Download as Opus

```bash
ytmusic-dl \
  "PLAYLIST_URL" \
  --audio-format opus
```

Opus output is generated through FFmpeg audio extraction.

### Download as FLAC

```bash
ytmusic-dl \
  "PLAYLIST_URL" \
  --audio-format flac
```

FLAC output is generated through FFmpeg audio extraction and supports embedded metadata and album artwork.

### Download as WAV

```bash
ytmusic-dl \
  "PLAYLIST_URL" \
  --audio-format wav
```

WAV output is generated through FFmpeg audio extraction and supports embedded ID3 metadata and album artwork.

> Note: Converting YouTube audio to FLAC or WAV does not increase the original source quality. These formats preserve the decoded audio without additional lossy compression, but they cannot restore information that was not present in the original YouTube stream. The downloader prints a warning when FLAC or WAV is requested from a lossy source.

### Download as M4A

```bash
ytmusic-dl \
  "PLAYLIST_URL" \
  --audio-format m4a
```

M4A output uses AAC at 256 kbps and supports embedded metadata and album artwork.

### Download as source (no re-encoding)

```bash
ytmusic-dl \
  "PLAYLIST_URL" \
  --audio-format source
```

Source mode keeps the best original audio stream in its native container, usually M4A/AAC or WebM/Opus, without re-encoding. Metadata and artwork are embedded when the container supports it (M4A); WebM files are kept as downloaded with a warning.

Conversion quality is fixed per format:

- MP3 — V0 variable bitrate
- Opus — 160 kbps
- M4A — 256 kbps AAC

### Custom output directory

```bash
ytmusic-dl \
  "PLAYLIST_URL" \
  --output downloads/music
```

### Disable lyrics

```bash
ytmusic-dl \
  "PLAYLIST_URL" \
  --no-lyrics
```

### Disable thumbnails

```bash
ytmusic-dl \
  "PLAYLIST_URL" \
  --no-thumbnail
```

## Lyrics

The downloader supports multiple lyrics providers.

The current provider order is:

1. **LRCLIB**
2. **NetEase Cloud Music**

The downloader searches multiple lyrics providers and selects the best validated result.

Lyrics candidates are validated using:

- Track title similarity
- Artist matching
- Track duration
- Album matching, as supporting evidence
- Lyrics availability

When multiple suitable results are available, synchronized lyrics are preferred.

Lyrics are saved as separate `.lrc` files alongside the downloaded audio.

Example:

```text
downloads/
└── 空耳 + 还你茉莉 (Live)/
    ├── 01 - 单依纯 - 空耳 + 还你茉莉 (Live).opus
    └── 01 - 单依纯 - 空耳 + 还你茉莉 (Live).lrc
```

If no suitable lyrics are found, the audio download continues without creating an `.lrc` file.

During playlist and single-track downloads, lyrics are saved only when the match reaches `--lyrics-confidence` (default `high`). Pass `--lyrics-confidence medium` to accept medium-confidence matches as well.

You can disable lyrics completely with:

```bash
ytmusic-dl "PLAYLIST_URL" --no-lyrics
```

### Search and download lyrics without audio

The `lyrics` commands search providers and write lyrics without downloading any audio and without requiring browser cookies.

Search without saving anything:

```bash
ytmusic-dl lyrics search "空耳 + 还你茉莉 (Live)" --artist "单依纯"
```

Save the best match:

```bash
ytmusic-dl lyrics download "空耳 + 还你茉莉 (Live)" --artist "单依纯" --best
```

Save a specific candidate from the search list:

```bash
ytmusic-dl lyrics download "空耳 + 还你茉莉 (Live)" --artist "单依纯" --select 2
```

Use a YouTube Music track URL instead of a title and artist:

```bash
ytmusic-dl lyrics download "https://music.youtube.com/watch?v=VIDEO_ID" --best
```

Each candidate shows its provider, score, confidence (`high`, `medium`, `low`), match reasons, rejection reasons, and edition notes. Every discovered candidate is scored; the best 10 are shown by default.

`--best` saves a high-confidence match automatically. A medium-confidence match asks for confirmation first, or needs `--yes` when running without a terminal. Low-confidence matches can only be saved by choosing them explicitly with `--select N`. `--min-confidence high` restricts `--best` to high-confidence matches only.

Provider diagnostics are hidden by default. Pass `--verbose` to see NetEase search and lyrics requests.

Files are written to `downloads/lyrics/` by default as `<Artist> - <Title>.lrc`. Synchronized lyrics are preferred, with plain lyrics as a fallback. Existing files are not replaced unless you pass `--overwrite`.

| Option                   | Description                                          |
| ------------------------ | ---------------------------------------------------- |
| `--artist NAME`          | Artist name (required when searching by title)       |
| `--album NAME`           | Album name                                           |
| `--duration SECONDS`     | Track duration used for matching                     |
| `--limit N`              | Maximum candidates to show, best first (default: 10, 0 shows all) |
| `--best`                 | Save the highest-scoring accepted candidate          |
| `--select N`             | Save candidate N from the search list                |
| `--min-confidence LEVEL` | Minimum confidence for `--best`: `high` or `medium` (default: `medium`) |
| `--yes`                  | Confirm a medium-confidence match without prompting  |
| `-o, --output DIR`       | Output directory. Default: `downloads/lyrics`        |
| `-v, --verbose`          | Show provider diagnostics                            |
| `--overwrite`            | Replace an existing lyrics file                      |

## Browser Cookies

The downloader can use cookies from supported browsers through `yt-dlp`.

This allows the downloader to access YouTube using an existing browser session when necessary.

When no browser is specified, the downloader automatically searches detected browser profiles for usable YouTube cookies. Cookie detection only runs when a track actually needs downloading, so re-running a playlist whose tracks already exist does not require cookies.

If no usable cookies are found, the download continues without them, and `yt-dlp` reports any access errors per track.

You can check detected browser profiles with:

```bash
ytmusic-dl --list-browsers
```

To explicitly select a browser:

```bash
ytmusic-dl "PLAYLIST_URL" --browser vivaldi
```

### Supported Browsers

The downloader can detect profiles from browsers including:

- Vivaldi
- Chrome
- Chromium
- Brave
- Firefox
- Edge
- Opera
- Whale

Whether usable YouTube cookies are available depends on the browser profile, operating system, and browser state.

The browser may need to be completely closed before cookies can be read successfully, depending on the browser and operating system.

Do not share or commit browser cookie files.

### List Detected Browsers

```bash
ytmusic-dl --list-browsers
```

Example:

```text
============================================================
Detected Browsers
============================================================

Browser: vivaldi
Profile: /home/user/.config/vivaldi/Default
Status:  YouTube cookies available

Browser: firefox
Profile: /home/user/.config/mozilla/firefox/xxxxxxxx.default-release
Status:  YouTube cookies available
```

This command is useful for troubleshooting browser profile and cookie detection before downloading.

## Options

| Option                  | Description                                                         |
| ----------------------- | ------------------------------------------------------------------- |
| `--output DIR`          | Output directory. Default: `downloads`                              |
| `--audio-format FORMAT` | Audio format: `mp3`, `opus`, `flac`, `wav`, `m4a`, or `source` |
| `--browser BROWSER`     | Browser to use for YouTube cookies                                  |
| `--list-browsers`       | List detected browsers and YouTube cookie availability              |
| `--no-lyrics`           | Disable lyrics downloading                                          |
| `--lyrics-confidence LEVEL` | Minimum lyrics confidence to save: `high` (default) or `medium` |
| `--no-thumbnail`        | Disable thumbnail embedding                                         |
| `-h, --help`            | Show help                                                           |

## Combine Options

```bash
ytmusic-dl \
  "PLAYLIST_URL" \
  --audio-format flac \
  --output downloads/music \
  --browser vivaldi \
  --no-lyrics \
  --no-thumbnail
```

## Desktop Application (preview)

The desktop interface is optional and requires PySide6. Install the GUI extra:

```bash
uv sync --extra gui
```

Run it:

```bash
uv run --extra gui ytmusic-dl-gui
```

For an installed CLI:

```bash
uv tool install ".[gui]"
ytmusic-dl-gui
```

The preview has three tabs: **Music Download**, **Lyrics Only**, and **Settings**.

- **Music Download** is functional: a playlist or track URL, output directory, audio format (including `source` and `m4a`), browser cookies, lyrics and thumbnail options, live per-track progress, cancellation, a download log, and a source/output quality report.
- **Lyrics Only** is functional: search by title and artist or by YouTube Music URL, review every candidate with confidence and match reasons, preview synchronized or plain lyrics, and save to an `.lrc` file. Rejected candidates cannot be saved, and medium/low matches ask for confirmation.
- **Settings** reports the detected FFmpeg, FFprobe, and Deno locations and versions, including installations outside `PATH`. Detected tool directories are added to `PATH` at startup so Finder launches work.

PySide6 6.12 has been verified with Python 3.14 on macOS. Fedora testing is still pending.

On macOS, the app prepends detected Homebrew, `/usr/local`, and `~/.deno` directories to `PATH` at startup, so it works even when launched without the shell environment.

## Troubleshooting

### `HTTP Error 403: Forbidden`

YouTube refused the media download. Sign in to YouTube in a supported browser, confirm cookies are detected with:

```bash
ytmusic-dl --list-browsers
```

then let the downloader detect them automatically or pass `--browser NAME` explicitly.

### `Signature solving failed`

If `yt-dlp` reports errors such as:

```text
Signature solving failed
n challenge solving failed
The page needs to be reloaded.
```

make sure Deno is installed:

```bash
deno --version
```

You can verify that `yt-dlp` is using Deno by looking for:

```text
[youtube] [jsc:deno] Solving JS challenges using deno
```

If Deno is installed and the error continues, update the dependency — YouTube changes its player frequently and older `yt-dlp` releases stop solving the current challenges:

```bash
uv lock --upgrade-package yt-dlp
uv sync
```

For an installed CLI, reinstall it afterwards:

```bash
uv tool install --force .
```

## Output

Each download gets its own directory based on the playlist or track name.

Example playlist:

```text
downloads/
└── Album - 純妹妹/
    ├── 01 - 单依纯Official - 還有什麼更好的.opus
    ├── 01 - 单依纯Official - 還有什麼更好的.lrc
    ├── 02 - 单依纯Official - 純妹妹 (2025版).opus
    └── ...
```

Example single track:

```text
downloads/
└── 空耳 + 还你茉莉 (Live)/
    ├── 01 - 单依纯 - 空耳 + 还你茉莉 (Live).opus
    └── 01 - 单依纯 - 空耳 + 还你茉莉 (Live).lrc
```

The same output structure is used regardless of the selected audio format.

For example, a FLAC download:

```text
downloads/
└── Album - 光波/
    └── 01 - 单依纯Official - 光波.flac
```

A WAV download:

```text
downloads/
└── Album - 光波/
    └── 01 - 单依纯Official - 光波.wav
```

Audio files include:

- Title
- Artist
- Album
- Track number
- Embedded thumbnail

Metadata and artwork are embedded using format-appropriate tagging:

- MP3 — ID3 metadata and APIC artwork
- Opus — Vorbis comments and embedded artwork
- FLAC — Vorbis comments and embedded FLAC picture metadata
- WAV — ID3 metadata and APIC artwork
- M4A — MP4 atoms and embedded cover art

Source mode keeps the container `yt-dlp` chose, so the extension may be `.m4a` or `.webm` instead of the requested format. WebM files are not tagged.

Lyrics are saved separately as `.lrc` files when suitable lyrics are available.

## Existing Tracks

If a track already exists, it is skipped automatically:

```text
Skipped: 還有什麼更好的 (audio file already exists)
```

This makes it safe to run the same playlist again.

## Testing

Run the complete test suite:

```bash
uv run pytest -v
```

Current test status:

```text
195 passed
```

The GUI tests are skipped when PySide6 is not installed.

The test suite covers:

- Browser detection
- CLI argument parsing
- Audio downloading
- MP3, Opus, FLAC, WAV, M4A, and source output configuration
- Lyrics providers and matching
- Lyrics confidence, match reasons, and rejection reasons
- Lyrics-only search and download commands
- Metadata embedding
- Thumbnail embedding
- Download pipeline behavior
- Desktop window, lyrics search/preview/save, download progress/cancellation, and external tool detection

The pipeline tests do not depend on a real browser profile or usable YouTube cookies, so the suite runs the same way on any machine.

You can also run the lyrics-specific tests:

```bash
uv run pytest tests/test_lyrics.py -v
```

## Roadmap

See [docs/ROADMAP.md](docs/ROADMAP.md) for the current project review, known issues, and planned improvements.

## Development

Run directly from the repository:

```bash
uv run ytmusic-dl "PLAYLIST_URL"
```

Run tests:

```bash
uv run pytest -v
```

Check for whitespace errors:

```bash
git diff --check
```

## Legal Notice

This project is intended for personal and educational use.

Users are responsible for complying with YouTube's Terms of Service, applicable copyright laws, and the rights of content creators.

Only download content that you are legally permitted to download.

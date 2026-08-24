# YouTube Music Downloader

A lightweight CLI tool for downloading audio from YouTube Music playlists and individual tracks.

## Features

- Download YouTube Music playlists and individual tracks
- MP3 or Opus output
- Embed title, artist, album, and track number
- Embed YouTube thumbnails as album artwork
- Search and save lyrics as `.lrc` files
- Multiple lyrics providers with automatic fallback
- Validate lyrics matches using title, artist, and duration
- Prefer synchronized lyrics when available
- Automatically skip existing tracks
- Automatic browser cookie detection
- Select a specific browser for YouTube cookies
- Inspect detected browsers and cookie availability
- Support custom output directories
- Support Unicode filenames
- Simple download summary

## Requirements

- Python 3.14+
- [uv](https://docs.astral.sh/uv/)
- FFmpeg
- [Deno](https://deno.com/)

Deno is required by current `yt-dlp` versions for YouTube JavaScript challenge solving.

FFmpeg is required for audio conversion, remuxing, and metadata processing.

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

### Download as Opus

```bash
ytmusic-dl \
  "PLAYLIST_URL" \
  --audio-format opus
```

Opus output is generated through FFmpeg audio extraction.

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

You can disable lyrics completely with:

```bash
ytmusic-dl "PLAYLIST_URL" --no-lyrics
```

## Browser Cookies

The downloader can use cookies from supported browsers through `yt-dlp`.

This allows the downloader to access YouTube using an existing browser session when necessary.

When no browser is specified, the downloader automatically searches detected browser profiles for usable YouTube cookies.

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

| Option | Description |
| --- | --- |
| `--output DIR` | Output directory. Default: `downloads` |
| `--audio-format FORMAT` | Audio format: `mp3` or `opus` |
| `--browser BROWSER` | Browser to use for YouTube cookies |
| `--list-browsers` | List detected browsers and YouTube cookie availability |
| `--no-lyrics` | Disable lyrics downloading |
| `--no-thumbnail` | Disable thumbnail embedding |
| `-h, --help` | Show help |

## Combine Options

```bash
ytmusic-dl \
  "PLAYLIST_URL" \
  --audio-format opus \
  --output downloads/music \
  --browser vivaldi \
  --no-lyrics \
  --no-thumbnail
```

## Troubleshooting

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

Audio files include:

- Title
- Artist
- Album
- Track number
- Embedded thumbnail

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
59 passed
```

You can also run the lyrics-specific tests:

```bash
uv run pytest tests/test_lyrics.py -v
```

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

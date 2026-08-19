# YouTube Music Downloader

A lightweight CLI tool for downloading audio from YouTube Music playlists.

## Features

- Download YouTube Music playlists
- MP3 or Opus output
- Embed title, artist, album, and track number
- Embed YouTube thumbnails as album artwork
- Search and save lyrics as `.lrc` files
- Automatically skip existing tracks
- Automatic browser cookie detection
- Select a specific browser for YouTube cookies
- Inspect detected browsers and cookie availability
- Support custom output directories
- Support Unicode filenames
- Simple download summary

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- FFmpeg

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

Make sure FFmpeg is installed.

### Fedora

```bash
sudo dnf install ffmpeg
```

### Ubuntu / Debian

```bash
sudo apt install ffmpeg
```

## Usage

### Download a playlist

```bash
ytmusic-dl "PLAYLIST_URL"
```

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

Opus downloads preserve the original Opus audio stream without re-encoding.

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

### Select a browser

You can explicitly select a browser to use for YouTube cookies:

```bash
ytmusic-dl \
  "PLAYLIST_URL" \
  --browser vivaldi
```

Supported browsers include:

- Vivaldi
- Chrome
- Chromium
- Brave
- Firefox
- Edge
- Opera
- Whale
- Safari

The browser must contain usable YouTube cookies.

### List detected browsers

To check which browser profiles are detected and whether usable YouTube cookies are available:

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

This is useful for troubleshooting browser cookie detection.

### Combine options

```bash
ytmusic-dl \
  "PLAYLIST_URL" \
  --audio-format opus \
  --output downloads/music \
  --browser vivaldi \
  --no-lyrics \
  --no-thumbnail
```

## Options

| Option | Description |
|---|---|
| `--output DIR` | Output directory. Default: `downloads` |
| `--audio-format FORMAT` | Audio format: `mp3` or `opus` |
| `--browser BROWSER` | Browser to use for YouTube cookies |
| `--list-browsers` | List detected browsers and YouTube cookie availability |
| `--no-lyrics` | Disable lyrics downloading |
| `--no-thumbnail` | Disable thumbnail embedding |
| `-h, --help` | Show help |

## Browser Cookies

The downloader can use cookies from supported browsers through `yt-dlp`.

This allows the downloader to access YouTube using an existing browser session when necessary.

When no browser is specified, the downloader automatically searches detected browser profiles for usable YouTube cookies.

You can check the detected browser profiles with:

```bash
ytmusic-dl --list-browsers
```

To explicitly select a browser:

```bash
ytmusic-dl "PLAYLIST_URL" --browser vivaldi
```

The browser may need to be closed before cookies can be read successfully, depending on the browser and operating system.

Do not share or commit browser cookie files.

## Output

Each playlist gets its own directory.

Example:

```text
downloads/
└── Album - 純妹妹/
    ├── 01 - 单依纯Official - 還有什麼更好的.opus
    ├── 01 - 单依纯Official - 還有什麼更好的.lrc
    ├── 02 - 单依纯Official - 純妹妹 (2025版).opus
    ├── 02 - 单依纯Official - 純妹妹 (2025版).lrc
    └── ...
```

Audio files include:

- Title
- Artist
- Album
- Track number
- Embedded thumbnail

Lyrics are saved separately as `.lrc` files when available.

### Existing Tracks

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
46 passed
```

Run individual test modules when developing:

```bash
uv run pytest tests/test_browser.py -v
uv run pytest tests/test_cli.py -v
uv run pytest tests/test_downloader.py -v
uv run pytest tests/test_metadata.py -v
uv run pytest tests/test_pipeline.py -v
uv run pytest tests/test_thumbnail.py -v
```

## Development

When working directly from the repository, you can run the CLI without installing it:

```bash
uv run ytmusic-dl "PLAYLIST_URL"
```

Run the test suite:

```bash
uv run pytest -v
```

Check for whitespace errors before committing:

```bash
git diff --check
```

## Legal Notice

This project is intended for personal and educational use.

Users are responsible for complying with YouTube's Terms of Service, applicable copyright laws, and the rights of content creators.

Only download content that you are legally permitted to download.

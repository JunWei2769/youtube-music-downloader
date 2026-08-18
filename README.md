# YouTube Music Downloader

A lightweight CLI tool for downloading audio from YouTube Music playlists.

## Features

- Download YouTube Music playlists
- MP3 or Opus output
- Embed title, artist, album, and track number
- Embed YouTube thumbnails as album artwork
- Search and save lyrics as `.lrc` files
- Automatically skip existing tracks
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
git clone <repository-url>
cd youtube-music-downloader
```

Install dependencies:

```bash
uv sync
```

Make sure FFmpeg is installed:

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
uv run ytmusic-dl "PLAYLIST_URL"
```

By default, audio is downloaded as MP3 into:

```text
downloads/
```

### Download as Opus

```bash
uv run ytmusic-dl \
  "PLAYLIST_URL" \
  --audio-format opus
```

Opus downloads preserve the original Opus audio stream without re-encoding.

### Custom output directory

```bash
uv run ytmusic-dl \
  "PLAYLIST_URL" \
  --output downloads/music
```

### Disable lyrics

```bash
uv run ytmusic-dl \
  "PLAYLIST_URL" \
  --no-lyrics
```

### Disable thumbnails

```bash
uv run ytmusic-dl \
  "PLAYLIST_URL" \
  --no-thumbnail
```

### Combine options

```bash
uv run ytmusic-dl \
  "PLAYLIST_URL" \
  --audio-format opus \
  --output downloads/music \
  --no-lyrics \
  --no-thumbnail
```

## Options

| Option | Description |
|---|---|
| `--output DIR` | Output directory. Default: `downloads` |
| `--audio-format FORMAT` | Audio format: `mp3` or `opus` |
| `--no-lyrics` | Disable lyrics downloading |
| `--no-thumbnail` | Disable thumbnail embedding |
| `-h, --help` | Show help |

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
27 passed
```

## Legal Notice

This project is intended for personal and educational use.

Users are responsible for complying with YouTube's Terms of Service, applicable copyright laws, and the rights of content creators.

Only download content that you are legally permitted to download.

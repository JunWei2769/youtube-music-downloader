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

### System Dependencies

Make sure FFmpeg and Deno are installed before downloading.

#### Fedora

```bash
sudo dnf install ffmpeg deno
```

#### Ubuntu / Debian

Install FFmpeg:

```bash
sudo apt install ffmpeg
```

Install Deno:

```bash
curl -fsSL https://deno.land/install.sh | sh
```

Restart your terminal or reload your shell configuration after installing Deno.

#### Windows

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

#### macOS

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

On Windows, Chromium-based browser profiles are detected from their `User Data` directories. For example:

```text
C:\Users\<user>\AppData\Local\Vivaldi\User Data\Default
C:\Users\<user>\AppData\Local\Microsoft\Edge\User Data\Default
```

This command is useful for troubleshooting browser cookie detection before downloading.

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

The browser may need to be completely closed before cookies can be read successfully, depending on the browser and operating system.

Do not share or commit browser cookie files.

### Windows

Chromium-based browsers store their profiles under their `User Data` directory.

Common locations include:

```text
%LOCALAPPDATA%\Google\Chrome\User Data
%LOCALAPPDATA%\Microsoft\Edge\User Data
%LOCALAPPDATA%\Vivaldi\User Data
%LOCALAPPDATA%\BraveSoftware\Brave-Browser\User Data
```

Chromium cookie databases may be stored inside each profile at:

```text
<profile>\Cookies
```

or:

```text
<profile>\Network\Cookies
```

For example:

```text
C:\Users\<user>\AppData\Local\Vivaldi\User Data\Default\Network\Cookies
```

If a browser is running, its cookie database may be locked. Completely quit the browser before running:

```bash
ytmusic-dl --list-browsers
```

or downloading with:

```bash
ytmusic-dl "PLAYLIST_URL" --browser vivaldi
```

On Windows, browser profiles can be detected even when their cookies cannot be decrypted. If `--list-browsers` reports:

```text
Status:  No usable YouTube cookies
```

the issue may be related to the browser's cookie encryption or `yt-dlp`'s ability to decrypt that browser's cookies.

### macOS

macOS may restrict terminal applications from accessing browser cookie databases.

If Chrome cookies cannot be detected:

1. Open **System Settings → Privacy & Security → Full Disk Access**.
2. Enable Full Disk Access for the terminal application running `ytmusic-dl`.
3. Completely quit and reopen the terminal.
4. Check browser detection again:

```bash
ytmusic-dl --list-browsers
```

You should see a result similar to:

```text
Browser: chrome
Profile: /Users/your-user/Library/Application Support/Google/Chrome/Default
Status:  YouTube cookies available
```

## Troubleshooting

### `Signature solving failed`

If `yt-dlp` reports errors such as:

```text
Signature solving failed
n challenge solving failed
The page needs to be reloaded.
```

make sure Deno is installed and available in your `PATH`:

```bash
deno --version
```

Then retry the download.

You can verify that `yt-dlp` is using Deno by looking for:

```text
[youtube] [jsc:deno] Solving JS challenges using deno
```

If the debug output contains:

```text
[debug] JS runtimes: none
```

`yt-dlp` cannot find a supported JavaScript runtime.

### YouTube cookies are not detected

Run:

```bash
ytmusic-dl --list-browsers
```

If the browser is not listed:

- Make sure the browser is installed.
- Make sure the browser profile exists.
- Make sure you are logged into YouTube or YouTube Music in that profile.

If the browser is detected but shows:

```text
Status:  No usable YouTube cookies
```

make sure:

- You are logged into YouTube or YouTube Music in the selected browser.
- The browser profile is the profile where you are logged in.
- The browser is completely closed if cookie access is blocked while it is running.
- On Windows, the browser's cookies can be decrypted by `yt-dlp`.
- On macOS, the terminal application has Full Disk Access.

### Browser cookie database cannot be copied

If `yt-dlp` reports:

```text
Could not copy Chrome cookie database
```

completely close the browser and retry.

Chromium-based browsers may keep their cookie database locked while they are running.

### Windows DPAPI cookie decryption failure

If `yt-dlp` reports:

```text
Failed to decrypt with DPAPI
```

the browser may be detected correctly while its cookies cannot be decrypted.

This is a browser-cookie decryption issue handled by `yt-dlp`, rather than a browser profile detection issue.

First make sure the browser is completely closed and retry:

```bash
ytmusic-dl --list-browsers
```

If the problem persists, test the browser directly with `yt-dlp`:

```bash
yt-dlp --cookies-from-browser edge "VIDEO_URL"
```

or:

```bash
yt-dlp --cookies-from-browser vivaldi "VIDEO_URL"
```

This helps determine whether the issue is specific to `ytmusic-dl` or to `yt-dlp`'s browser cookie handling.

### Verify Deno

```bash
deno --version
```

### Verify FFmpeg

```bash
ffmpeg -version
```

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
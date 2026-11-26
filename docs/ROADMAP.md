# Project Review and Roadmap

Last reviewed: 2026-11-26  
Current release: `v0.2.0`

This document records the current project state, known issues, and the planned direction for future development. It is a planning document; listed items are not necessarily implemented yet.

## Current State

### Overview

YouTube Music Downloader is a Python CLI for downloading YouTube Music playlists and individual tracks. It supports:

- MP3, Opus, FLAC, and WAV output
- Embedded title, artist, album, and track-number metadata
- Embedded YouTube thumbnails
- Separate `.lrc` lyrics files
- LRCLIB and NetEase Cloud Music lyrics providers
- Title, artist, and duration-based lyrics matching
- Browser-cookie detection for several Chromium-based browsers and Firefox
- Automatic skipping of existing audio files
- Custom output directories and Unicode-safe filenames

### Architecture

The application is organized into focused modules under `src/ytmusic_dl/`:

- `cli.py`: argument parsing and command-line interaction
- `downloader.py`: `yt-dlp` extraction and audio downloading
- `browser.py`: browser profile and cookie detection
- `pipeline.py`: audio, metadata, thumbnail, and lyrics orchestration
- `lyrics.py`: provider integrations, search normalization, scoring, and writing
- `metadata.py`: format-specific metadata embedding
- `thumbnail.py`: thumbnail downloading and artwork embedding
- `models.py`: shared dataclasses
- `utils.py`: filename and path helpers

### Verification Snapshot

At the time of this review:

- 73 tests were collected.
- 70 tests passed.
- 3 tests failed because they depend on finding a real browser profile with usable YouTube cookies.
- The README still states `65 passed`, which is outdated.
- The working tree contained only a pre-existing untracked `.DS_Store`.

The failing pipeline tests do not mock `find_browser_with_cookies`, so they fail in environments without usable browser cookies. They should be made environment-independent before adding new features.

## Known Issues and Risks

1. **Lyrics false positives**
   - Aggressive title variants can make live, studio, cover, remix, and remaster versions appear equivalent.
   - Album metadata is not included in final lyrics scoring.
   - Missing durations are treated as acceptable.
   - NetEase returns the first accepted candidate instead of retaining alternatives.
   - Low-confidence matches are saved without requiring user confirmation.

2. **Audio quality limitations**
   - FLAC/WAV output does not improve the quality of a lossy YouTube source.
   - MP3 and Opus conversion can introduce additional lossy encoding.
   - The application does not currently expose a source-preserving output mode.
   - Source and output codec/bitrate information is not reported.

3. **Maintainability**
   - `lyrics.py` is over 1,000 lines and will become harder to extend as more providers and confidence logic are added.
   - The lyrics user agent still reports version `0.1.0`.
   - A pipeline comment still refers specifically to MP3 metadata.
   - Whale and Safari paths exist in browser detection code but are not active detection targets or CLI choices.

4. **Platform considerations**
   - Playlist extraction does not currently use browser cookies; only downloading does.
   - `forceipv4` is hardcoded.
   - A future macOS desktop app must not rely solely on `PATH` to locate FFmpeg or Deno when launched from Finder.

## Planned Direction

### Guiding Decisions

- Build a GUI-independent application/service layer before adding the desktop interface.
- Implement lyrics-only search/download as a CLI feature first.
- Improve lyrics matching with explainable confidence and explicit handling of ambiguous results.
- Add a Best/Source audio mode that preserves the selected source stream without unnecessary transcoding.
- Target a native PySide6 desktop application for Fedora/Linux and macOS first.
- Keep Windows support as a later consideration.

### Phase 0: Baseline Cleanup

- [ ] Make all pipeline tests independent of the local browser environment.
- [ ] Update the README test-status section.
- [ ] Correct outdated version strings and comments.
- [ ] Confirm the existing music-download CLI remains backward compatible.

### Phase 1: Lyrics-Only Foundation

- [ ] Add a `LyricsQuery` model with title, artist, album, duration, and optional source URL.
- [ ] Add a shared lyrics service used by both CLI and future GUI code.
- [ ] Return structured candidates containing provider metadata, scores, and rejection reasons.
- [ ] Ensure lyrics-only operation never downloads audio or requires browser cookies.
- [ ] Add CLI commands:

  ```bash
  ytmusic-dl lyrics search "Song Title" --artist "Artist Name"
  ytmusic-dl lyrics download "Song Title" --artist "Artist Name" --best
  ytmusic-dl lyrics download "https://music.youtube.com/watch?v=VIDEO_ID" --best
  ```

- [ ] Support `--best`, `--select N`, `--min-confidence`, output directories, and overwrite protection.
- [ ] Default to synchronized lyrics when available, with plain-text output as fallback.
- [ ] Add unit and CLI tests for lyrics-only behavior.

### Phase 2: Lyrics Accuracy

- [ ] Create a regression corpus for same-title, same-artist, version, cover, bilingual, missing-duration, and instrumental cases.
- [ ] Use aggressive title normalization for search only, not as sole proof of a correct match.
- [ ] Include album, artist, title, duration, and version compatibility in scoring.
- [ ] Penalize studio/live/acoustic/remix/cover/remaster mismatches.
- [ ] Keep multiple NetEase candidates instead of returning the first accepted result.
- [ ] Deduplicate and compare candidates across providers.
- [ ] Add confidence thresholds:
  - High confidence: automatic selection is allowed.
  - Medium confidence: require explicit confirmation.
  - Low confidence: require manual candidate selection.
- [ ] Expose match explanations in CLI output and the future GUI.
- [ ] Evaluate optional Chromaprint/AcoustID + MusicBrainz recording identification for downloaded audio.

### Phase 3: Audio Quality

- [ ] Add a Best/Source output mode.
- [ ] Prefer stream-copying or remuxing over re-encoding when possible.
- [ ] Add AAC/M4A output support.
- [ ] Add M4A metadata and cover-art support using Mutagen's MP4 implementation.
- [ ] Refactor downloading to use the actual final file path returned by `yt-dlp`.
- [ ] Update skip-existing logic for dynamically determined extensions.
- [ ] Make conversion quality explicit for MP3, Opus, and AAC modes.
- [ ] Report source codec/bitrate, output codec/bitrate, and copy/remux/transcode status.
- [ ] Warn when FLAC/WAV is selected from a lossy source.
- [ ] Verify real downloads with `yt-dlp -F` and `ffprobe`.

### Phase 4: Native Desktop Application

- [ ] Verify PySide6 compatibility with Python 3.14 on Fedora and macOS.
- [ ] Create a PySide6 main window with:
  - Music Download tab
  - Lyrics Only tab
  - Settings tab
- [ ] Run network and download work in background workers.
- [ ] Add progress, logging, cancellation, and completion signals.
- [ ] Show lyrics candidates with confidence, match reasons, and previews.
- [ ] Add an audio-quality selector and source/output quality report.
- [ ] Detect FFmpeg and Deno without relying exclusively on `PATH`.
- [ ] Test Fedora under Wayland and X11.
- [ ] Test macOS terminal and Finder launches.

### Phase 5: Packaging and Releases

Suggested release sequence:

- `v0.3.0`: lyrics-only CLI and improved matching confidence
- `v0.4.0`: Best/Source audio mode and M4A support
- `v0.5.0`: native desktop application

Packaging goals:

- Linux: AppImage first, optional RPM later
- macOS: `.app`/`.dmg`, with signing and notarization when public distribution is ready
- Updated README, screenshots, desktop installation instructions, and troubleshooting guidance

## Acceptance Criteria

### Lyrics

- Known same-title regression cases do not silently receive incorrect lyrics.
- Every selected result exposes confidence and match reasons.
- Ambiguous results require user selection.
- Lyrics-only commands never download audio.

### Audio

- Best/Source mode does not re-encode audio.
- M4A metadata and artwork are preserved.
- Source and output codec/bitrate information is visible.
- FLAC/WAV documentation clearly states that quality cannot exceed the source.

### Desktop Application

- The UI remains responsive during downloads and lyrics searches.
- Long-running jobs can be cancelled.
- Fedora and macOS smoke tests pass.
- FFmpeg and Deno discovery works from normal desktop launches.

## Open Decisions

- Confirm PySide6 versus PyQt6 after the Python 3.14 compatibility spike.
- Decide whether Best/Source should become the default output mode or remain opt-in.
- Decide whether plain-only lyrics should default to `.lrc` or `.txt`.
- Decide whether recording identification via AcoustID/MusicBrainz is worth the added dependencies and network calls.
- Decide the public packaging and distribution approach for Linux and macOS.

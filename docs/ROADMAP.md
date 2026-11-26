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
- `lyrics/`: lyrics package
  - `normalize.py`: text normalization and title variants
  - `scoring.py`: title, artist, and duration scoring and confidence
  - `providers/`: LRCLIB and NetEase provider integrations
  - `service.py`: search, candidate scoring, selection, and writing
- `cli_lyrics.py`: lyrics-only search and download commands
- `metadata.py`: format-specific metadata embedding
- `thumbnail.py`: thumbnail downloading and artwork embedding
- `models.py`: shared dataclasses
- `utils.py`: filename and path helpers

### Verification Snapshot

At the time of this review:

- 132 tests were collected.
- 132 tests passed.
- No tests depend on a local browser profile or usable YouTube cookies.
- The README test status matches the suite.
- CI runs the suite on every push to `main` and on pull requests.

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

3. **Platform considerations**
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

- [x] Make all pipeline tests independent of the local browser environment.
- [x] Update the README test-status section.
- [x] Correct outdated version strings and comments.
- [x] Confirm the existing music-download CLI remains backward compatible.
- [x] Add a CI workflow that runs the test suite.
- [x] Promote Naver Whale to an active browser and remove the unused Safari path.

### Phase 1: Lyrics-Only Foundation

- [x] Add a `LyricsQuery` model with title, artist, album, duration, and optional source URL.
- [x] Add a shared lyrics service used by both CLI and future GUI code.
- [x] Return structured candidates containing provider metadata, scores, and rejection reasons.
- [x] Ensure lyrics-only operation never downloads audio or requires browser cookies.
- [x] Add CLI commands:

  ```bash
  ytmusic-dl lyrics search "Song Title" --artist "Artist Name"
  ytmusic-dl lyrics download "Song Title" --artist "Artist Name" --best
  ytmusic-dl lyrics download "https://music.youtube.com/watch?v=VIDEO_ID" --best
  ```

- [x] Support `--best`, `--select N`, `--min-confidence`, output directories, and overwrite protection.
- [x] Default to synchronized lyrics when available, with plain-text output as fallback.
- [x] Add unit and CLI tests for lyrics-only behavior.

### Phase 2: Lyrics Accuracy

- [ ] Create a regression corpus for same-title, same-artist, version, cover, bilingual, missing-duration, and instrumental cases.
  - Initial corpus: `tests/test_lyrics_regression.py`, built from the real responses below. It grows with each scoring fix.
  - Observed in real runs (2026-11-26):
    - YouTube titles containing `Official Video` or `4K Remaster` used to pollute NetEase search terms. (Fixed: search terms are cleaned and capped at six.)
    - Those same tokens still lower title similarity during scoring, even when the provider's title is clean.
    - NetEase filters rejected candidates internally, so the CLI cannot show why they lost. (Fixed: NetEase now returns every candidate; the service scores and explains them.)
    - LRCLIB sometimes repeats the video title in the album field, so album comparison cannot be a strict requirement.
    - A correct match with no known duration still reaches `medium` confidence.
    - NetEase artist fields list many aliases, which depressed artist similarity even when the canonical name matched (`Rick Astley` scored 0.20). (Fixed: similarity now compares against the shorter artist list, so an alias match scores 1.0.)
    - NetEase can return the same recording under different album names, so cross-candidate deduplication is needed. (Fixed for exact duplicates: same provider, title, artist, and duration collapse, preferring lyrics content and a matching album.)
- [x] Use aggressive title normalization for search only, not as sole proof of a correct match.
- [ ] Include album, artist, title, duration, and version compatibility in scoring.
- [x] Penalize studio/live/acoustic/remix/cover/remaster mismatches.
- [x] Keep multiple NetEase candidates instead of returning the first accepted result.
- [ ] Deduplicate and compare candidates across providers.
  - Same-provider duplicates with identical title, artist, and duration now collapse, and original/remaster copies are treated as one recording. Live, acoustic, and instrumental editions stay separate, and cross-provider copies are kept.
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

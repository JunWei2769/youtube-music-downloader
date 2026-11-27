"""Render documentation screenshots with the offscreen Qt platform."""

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from ytmusic_dl.gui.download_tab import DownloadTab
from ytmusic_dl.gui.format_audit import FormatAuditDialog
from ytmusic_dl.gui.lyrics_tab import LyricsTab
from ytmusic_dl.gui.window import MainWindow
from ytmusic_dl.models import (
    AudioFormatInfo,
    AudioFormatReport,
    LyricsCandidate,
    LyricsQuery,
    LyricsResult,
    Track,
)

OUTPUT = Path("docs/screenshots")

def make_track(
    index: int,
    title: str,
    artist: str,
    album: str,
    duration: float,
    video_id: str,
) -> Track:
    return Track(
        playlist_index=index,
        title=title,
        artist=artist,
        album=album,
        duration=duration,
        video_id=video_id,
        webpage_url=(
            f"https://music.youtube.com/watch?v={video_id}"
        ),
        playlist_name="Mandopop Essentials",
    )

def make_candidate(
    title: str,
    artist: str,
    *,
    confidence: str = "high",
    provider: str = "lrclib",
    duration: float = 210,
) -> LyricsCandidate:
    return LyricsCandidate(
        result=LyricsResult(
            provider=provider,
            provider_id="screenshot",
            track_name=title,
            artist_name=artist,
            album_name="Screenshot Album",
            duration=duration,
            instrumental=False,
            synced_lyrics=(
                "[00:12.00] 想说却还没说的 还很多\n"
                "[00:17.00] 攒着是因为想写成歌\n"
            ),
            plain_lyrics="想说却还没说的 还很多\n攒着是因为想写成歌\n",
        ),
        score=1.12,
        confidence=confidence,
        match_reasons=[
            "title matches",
            "artist matches",
            "duration close",
        ],
    )

def render(
    widget,
    path: Path,
    size: tuple[int, int],
) -> None:
    widget.resize(*size)
    widget.show()
    QApplication.processEvents()
    widget.grab().save(str(path))
    widget.hide()

def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)

    temporary = tempfile.TemporaryDirectory(
        prefix="ytmusic_screens_"
    )
    settings = QSettings(
        str(Path(temporary.name) / "settings.ini"),
        QSettings.Format.IniFormat,
    )

    app = QApplication.instance() or QApplication(sys.argv)

    window = MainWindow(settings=settings)
    window.resize(1180, 820)

    download_tab = window.tabs.widget(0)

    assert isinstance(download_tab, DownloadTab)

    tracks = [
        make_track(
            1,
            "山丘",
            "李宗盛",
            "山丘",
            331,
            "screenshot1",
        ),
        make_track(
            2,
            "年少有为",
            "李荣浩",
            "耳朵",
            289,
            "screenshot2",
        ),
        make_track(
            3,
            "起风了",
            "买辣椒也用券",
            None,
            331,
            "screenshot3",
        ),
        make_track(
            4,
            "刻在我心底的名字",
            "卢广仲",
            "刻在我心底的名字",
            320,
            "screenshot4",
        ),
    ]

    download_tab.url_input.setText(
        "https://music.youtube.com/playlist?list=PLscreenshot"
    )
    download_tab.output_input.setText("~/Music/downloads")
    download_tab.track_table.set_tracks(tracks)

    download_tab.track_table.update_lyrics(
        tracks[0],
        make_candidate("山丘", "李宗盛"),
        "",
    )
    download_tab.track_table.update_lyrics(
        tracks[1],
        make_candidate("年少有为", "李荣浩"),
        "",
    )
    download_tab.track_table.update_lyrics(
        tracks[2],
        make_candidate(
            "起风了",
            "买辣椒也用券",
            confidence="medium",
        ),
        "",
    )
    download_tab.track_table.update_lyrics(
        tracks[3],
        None,
        "Rejected: artist does not match; "
        "provider artist: 卢广仲 (cover)",
    )

    download_tab.track_table.checkboxes[id(tracks[3])].setChecked(
        False
    )
    download_tab.selection_label.setText("3 of 4 selected")

    window.tabs.setCurrentIndex(0)

    render(
        window,
        OUTPUT / "music-download.png",
        (1180, 820),
    )

    lyrics_tab = window.tabs.widget(1)

    assert isinstance(lyrics_tab, LyricsTab)

    lyrics_tab.query_input.setText(
        "https://music.youtube.com/watch?v=screenshot1"
    )
    lyrics_tab.artist_input.setText("李宗盛")
    lyrics_tab._apply_results(
        LyricsQuery(title="山丘", artist="李宗盛"),
        [
            make_candidate("山丘", "李宗盛"),
            make_candidate(
                "山丘 (Live)",
                "李宗盛",
                confidence="medium",
                duration=410,
            ),
            make_candidate(
                "山丘",
                "李宗盛",
                confidence="low",
                provider="netease",
                duration=330,
            ),
        ],
    )

    window.tabs.setCurrentIndex(1)

    render(
        window,
        OUTPUT / "lyrics-only.png",
        (1180, 820),
    )

    report = AudioFormatReport(
        title="山丘 — 李宗盛",
        formats=[
            AudioFormatInfo(
                format_id="251",
                extension="webm",
                codec="opus",
                bitrate=128.9,
                sample_rate=48000,
                note="medium",
                protocol="https",
            ),
            AudioFormatInfo(
                format_id="140",
                extension="m4a",
                codec="mp4a.40.2",
                bitrate=129.5,
                sample_rate=44100,
                note="medium",
                protocol="https",
            ),
            AudioFormatInfo(
                format_id="250",
                extension="webm",
                codec="opus",
                bitrate=61.1,
                sample_rate=48000,
                note="low",
                protocol="https",
            ),
            AudioFormatInfo(
                format_id="249",
                extension="webm",
                codec="opus",
                bitrate=46.2,
                sample_rate=48000,
                note="low",
                protocol="https",
            ),
        ],
        selected_format_id="251",
    )

    dialog = FormatAuditDialog(report)

    render(
        dialog,
        OUTPUT / "format-audit.png",
        (820, 420),
    )

    window.close()
    dialog.close()
    temporary.cleanup()

    print(f"Screenshots written to {OUTPUT}")

    return 0

if __name__ == "__main__":
    raise SystemExit(main())

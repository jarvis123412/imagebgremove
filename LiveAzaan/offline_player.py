"""Offline azaan playback for no-network scenarios."""

from __future__ import annotations

from pathlib import Path
from typing import Dict

from kivy.core.audio import SoundLoader


class OfflineAzaanPlayer:
    def __init__(self, assets_dir: str = "assets"):
        base = Path(assets_dir)
        self.tracks: Dict[str, Path] = {
            "fajr": base / "fajr.mp3",
            "zuhr": base / "zuhr.mp3",
            "asr": base / "asr.mp3",
            "maghrib": base / "maghrib.mp3",
            "isha": base / "isha.mp3",
        }
        self.current_sound = None

    def play(self, prayer_name: str) -> None:
        path = self.tracks.get(prayer_name.lower())
        if not path or not path.exists():
            raise FileNotFoundError(f"Offline track not found for prayer: {prayer_name}")
        self.stop()
        self.current_sound = SoundLoader.load(str(path))
        if self.current_sound:
            self.current_sound.play()

    def stop(self) -> None:
        if self.current_sound:
            self.current_sound.stop()
            self.current_sound = None

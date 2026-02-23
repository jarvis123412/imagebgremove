"""Masjid priority management for listeners."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass(order=True)
class MasjidPriority:
    priority: int
    masjid_id: str
    enabled: bool = True


class PriorityManager:
    def __init__(self):
        self.priority_list: List[MasjidPriority] = []

    def set_priority(self, masjid_id: str, priority: int, enabled: bool = True) -> None:
        self.priority_list = [p for p in self.priority_list if p.masjid_id != masjid_id]
        self.priority_list.append(MasjidPriority(priority=priority, masjid_id=masjid_id, enabled=enabled))
        self.priority_list.sort()

    def set_enabled(self, masjid_id: str, enabled: bool) -> None:
        for item in self.priority_list:
            if item.masjid_id == masjid_id:
                item.enabled = enabled
                break

    def highest_priority_live(self, live_masjid_ids: List[str]) -> Optional[str]:
        for item in sorted(self.priority_list):
            if item.enabled and item.masjid_id in live_masjid_ids:
                return item.masjid_id
        return None

    def as_dicts(self) -> List[dict]:
        return [
            {"masjid_id": p.masjid_id, "priority": p.priority, "enabled": p.enabled}
            for p in sorted(self.priority_list)
        ]

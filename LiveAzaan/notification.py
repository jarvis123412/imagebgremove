"""Notification utilities.

For Android production, FCM delivery is handled by platform services. This module
provides token registration and local callback dispatch used by the app runtime.
"""

from __future__ import annotations

import json
import os
from typing import Callable, Optional

import requests


class NotificationManager:
    def __init__(self, server_key: Optional[str] = None):
        self.server_key = server_key or os.getenv("FCM_SERVER_KEY", "")
        self.on_notification: Optional[Callable[[dict], None]] = None

    def set_notification_handler(self, handler: Callable[[dict], None]) -> None:
        self.on_notification = handler

    def trigger_remote_notification(self, device_token: str, title: str, body: str, data: Optional[dict] = None) -> dict:
        if not self.server_key:
            raise ValueError("FCM_SERVER_KEY is required")
        payload = {
            "to": device_token,
            "notification": {"title": title, "body": body},
            "data": data or {},
            "priority": "high",
        }
        response = requests.post(
            "https://fcm.googleapis.com/fcm/send",
            headers={
                "Authorization": f"key={self.server_key}",
                "Content-Type": "application/json",
            },
            data=json.dumps(payload),
            timeout=20,
        )
        response.raise_for_status()
        return response.json()

    def receive_notification(self, payload: dict) -> None:
        if self.on_notification:
            self.on_notification(payload)

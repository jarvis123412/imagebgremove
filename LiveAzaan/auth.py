"""Firebase Authentication manager for Live Azaan."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import os
from typing import Optional

import requests


class AuthError(Exception):
    """Raised for authentication failures."""


@dataclass
class AuthSession:
    user_id: str
    email: str
    id_token: str
    refresh_token: str
    expires_at: datetime

    @property
    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) >= self.expires_at


class AuthManager:
    def __init__(self, firebase_api_key: Optional[str] = None, timeout: int = 20):
        self.api_key = firebase_api_key or os.getenv("FIREBASE_API_KEY", "")
        self.timeout = timeout
        self.session: Optional[AuthSession] = None
        if not self.api_key:
            raise AuthError("FIREBASE_API_KEY is required")

    def register(self, email: str, password: str) -> AuthSession:
        return self._authenticate("accounts:signUp", email, password)

    def login(self, email: str, password: str) -> AuthSession:
        return self._authenticate("accounts:signInWithPassword", email, password)

    def logout(self) -> None:
        self.session = None

    def require_token(self) -> str:
        if not self.session:
            raise AuthError("No active session")
        if self.session.is_expired:
            self._refresh_token()
        return self.session.id_token

    def _authenticate(self, endpoint: str, email: str, password: str) -> AuthSession:
        url = f"https://identitytoolkit.googleapis.com/v1/{endpoint}?key={self.api_key}"
        payload = {"email": email, "password": password, "returnSecureToken": True}
        response = requests.post(url, json=payload, timeout=self.timeout)
        if not response.ok:
            raise AuthError(self._extract_error(response))
        data = response.json()
        self.session = AuthSession(
            user_id=data["localId"],
            email=data["email"],
            id_token=data["idToken"],
            refresh_token=data["refreshToken"],
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=int(data.get("expiresIn", "3600"))),
        )
        return self.session

    def _refresh_token(self) -> None:
        if not self.session:
            raise AuthError("No active session")

        url = f"https://securetoken.googleapis.com/v1/token?key={self.api_key}"
        payload = {"grant_type": "refresh_token", "refresh_token": self.session.refresh_token}
        response = requests.post(url, data=payload, timeout=self.timeout)
        if not response.ok:
            raise AuthError(self._extract_error(response))

        data = response.json()
        self.session.id_token = data["id_token"]
        self.session.refresh_token = data.get("refresh_token", self.session.refresh_token)
        self.session.expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(data.get("expires_in", "3600")))

    @staticmethod
    def _extract_error(response: requests.Response) -> str:
        body = response.text
        if "application/json" in response.headers.get("content-type", ""):
            body = response.json().get("error", {}).get("message", body)
        return body

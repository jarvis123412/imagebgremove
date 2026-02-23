"""Masjid and user profile management using Firestore REST APIs."""

from __future__ import annotations

from datetime import datetime, timezone
import os
from typing import Any, Dict, List

import requests


class MasjidError(Exception):
    """Raised for masjid management failures."""


class MasjidManager:
    def __init__(self, project_id: str | None = None, timeout: int = 20):
        self.project_id = project_id or os.getenv("FIREBASE_PROJECT_ID", "")
        self.timeout = timeout
        if not self.project_id:
            raise MasjidError("FIREBASE_PROJECT_ID is required")

    @property
    def base_url(self) -> str:
        return f"https://firestore.googleapis.com/v1/projects/{self.project_id}/databases/(default)/documents"

    def create_masjid(self, id_token: str, masjid_id: str, masjid_name: str, maulvi_id: str) -> Dict[str, Any]:
        payload = {
            "fields": {
                "masjid_id": {"stringValue": masjid_id},
                "masjid_name": {"stringValue": masjid_name},
                "maulvi_id": {"stringValue": maulvi_id},
                "is_live": {"booleanValue": False},
            }
        }
        url = f"{self.base_url}/masjid?documentId={masjid_id}"
        response = requests.post(url, json=payload, headers=self._headers(id_token), timeout=self.timeout)
        if not response.ok:
            raise MasjidError(response.text)
        return self._decode_document(response.json())

    def list_masjids(self, id_token: str) -> List[Dict[str, Any]]:
        response = requests.get(f"{self.base_url}/masjid", headers=self._headers(id_token), timeout=self.timeout)
        if not response.ok:
            raise MasjidError(response.text)
        return [self._decode_document(d) for d in response.json().get("documents", [])]

    def join_masjid(self, id_token: str, user_id: str, masjid_id: str) -> Dict[str, Any]:
        user = self.get_user(id_token, user_id)
        joined = set(user.get("joined_masjid", []))
        joined.add(masjid_id)

        fields = {
            "user_id": {"stringValue": user_id},
            "email": {"stringValue": user.get("email", "")},
            "joined_masjid": {"arrayValue": {"values": [{"stringValue": i} for i in sorted(joined)]}},
            "priority_list": {"arrayValue": {"values": user.get("_priority_raw", [])}},
        }
        url = f"{self.base_url}/users/{user_id}"
        response = requests.patch(url, params={"updateMask.fieldPaths": ["joined_masjid", "email", "user_id", "priority_list"]}, json={"fields": fields}, headers=self._headers(id_token), timeout=self.timeout)
        if not response.ok:
            raise MasjidError(response.text)
        return self._decode_document(response.json())

    def update_user_priorities(self, id_token: str, user_id: str, priority_items: List[dict]) -> Dict[str, Any]:
        values = []
        for item in priority_items:
            values.append(
                {
                    "mapValue": {
                        "fields": {
                            "masjid_id": {"stringValue": item["masjid_id"]},
                            "priority": {"integerValue": int(item["priority"])},
                            "enabled": {"booleanValue": bool(item.get("enabled", True))},
                        }
                    }
                }
            )

        url = f"{self.base_url}/users/{user_id}"
        payload = {"fields": {"priority_list": {"arrayValue": {"values": values}}}}
        response = requests.patch(url, params={"updateMask.fieldPaths": ["priority_list"]}, json=payload, headers=self._headers(id_token), timeout=self.timeout)
        if not response.ok:
            raise MasjidError(response.text)
        return self._decode_document(response.json())

    def set_masjid_live(self, id_token: str, masjid_id: str, is_live: bool) -> Dict[str, Any]:
        # sync in masjid collection
        m_url = f"{self.base_url}/masjid/{masjid_id}"
        m_payload = {"fields": {"is_live": {"booleanValue": is_live}}}
        m_resp = requests.patch(m_url, params={"updateMask.fieldPaths": ["is_live"]}, json=m_payload, headers=self._headers(id_token), timeout=self.timeout)
        if not m_resp.ok:
            raise MasjidError(m_resp.text)

        # write stream status collection
        ts = datetime.now(timezone.utc).isoformat()
        s_url = f"{self.base_url}/stream/{masjid_id}"
        s_payload = {
            "fields": {
                "masjid_id": {"stringValue": masjid_id},
                "is_live": {"booleanValue": is_live},
                "timestamp": {"timestampValue": ts},
            }
        }
        s_resp = requests.patch(s_url, json=s_payload, headers=self._headers(id_token), timeout=self.timeout)
        if not s_resp.ok:
            raise MasjidError(s_resp.text)

        return self._decode_document(m_resp.json())

    def get_user(self, id_token: str, user_id: str) -> Dict[str, Any]:
        response = requests.get(f"{self.base_url}/users/{user_id}", headers=self._headers(id_token), timeout=self.timeout)
        if response.status_code == 404:
            return {"user_id": user_id, "email": "", "joined_masjid": [], "priority_list": [], "_priority_raw": []}
        if not response.ok:
            raise MasjidError(response.text)
        decoded = self._decode_document(response.json())
        decoded["_priority_raw"] = self._to_priority_raw(decoded.get("priority_list", []))
        return decoded

    @staticmethod
    def _headers(id_token: str) -> Dict[str, str]:
        return {"Authorization": f"Bearer {id_token}", "Content-Type": "application/json"}

    def _decode_document(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        fields = doc.get("fields", {})
        out: Dict[str, Any] = {}
        for key, value in fields.items():
            out[key] = self._decode_value(value)
        return out

    def _decode_value(self, value: Dict[str, Any]) -> Any:
        if "stringValue" in value:
            return value["stringValue"]
        if "booleanValue" in value:
            return value["booleanValue"]
        if "integerValue" in value:
            return int(value["integerValue"])
        if "timestampValue" in value:
            return value["timestampValue"]
        if "arrayValue" in value:
            return [self._decode_value(v) for v in value["arrayValue"].get("values", [])]
        if "mapValue" in value:
            fields = value["mapValue"].get("fields", {})
            return {k: self._decode_value(v) for k, v in fields.items()}
        return None

    @staticmethod
    def _to_priority_raw(items: List[dict]) -> List[dict]:
        out = []
        for item in items:
            out.append(
                {
                    "mapValue": {
                        "fields": {
                            "masjid_id": {"stringValue": item.get("masjid_id", "")},
                            "priority": {"integerValue": int(item.get("priority", 0))},
                            "enabled": {"booleanValue": bool(item.get("enabled", True))},
                        }
                    }
                }
            )
        return out

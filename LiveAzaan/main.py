"""Main entrypoint for the Live Azaan Kivy application."""

from __future__ import annotations

import os
from typing import Optional

from kivy.app import App
from kivy.lang import Builder
from kivy.properties import StringProperty
from kivy.uix.screenmanager import Screen, ScreenManager

from auth import AuthError, AuthManager
from masjid import MasjidError, MasjidManager
from notification import NotificationManager
from offline_player import OfflineAzaanPlayer
from priority import PriorityManager
from stream_receiver import LiveStreamReceiver
from stream_sender import LiveStreamSender


class LoginScreen(Screen):
    status_text = StringProperty("")


class RegisterScreen(Screen):
    status_text = StringProperty("")


class DashboardScreen(Screen):
    user_email = StringProperty("Not logged in")
    mode_text = StringProperty("Listener")


class MasjidListScreen(Screen):
    status_text = StringProperty("")
    masjid_data = StringProperty("No masjids loaded")


class LiveAzaanScreen(Screen):
    stream_status = StringProperty("Idle")


class SettingsScreen(Screen):
    status_text = StringProperty("")


class LiveAzaanApp(App):
    def build(self):
        self.title = "Live Azaan"
        Builder.load_file("ui.kv")

        self.auth: Optional[AuthManager] = None
        self.masjid: Optional[MasjidManager] = None
        self._init_services()

        self.notifications = NotificationManager(os.getenv("FCM_SERVER_KEY"))
        self.priority = PriorityManager()
        self.offline_player = OfflineAzaanPlayer("assets")
        self.sender: Optional[LiveStreamSender] = None
        self.receiver: Optional[LiveStreamReceiver] = None
        self.user_role = "listener"
        self.notifications.set_notification_handler(self._on_notification)

        sm = ScreenManager()
        sm.add_widget(LoginScreen(name="login"))
        sm.add_widget(RegisterScreen(name="register"))
        sm.add_widget(DashboardScreen(name="dashboard"))
        sm.add_widget(MasjidListScreen(name="masjid_list"))
        sm.add_widget(LiveAzaanScreen(name="live_azaan"))
        sm.add_widget(SettingsScreen(name="settings"))
        return sm

    def _init_services(self) -> None:
        try:
            self.auth = AuthManager(os.getenv("FIREBASE_API_KEY"))
            self.masjid = MasjidManager(os.getenv("FIREBASE_PROJECT_ID"))
        except (AuthError, MasjidError) as exc:
            # allow app to open UI while surfacing configuration problems
            self.auth = None
            self.masjid = None
            self._set_status_all(f"Configuration error: {exc}")

    def _set_status_all(self, message: str) -> None:
        if not self.root:
            return
        self.root.get_screen("login").status_text = message
        self.root.get_screen("register").status_text = message
        self.root.get_screen("masjid_list").status_text = message
        self.root.get_screen("settings").status_text = message

    def do_login(self, email: str, password: str) -> None:
        if not self.auth:
            self.root.get_screen("login").status_text = "Auth service is not configured"
            return

        try:
            session = self.auth.login(email.strip(), password)
            dashboard = self.root.get_screen("dashboard")
            dashboard.user_email = session.email
            self.root.get_screen("login").status_text = ""
            self.root.current = "dashboard"
        except AuthError as exc:
            self.root.get_screen("login").status_text = str(exc)

    def do_register(self, email: str, password: str) -> None:
        if not self.auth:
            self.root.get_screen("register").status_text = "Auth service is not configured"
            return
        try:
            self.auth.register(email.strip(), password)
            self.root.get_screen("register").status_text = "Registration successful"
            self.root.current = "login"
        except AuthError as exc:
            self.root.get_screen("register").status_text = str(exc)

    def set_role(self, role: str) -> None:
        self.user_role = role
        self.root.get_screen("dashboard").mode_text = role.capitalize()

    def create_masjid(self, masjid_id: str, masjid_name: str) -> None:
        if not (self.auth and self.masjid and self.auth.session):
            self.root.get_screen("masjid_list").status_text = "Please login first"
            return
        try:
            token = self.auth.require_token()
            self.masjid.create_masjid(token, masjid_id.strip(), masjid_name.strip(), self.auth.session.user_id)
            self.root.get_screen("masjid_list").status_text = "Masjid created"
        except (AuthError, MasjidError) as exc:
            self.root.get_screen("masjid_list").status_text = str(exc)

    def join_masjid(self, masjid_id: str) -> None:
        if not (self.auth and self.masjid and self.auth.session):
            self.root.get_screen("masjid_list").status_text = "Please login first"
            return
        try:
            token = self.auth.require_token()
            self.masjid.join_masjid(token, self.auth.session.user_id, masjid_id.strip())
            self.root.get_screen("masjid_list").status_text = f"Joined masjid {masjid_id}"
        except (AuthError, MasjidError) as exc:
            self.root.get_screen("masjid_list").status_text = str(exc)

    def load_masjids(self) -> None:
        if not (self.auth and self.masjid and self.auth.session):
            self.root.get_screen("masjid_list").status_text = "Please login first"
            return
        try:
            token = self.auth.require_token()
            masjids = self.masjid.list_masjids(token)
            names = [f"{m.get('masjid_id','?')} | {m.get('masjid_name','?')} | live={m.get('is_live', False)}" for m in masjids]
            self.root.get_screen("masjid_list").masjid_data = "\n".join(names) if names else "No masjids found"
            self.root.get_screen("masjid_list").status_text = "Masjid list refreshed"
        except (AuthError, MasjidError) as exc:
            self.root.get_screen("masjid_list").status_text = str(exc)

    def start_azaan(self, host: str, port: str, masjid_id: str) -> None:
        if self.user_role != "maulvi":
            self.root.get_screen("live_azaan").stream_status = "Switch role to Maulvi first"
            return

        try:
            self.sender = LiveStreamSender(host=host.strip(), port=int(port))
            self.sender.start()
            self.root.get_screen("live_azaan").stream_status = "Broadcasting live"
            self._update_masjid_live(masjid_id.strip(), True)
        except (ValueError, OSError) as exc:
            self.root.get_screen("live_azaan").stream_status = f"Start failed: {exc}"

    def stop_azaan(self, masjid_id: str) -> None:
        if self.sender:
            self.sender.stop()
        self.root.get_screen("live_azaan").stream_status = "Stopped"
        self._update_masjid_live(masjid_id.strip(), False)

    def listen_live(self, host: str, port: str) -> None:
        try:
            self.receiver = LiveStreamReceiver(host=host.strip(), port=int(port))
            self.receiver.start()
            self.root.get_screen("live_azaan").stream_status = "Listening"
        except (ValueError, OSError) as exc:
            self.root.get_screen("live_azaan").stream_status = f"Listen failed: {exc}"
            self.play_offline("fajr")

    def stop_listen(self) -> None:
        if self.receiver:
            self.receiver.stop()
        self.root.get_screen("live_azaan").stream_status = "Idle"

    def play_offline(self, prayer_name: str = "fajr") -> None:
        try:
            self.offline_player.play(prayer_name)
        except FileNotFoundError as exc:
            self.root.get_screen("live_azaan").stream_status = str(exc)

    def set_priority(self, masjid_id: str, priority: str) -> None:
        try:
            self.priority.set_priority(masjid_id=masjid_id.strip(), priority=int(priority), enabled=True)
            if self.auth and self.masjid and self.auth.session:
                token = self.auth.require_token()
                self.masjid.update_user_priorities(token, self.auth.session.user_id, self.priority.as_dicts())
            self.root.get_screen("settings").status_text = "Priority saved"
        except (ValueError, AuthError, MasjidError) as exc:
            self.root.get_screen("settings").status_text = f"Priority update failed: {exc}"

    def _update_masjid_live(self, masjid_id: str, is_live: bool) -> None:
        if not masjid_id:
            return
        if not (self.auth and self.masjid and self.auth.session):
            return
        try:
            token = self.auth.require_token()
            self.masjid.set_masjid_live(token, masjid_id, is_live)
        except (AuthError, MasjidError):
            pass

    def _on_notification(self, payload: dict) -> None:
        data = payload.get("data", {})
        if data.get("action") == "play_offline":
            self.play_offline(data.get("prayer", "fajr"))


if __name__ == "__main__":
    LiveAzaanApp().run()

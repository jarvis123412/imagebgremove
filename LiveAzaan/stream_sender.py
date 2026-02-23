"""Audio stream sender for the Maulvi broadcaster role."""

from __future__ import annotations

import socket
import ssl
import threading
from typing import Optional

import pyaudio

from noise_reduction import NoiseReducer


class LiveStreamSender:
    def __init__(
        self,
        host: str,
        port: int,
        ca_cert: Optional[str] = None,
        channels: int = 1,
        rate: int = 16000,
        chunk: int = 1024,
    ):
        self.host = host
        self.port = port
        self.channels = channels
        self.rate = rate
        self.chunk = chunk
        self.ca_cert = ca_cert
        self.reducer = NoiseReducer()
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_stream, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)

    def _ssl_context(self) -> ssl.SSLContext:
        context = ssl.create_default_context(cafile=self.ca_cert)
        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED
        return context

    def _run_stream(self) -> None:
        pa = pyaudio.PyAudio()
        mic = pa.open(
            format=pyaudio.paInt16,
            channels=self.channels,
            rate=self.rate,
            input=True,
            frames_per_buffer=self.chunk,
        )

        try:
            context = self._ssl_context()
            with socket.create_connection((self.host, self.port), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=self.host) as secure_sock:
                    while self._running:
                        data = mic.read(self.chunk, exception_on_overflow=False)
                        secure_sock.sendall(self.reducer.reduce_noise(data))
        finally:
            mic.stop_stream()
            mic.close()
            pa.terminate()

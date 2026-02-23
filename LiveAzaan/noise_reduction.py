"""Real-time audio noise reduction pipeline."""

from __future__ import annotations

import audioop
import importlib
import importlib.util


def _load_rnnoise():
    spec = importlib.util.find_spec("rnnoise")
    if spec is None:
        return None
    module = importlib.import_module("rnnoise")
    return module


_RNNOISE_MODULE = _load_rnnoise()


class NoiseReducer:
    def __init__(self, sample_width: int = 2, gate_threshold: int = 350):
        self.sample_width = sample_width
        self.gate_threshold = gate_threshold
        self._rn = _RNNOISE_MODULE.RNNoise() if _RNNOISE_MODULE else None

    def reduce_noise(self, audio_data: bytes) -> bytes:
        if not audio_data:
            return audio_data
        if self._rn:
            return self._reduce_rnnoise(audio_data)
        return self._reduce_noise_gate(audio_data)

    def _reduce_rnnoise(self, audio_data: bytes) -> bytes:
        frame_size = 480 * self.sample_width
        cleaned = bytearray()
        for i in range(0, len(audio_data), frame_size):
            chunk = audio_data[i : i + frame_size]
            if len(chunk) < frame_size:
                cleaned.extend(chunk)
                continue
            cleaned.extend(self._rn.process_frame(chunk))
        return bytes(cleaned)

    def _reduce_noise_gate(self, audio_data: bytes) -> bytes:
        rms = audioop.rms(audio_data, self.sample_width)
        if rms < self.gate_threshold:
            return b"\x00" * len(audio_data)
        return audio_data


def reduce_noise(audio_data: bytes) -> bytes:
    return NoiseReducer().reduce_noise(audio_data)

"""Speech to text with faster-whisper (runs fully offline on the Pi)."""
from __future__ import annotations

import logging

import numpy as np

from .config import CONFIG

log = logging.getLogger("ghost.stt")


class Transcriber:
    def __init__(self):
        from faster_whisper import WhisperModel
        log.info("loading whisper %s (%s)", CONFIG.whisper_model, CONFIG.whisper_compute)
        self.model = WhisperModel(CONFIG.whisper_model, device="cpu",
                                  compute_type=CONFIG.whisper_compute, cpu_threads=4)

    def transcribe(self, audio_f32: np.ndarray) -> str:
        segments, info = self.model.transcribe(
            audio_f32, language="en", beam_size=1, vad_filter=True,
            condition_on_previous_text=False,
            initial_prompt="Hey Ghost. Guardian. Destiny. Tower. Vanguard.")
        text = " ".join(s.text.strip() for s in segments).strip()
        log.info("heard: %r", text)
        return text

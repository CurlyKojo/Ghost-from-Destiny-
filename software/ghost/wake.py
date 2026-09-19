"""Wake word detection with openWakeWord.

Default wake phrase is "Hey Ghost" via a custom model at models/hey_ghost.onnx.  If that
file is missing we fall back to a bundled model ("hey_jarvis") so the Ghost still works
while you train the custom one - see docs/05-software-setup.md for the 20-minute recipe.
"""
from __future__ import annotations

import logging
import os

import numpy as np

from .config import CONFIG

log = logging.getLogger("ghost.wake")


class WakeWord:
    def __init__(self):
        from openwakeword.model import Model  # imported lazily; heavy
        import openwakeword
        try:
            openwakeword.utils.download_models()   # no-op once cached
        except Exception as e:  # offline is fine if the models are already there
            log.debug("model download skipped: %s", e)

        if os.path.exists(CONFIG.wake_model):
            self.model = Model(wakeword_models=[CONFIG.wake_model], inference_framework="onnx")
            self.name = os.path.splitext(os.path.basename(CONFIG.wake_model))[0]
            log.info("wake word model: %s", CONFIG.wake_model)
        else:
            self.model = Model(wakeword_models=[CONFIG.wake_fallback], inference_framework="onnx")
            self.name = CONFIG.wake_fallback
            log.warning("custom wake model not found at %s - using bundled '%s'",
                        CONFIG.wake_model, CONFIG.wake_fallback)
        self._cool_until = 0.0

    def detect(self, frame_int16: np.ndarray) -> bool:
        """Feed one 80 ms frame (1280 samples, int16 @ 16 kHz)."""
        scores = self.model.predict(frame_int16)
        score = max(v for k, v in scores.items() if self.name in k) if scores else 0.0
        return score >= CONFIG.wake_threshold

    def reset(self):
        self.model.reset()

"""All tunables in one place.  Everything can be overridden with environment variables
(or a .env file next to this package - see software/.env.example)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ENV_FILE = _HERE.parent / ".env"


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv(_ENV_FILE)


def _env(name: str, default):
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    if isinstance(default, bool):
        return raw.lower() in ("1", "true", "yes", "on")
    if isinstance(default, int):
        return int(raw)
    if isinstance(default, float):
        return float(raw)
    return raw


@dataclass
class Config:
    # --- identity ---------------------------------------------------------
    guardian_name: str = _env("GHOST_GUARDIAN_NAME", "Guardian")
    city: str = _env("GHOST_CITY", "")              # default city for weather
    timezone: str = _env("GHOST_TZ", "")            # e.g. America/Chicago; empty = system

    # --- brain (Claude) ----------------------------------------------------
    model: str = _env("GHOST_MODEL", "claude-opus-5")
    effort: str = _env("GHOST_EFFORT", "low")      # low keeps replies snappy
    max_tokens: int = _env("GHOST_MAX_TOKENS", 2048)
    history_turns: int = _env("GHOST_HISTORY_TURNS", 12)
    fallbacks: bool = _env("GHOST_FALLBACKS", True)  # server-side refusal fallback

    # --- audio -------------------------------------------------------------
    sample_rate: int = 16000
    input_device: str = _env("GHOST_INPUT_DEVICE", "")   # sounddevice name/index, "" = default
    output_device: str = _env("GHOST_OUTPUT_DEVICE", "")
    volume: float = _env("GHOST_VOLUME", 0.8)
    vad_threshold: float = _env("GHOST_VAD_THRESHOLD", 0.012)   # RMS, 0..1 scale
    vad_silence_s: float = _env("GHOST_VAD_SILENCE", 0.9)
    vad_max_s: float = _env("GHOST_VAD_MAX", 12.0)
    followup_window_s: float = _env("GHOST_FOLLOWUP", 6.0)

    # --- wake word ---------------------------------------------------------
    wake_model: str = _env("GHOST_WAKE_MODEL", str(_HERE.parent / "models" / "hey_ghost.onnx"))
    wake_fallback: str = _env("GHOST_WAKE_FALLBACK", "hey_jarvis")  # bundled openWakeWord model
    wake_threshold: float = _env("GHOST_WAKE_THRESHOLD", 0.5)

    # --- speech to text ----------------------------------------------------
    whisper_model: str = _env("GHOST_WHISPER_MODEL", "base.en")
    whisper_compute: str = _env("GHOST_WHISPER_COMPUTE", "int8")

    # --- text to speech ----------------------------------------------------
    tts_engine: str = _env("GHOST_TTS", "piper")   # piper | elevenlabs
    piper_model: str = _env("PIPER_MODEL", str(_HERE.parent / "models" / "en_US-ryan-medium.onnx"))
    piper_length_scale: float = _env("PIPER_LENGTH", 0.95)   # <1 = a little faster
    voice_pitch: float = _env("GHOST_VOICE_PITCH", 1.06)     # >1 = slightly higher
    voice_fx: bool = _env("GHOST_VOICE_FX", True)            # the "Ghost" filter chain
    elevenlabs_voice_id: str = _env("ELEVENLABS_VOICE_ID", "")

    # --- eye display (GC9A01, SPI0) ---------------------------------------
    display: str = _env("GHOST_DISPLAY", "auto")   # auto | gc9a01 | none | png
    display_dc: int = _env("GHOST_DISPLAY_DC", 25)
    display_rst: int = _env("GHOST_DISPLAY_RST", 27)
    display_cs: int = _env("GHOST_DISPLAY_CS", 8)
    display_bl: int = _env("GHOST_DISPLAY_BL", 24)
    display_fps: int = _env("GHOST_DISPLAY_FPS", 24)
    display_rotation: int = _env("GHOST_DISPLAY_ROTATION", 0)

    # --- LED ring ----------------------------------------------------------
    led_count: int = _env("GHOST_LED_COUNT", 16)
    led_pin: int = _env("GHOST_LED_PIN", 12)       # GPIO12 (PWM0) - keeps 18-21 free for I2S
    led_brightness: float = _env("GHOST_LED_BRIGHTNESS", 0.35)

    # --- servos (PCA9685 over I2C) ----------------------------------------
    servos: bool = _env("GHOST_SERVOS", True)
    servo_pan_ch: int = _env("GHOST_SERVO_PAN", 0)
    servo_tilt_ch: int = _env("GHOST_SERVO_TILT", 1)
    pan_center: float = _env("GHOST_PAN_CENTER", 90.0)
    tilt_center: float = _env("GHOST_TILT_CENTER", 90.0)
    pan_range: float = _env("GHOST_PAN_RANGE", 45.0)    # +- degrees from centre
    tilt_range: float = _env("GHOST_TILT_RANGE", 15.0)  # +- degrees; the arm clears +-15

    # --- integrations ------------------------------------------------------
    ha_url: str = _env("HA_URL", "")               # Home Assistant, e.g. http://homeassistant.local:8123
    ha_token: str = _env("HA_TOKEN", "")

    extra: dict = field(default_factory=dict)


CONFIG = Config()

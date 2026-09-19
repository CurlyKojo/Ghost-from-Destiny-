"""Tools the Ghost can call.  Each tool has a JSON schema (for Claude), a validator,
and an implementation.  Keep the schemas tight - with eager input streaming the client
owns validation."""
from __future__ import annotations

import datetime as dt
import json
import threading
import time
from typing import Any, Callable

import requests

from .config import CONFIG


# ---------------------------------------------------------------------------
# timers
# ---------------------------------------------------------------------------
class TimerBook:
    """Background timers that fire a callback with a label."""

    def __init__(self, on_fire: Callable[[str], None]):
        self._on_fire = on_fire
        self._timers: dict[str, tuple[threading.Timer, float]] = {}
        self._lock = threading.Lock()

    def add(self, seconds: float, label: str) -> str:
        label = label or "timer"
        with self._lock:
            if label in self._timers:
                self._timers[label][0].cancel()
            t = threading.Timer(seconds, self._fire, args=(label,))
            t.daemon = True
            self._timers[label] = (t, time.time() + seconds)
            t.start()
        return label

    def cancel(self, label: str) -> bool:
        with self._lock:
            if label in self._timers:
                self._timers.pop(label)[0].cancel()
                return True
            if label == "all" and self._timers:
                for t, _ in self._timers.values():
                    t.cancel()
                self._timers.clear()
                return True
        return False

    def remaining(self) -> dict[str, float]:
        now = time.time()
        with self._lock:
            return {k: max(0.0, end - now) for k, (_, end) in self._timers.items()}

    def _fire(self, label: str):
        with self._lock:
            self._timers.pop(label, None)
        self._on_fire(label)


# ---------------------------------------------------------------------------
# weather (Open-Meteo: free, no key)
# ---------------------------------------------------------------------------
_WMO = {
    0: "clear", 1: "mostly clear", 2: "partly cloudy", 3: "overcast", 45: "foggy", 48: "icy fog",
    51: "light drizzle", 53: "drizzle", 55: "heavy drizzle", 61: "light rain", 63: "rain",
    65: "heavy rain", 66: "freezing rain", 67: "heavy freezing rain", 71: "light snow", 73: "snow",
    75: "heavy snow", 77: "snow grains", 80: "rain showers", 81: "heavy showers", 82: "violent showers",
    85: "snow showers", 86: "heavy snow showers", 95: "thunderstorms", 96: "thunderstorms with hail",
    99: "severe thunderstorms with hail",
}


def weather(city: str) -> dict[str, Any]:
    city = city or CONFIG.city
    if not city:
        return {"error": "no city given and no default configured"}
    geo = requests.get("https://geocoding-api.open-meteo.com/v1/search",
                       params={"name": city, "count": 1}, timeout=8).json()
    if not geo.get("results"):
        return {"error": f"could not find a place called {city}"}
    g = geo["results"][0]
    wx = requests.get("https://api.open-meteo.com/v1/forecast", params={
        "latitude": g["latitude"], "longitude": g["longitude"],
        "current": "temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code",
        "temperature_unit": "fahrenheit", "wind_speed_unit": "mph", "forecast_days": 2, "timezone": "auto",
    }, timeout=8).json()
    cur, day = wx["current"], wx["daily"]
    return {
        "place": f"{g['name']}, {g.get('admin1', '')} {g.get('country_code', '')}".strip(),
        "now": {"temp_f": cur["temperature_2m"], "feels_like_f": cur["apparent_temperature"],
                "humidity": cur["relative_humidity_2m"], "wind_mph": cur["wind_speed_10m"],
                "sky": _WMO.get(cur["weather_code"], "unknown")},
        "today": {"high_f": day["temperature_2m_max"][0], "low_f": day["temperature_2m_min"][0],
                  "rain_chance_pct": day["precipitation_probability_max"][0],
                  "sky": _WMO.get(day["weather_code"][0], "unknown")},
        "tomorrow": {"high_f": day["temperature_2m_max"][1], "low_f": day["temperature_2m_min"][1],
                     "rain_chance_pct": day["precipitation_probability_max"][1],
                     "sky": _WMO.get(day["weather_code"][1], "unknown")},
    }


# ---------------------------------------------------------------------------
# home assistant (optional)
# ---------------------------------------------------------------------------
def home_assistant(domain: str, service: str, entity_id: str, data: dict | None = None) -> dict:
    if not CONFIG.ha_url or not CONFIG.ha_token:
        return {"error": "Home Assistant is not configured"}
    payload = {"entity_id": entity_id}
    if data:
        payload.update(data)
    r = requests.post(f"{CONFIG.ha_url.rstrip('/')}/api/services/{domain}/{service}",
                      headers={"Authorization": f"Bearer {CONFIG.ha_token}"},
                      json=payload, timeout=8)
    return {"status": r.status_code, "ok": r.ok}


# ---------------------------------------------------------------------------
# registry
# ---------------------------------------------------------------------------
class ToolBox:
    def __init__(self, timers: TimerBook, set_volume: Callable[[float], None]):
        self.timers = timers
        self.set_volume = set_volume

    # --- schemas sent to Claude -------------------------------------------
    def definitions(self) -> list[dict]:
        tools = [
            {
                "name": "get_time",
                "description": "Current local date and time. Use it for anything about 'now', today's date, or the day of the week.",
                "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
            },
            {
                "name": "set_timer",
                "description": "Start a countdown timer. Say it back in one natural sentence.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "seconds": {"type": "integer", "minimum": 1, "maximum": 86400},
                        "label": {"type": "string", "description": "short name, e.g. 'pasta'"},
                    },
                    "required": ["seconds"], "additionalProperties": False,
                },
            },
            {
                "name": "cancel_timer",
                "description": "Cancel a timer by label, or 'all'.",
                "input_schema": {"type": "object", "properties": {"label": {"type": "string"}},
                                 "required": ["label"], "additionalProperties": False},
            },
            {
                "name": "list_timers",
                "description": "Timers currently running and their remaining seconds.",
                "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
            },
            {
                "name": "get_weather",
                "description": "Current conditions and today/tomorrow forecast for a city. Omit city to use the Guardian's default.",
                "input_schema": {"type": "object", "properties": {"city": {"type": "string"}},
                                 "additionalProperties": False},
            },
            {
                "name": "set_volume",
                "description": "Set the Ghost's speaking volume, 0-100.",
                "input_schema": {"type": "object",
                                 "properties": {"percent": {"type": "integer", "minimum": 0, "maximum": 100}},
                                 "required": ["percent"], "additionalProperties": False},
            },
        ]
        if CONFIG.ha_url and CONFIG.ha_token:
            tools.append({
                "name": "home_assistant",
                "description": "Call a Home Assistant service, e.g. light.turn_on on light.desk_lamp, with optional data like brightness_pct or color_name.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "domain": {"type": "string"},
                        "service": {"type": "string"},
                        "entity_id": {"type": "string"},
                        "data": {"type": "object"},
                    },
                    "required": ["domain", "service", "entity_id"], "additionalProperties": False,
                },
            })
        for t in tools:
            t["strict"] = True                    # server validates the schema shape
            t["eager_input_streaming"] = True     # inputs stream as generated (we validate)
        return tools

    # --- client-side validation (eager streaming turns off server coercion) ----
    def validate(self, name: str, inp: Any) -> str | None:
        schema = next((t for t in self.definitions() if t["name"] == name), None)
        if schema is None:
            return f"unknown tool {name}"
        if not isinstance(inp, dict):
            return "input is not an object"
        props = schema["input_schema"]["properties"]
        for req in schema["input_schema"].get("required", []):
            if req not in inp:
                return f"missing required field {req}"
        for k, v in inp.items():
            if k not in props:
                return f"unexpected field {k}"
            want = props[k]["type"]
            ok = {"integer": lambda x: isinstance(x, int) and not isinstance(x, bool),
                  "string": lambda x: isinstance(x, str),
                  "object": lambda x: isinstance(x, dict)}[want](v)
            if not ok:
                return f"field {k} should be {want}"
            if want == "integer":
                if "minimum" in props[k] and v < props[k]["minimum"]:
                    return f"{k} below minimum"
                if "maximum" in props[k] and v > props[k]["maximum"]:
                    return f"{k} above maximum"
        return None

    # --- execution ----------------------------------------------------------
    def run(self, name: str, inp: dict) -> str:
        try:
            if name == "get_time":
                now = dt.datetime.now()
                if CONFIG.timezone:
                    from zoneinfo import ZoneInfo
                    now = dt.datetime.now(ZoneInfo(CONFIG.timezone))
                return json.dumps({"iso": now.isoformat(timespec="minutes"),
                                   "spoken": now.strftime("%A, %B %d, %I:%M %p").replace(" 0", " ")})
            if name == "set_timer":
                label = self.timers.add(int(inp["seconds"]), str(inp.get("label", "")).strip() or "timer")
                return json.dumps({"ok": True, "label": label, "seconds": int(inp["seconds"])})
            if name == "cancel_timer":
                return json.dumps({"cancelled": self.timers.cancel(str(inp["label"]))})
            if name == "list_timers":
                return json.dumps({"timers": {k: round(v) for k, v in self.timers.remaining().items()}})
            if name == "get_weather":
                return json.dumps(weather(str(inp.get("city", ""))))
            if name == "set_volume":
                self.set_volume(int(inp["percent"]) / 100.0)
                return json.dumps({"ok": True, "percent": int(inp["percent"])})
            if name == "home_assistant":
                return json.dumps(home_assistant(inp["domain"], inp["service"], inp["entity_id"], inp.get("data")))
            return json.dumps({"error": f"no such tool {name}"})
        except Exception as e:  # tool errors go back to the model, not up the stack
            return json.dumps({"error": f"{type(e).__name__}: {e}"})

"""Ghost main loop.

    IDLE --(wake word)--> LISTENING --(silence)--> THINKING --(first sentence)--> SPEAKING
      ^                                                                              |
      +---------------- (follow-up window if the Ghost asked a question) -------------+

Run on the Pi:      python -m ghost.main
Desktop / no mic:   python -m ghost.main --sim          (type instead of talk)
No API key yet:     python -m ghost.main --sim --mock   (canned brain, tests the body)
"""
from __future__ import annotations

import argparse
import logging
import queue
import random
import signal
import sys
import threading
import time

from .config import CONFIG
from .personality import TIMER_LINES, WAKE_ACKS
from .tools import TimerBook, ToolBox

log = logging.getLogger("ghost")


class MockBrain:
    """Stand-in for Brain when there is no API key: exercises the whole pipeline."""
    lines = [
        "[curious] Say that again, Guardian? [happy] Kidding. I heard you. This is a test of my voice and my eye.",
        "[thinking] Let me think about that. [excited] Got it! The answer is forty-two, obviously.",
        "[worried] I don't have a link to the Tower yet, so I'm running on canned lines. [smug] Still charming though.",
    ]
    def reply(self, text):
        from .brain import _StreamParser
        p = _StreamParser()
        yield from p.feed(random.choice(self.lines)); yield from p.flush()
    def forget(self): pass


class Ghost:
    def __init__(self, sim: bool, mock: bool):
        from .eye import Eye
        from .lights import Ring
        from .motion import Body
        from .tts import Voice
        from .audio import Speaker

        self.sim = sim
        self.eye = Eye(); self.eye.start()
        self.ring = Ring(); self.ring.start()
        self.body = Body(); self.body.start()
        self.speaker = Speaker()
        self.voice = None
        try:
            self.voice = Voice()
        except Exception as e:
            log.warning("no TTS voice (%s) - replies will be printed only", e)

        self.timers = TimerBook(on_fire=self._timer_fired)
        self.tools = ToolBox(self.timers, set_volume=lambda v: setattr(self.speaker, "volume", v))
        if mock:
            self.brain = MockBrain()
        else:
            from .brain import Brain
            self.brain = Brain(self.tools)

        self.mic = self.wake = self.stt = None
        if not sim:
            from .audio import Mic
            from .wake import WakeWord
            from .stt import Transcriber
            self.mic = Mic(); self.mic.start()
            self.wake = WakeWord()
            self.stt = Transcriber()

        self._speech_q: "queue.Queue[tuple[str, str] | None]" = queue.Queue()
        self._speaking = threading.Event()
        self._interrupt = threading.Event()
        self._stop = threading.Event()
        threading.Thread(target=self._speaker_loop, daemon=True, name="speaker").start()
        self.mood("neutral")

    # ------------------------------------------------------------------
    def mood(self, m: str):
        self.eye.set(mood=m); self.ring.set(mood=m); self.body.mood(m)

    def say(self, text: str, emotion: str = "neutral"):
        self._speech_q.put((text, emotion))

    def _speaker_loop(self):
        """Synthesize + play sentences in order; the eye follows the audio level."""
        while not self._stop.is_set():
            item = self._speech_q.get()
            if item is None:
                continue
            text, emotion = item
            print(f"  Ghost [{emotion}]: {text}")
            if self.voice is None:
                time.sleep(min(3.0, 0.05 * len(text))); continue
            self._speaking.set()
            try:
                audio, rate = self.voice.synth(text)
                self.eye.set(mood="speaking"); self.ring.set(mood="speaking")
                meter = threading.Thread(target=self._meter, daemon=True); meter.start()
                self.speaker.play(audio, rate)
            except Exception as e:
                log.error("speech failed: %s", e)
            finally:
                self._speaking.clear()
                if self._speech_q.empty():
                    self.eye.set(mood=emotion or "neutral"); self.ring.set(mood=emotion or "neutral")

    def _meter(self):
        while self.speaker.playing.is_set():
            lvl = min(1.0, self.speaker.level * 6.0)
            self.eye.set(level=lvl); self.ring.set(level=lvl)
            time.sleep(0.03)
        self.eye.set(level=0.0); self.ring.set(level=0.0)

    def _wait_for_speech_done(self):
        while not self._speech_q.empty() or self._speaking.is_set():
            time.sleep(0.05)

    def _timer_fired(self, label: str):
        self.speaker.chime("done")
        line = random.choice(TIMER_LINES).format(label=label)
        from .brain import _StreamParser
        p = _StreamParser()
        for c in list(p.feed(line)) + list(p.flush()):
            if c.kind == "emotion": self.mood(c.emotion)
            elif c.kind == "speech": self.say(c.text, c.emotion)

    # ------------------------------------------------------------------
    def handle(self, text: str) -> bool:
        """Send text to the brain and speak the reply.  Returns True if the reply asked a question."""
        if not text.strip():
            return False
        low = text.lower().strip(" .!?")
        if low in ("never mind", "nevermind", "cancel", "stop"):
            self.mood("neutral"); return False
        if low in ("forget everything", "new conversation", "reset"):
            self.brain.forget(); self.say("Fresh start, Guardian.", "happy"); return False
        self.mood("thinking")
        asked = False
        last_emotion = "neutral"
        for chunk in self.brain.reply(text):
            if chunk.kind == "emotion":
                last_emotion = chunk.emotion
                self.mood(chunk.emotion)
            elif chunk.kind == "speech":
                self.say(chunk.text, chunk.emotion or last_emotion)
                asked = chunk.text.rstrip().endswith("?")
            elif chunk.kind == "tool":
                self.eye.set(mood="thinking"); self.ring.set(mood="thinking")
        self._wait_for_speech_done()
        return asked

    # ------------------------------------------------------------------
    def run_sim(self):
        print("Ghost sim. Type to talk (Ctrl-C to quit). Eye frames -> /tmp/ghost_eye.png unless a display is attached.")
        while not self._stop.is_set():
            try:
                text = input("\nYou: ")
            except (EOFError, KeyboardInterrupt):
                break
            self.handle(text)
            self.mood("neutral")

    def run(self):
        log.info("Ghost online. Say 'Hey Ghost'.")
        followup_until = 0.0
        while not self._stop.is_set():
            try:
                frame = self.mic.read(timeout=1.0)
            except queue.Empty:
                continue
            if self._speaking.is_set():
                continue                                  # don't wake on our own voice
            woke = self.wake.detect(frame)
            in_followup = time.time() < followup_until
            if not woke and not in_followup:
                continue
            if woke:
                self.wake.reset()
                self.speaker.chime("wake")
                self.body.gesture("lean_in")
            # ---- listening
            self.mood("listening")
            audio = self.mic.record_utterance(on_level=lambda r: self.eye.set(listening_level=min(1.0, r * 25)))
            self.eye.set(listening_level=0.0)
            if audio is None:
                if woke:
                    ack = random.choice(WAKE_ACKS)
                    self.say(ack.split("] ", 1)[1], ack[1:ack.index("]")])
                    followup_until = time.time() + CONFIG.followup_window_s
                    self._wait_for_speech_done()
                else:
                    followup_until = 0.0
                    self.mood("neutral")
                continue
            # ---- thinking / speaking
            self.mood("thinking")
            text = self.stt.transcribe(audio)
            asked = self.handle(text)
            followup_until = time.time() + CONFIG.followup_window_s if asked else 0.0
            if not asked:
                self.mood("neutral")
            self.mic.drain()

    def shutdown(self):
        self._stop.set()
        for part in (self.eye, self.ring, self.body):
            part.stop()
        if self.mic:
            self.mic.stop()


def main(argv=None):
    ap = argparse.ArgumentParser(description="Destiny Ghost voice companion")
    ap.add_argument("--sim", action="store_true", help="type instead of using the microphone")
    ap.add_argument("--mock", action="store_true", help="canned brain (no API key needed)")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(name)s %(levelname)s %(message)s")
    g = Ghost(sim=args.sim, mock=args.mock)
    signal.signal(signal.SIGTERM, lambda *_: g.shutdown())
    try:
        if args.sim:
            g.run_sim()
        else:
            g.run()
    except KeyboardInterrupt:
        pass
    finally:
        g.shutdown()


if __name__ == "__main__":
    main()

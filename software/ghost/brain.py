"""The Ghost's brain: Claude with streaming, emotion tags and a tool loop.

Speech starts as soon as the first sentence has streamed in, so the Ghost feels alive
instead of pausing for the whole reply.  Emotion tags like [happy] are pulled out of the
stream and delivered to the body (eye, LEDs, servos) as events.
"""
from __future__ import annotations

import json
import logging
import random
import re
import time
from dataclasses import dataclass, field
from typing import Callable, Iterator

import anthropic

from .config import CONFIG, Config
from .personality import EMOTIONS, OFFLINE_LINES, REFUSAL_LINE, system_prompt
from .tools import ToolBox

log = logging.getLogger("ghost.brain")

_TAG = re.compile(r"\[(" + "|".join(EMOTIONS) + r")\]", re.IGNORECASE)
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+|(?<=[.!?])$")


@dataclass
class Chunk:
    """One unit of output: an emotion change or a sentence to speak."""
    kind: str                 # "emotion" | "speech" | "tool"
    text: str = ""
    emotion: str = ""


@dataclass
class Brain:
    tools: ToolBox
    cfg: Config = field(default_factory=lambda: CONFIG)
    client: anthropic.Anthropic = field(default_factory=anthropic.Anthropic)
    history: list[dict] = field(default_factory=list)

    def __post_init__(self):
        self._system = [{
            "type": "text",
            "text": system_prompt(self.cfg.guardian_name, self.cfg.city,
                                  bool(self.cfg.ha_url and self.cfg.ha_token)),
            "cache_control": {"type": "ephemeral"},
        }]
        self._last_used = time.time()

    # ------------------------------------------------------------------
    def reply(self, user_text: str) -> Iterator[Chunk]:
        """Stream a reply to `user_text` as emotion/speech chunks.  Handles the tool loop."""
        # Forget a stale conversation after 20 minutes of silence.
        if time.time() - self._last_used > 20 * 60:
            self.history.clear()
        self._last_used = time.time()

        self.history.append({"role": "user", "content": user_text})
        self._trim()
        try:
            yield from self._turn()
        except anthropic.RateLimitError:
            log.warning("rate limited")
            yield from self._canned("[annoyed] The Vanguard's comms are jammed. Try me again in a few seconds.")
        except anthropic.AuthenticationError:
            log.error("bad API key")
            yield from self._canned("[worried] My link to the Tower is refusing my credentials, Guardian. Check my API key.")
        except (anthropic.APIConnectionError, anthropic.APIStatusError) as e:
            log.warning("api error: %s", e)
            yield from self._canned(random.choice(OFFLINE_LINES))
        except ValueError as e:
            # a tool input the SDK could not parse at all (eager streaming)
            log.warning("unparseable tool input: %s", e)
            yield from self._canned("[worried] I fumbled that one. Say it again?")

    # ------------------------------------------------------------------
    def _turn(self) -> Iterator[Chunk]:
        for _round in range(6):               # tool loop guard
            parser = _StreamParser()
            kwargs = dict(
                model=self.cfg.model,
                max_tokens=self.cfg.max_tokens,     # spoken replies are short by design
                system=self._system,
                messages=self.history,
                tools=self.tools.definitions(),
                output_config={"effort": self.cfg.effort},
            )
            if self.cfg.fallbacks:
                # Server-side refusal fallback: if the model declines for policy reasons the
                # API re-runs the request on a fallback model inside the same call.
                kwargs["betas"] = ["server-side-fallback-2026-07-01"]
                kwargs["fallbacks"] = "default"
            with self.client.beta.messages.stream(**kwargs) as stream:
                for event in stream:
                    if event.type == "content_block_delta" and event.delta.type == "text_delta":
                        yield from parser.feed(event.delta.text)
                final = stream.get_final_message()
            yield from parser.flush()

            if final.stop_reason == "refusal":
                self.history.append({"role": "assistant", "content": REFUSAL_LINE})
                yield from self._canned(REFUSAL_LINE, record=False)
                return

            # Keep the full content (incl. tool_use blocks) so the transcript stays valid.
            self.history.append({"role": "assistant", "content": final.content})
            tool_uses = [b for b in final.content if b.type == "tool_use"]
            if not tool_uses or final.stop_reason == "max_tokens":
                return

            results = []
            for tu in tool_uses:
                yield Chunk(kind="tool", text=tu.name)
                err = self.tools.validate(tu.name, tu.input)
                if err:
                    results.append({"type": "tool_result", "tool_use_id": tu.id,
                                    "content": json.dumps({"error": err}), "is_error": True})
                    continue
                out = self.tools.run(tu.name, tu.input)
                results.append({"type": "tool_result", "tool_use_id": tu.id, "content": out})
            # all results in ONE user message
            self.history.append({"role": "user", "content": results})

    # ------------------------------------------------------------------
    def _canned(self, line: str, record: bool = True) -> Iterator[Chunk]:
        if record:
            self.history.append({"role": "assistant", "content": line})
        p = _StreamParser()
        yield from p.feed(line)
        yield from p.flush()

    def _trim(self):
        """Keep the last N user/assistant turns.  Never split a tool_use/tool_result pair."""
        limit = self.cfg.history_turns * 2
        while len(self.history) > limit:
            self.history.pop(0)
        # the transcript must start with a plain user turn, not a tool_result
        while self.history and (self.history[0]["role"] != "user"
                                or not isinstance(self.history[0]["content"], str)):
            self.history.pop(0)

    def forget(self):
        self.history.clear()


# ---------------------------------------------------------------------------
class _StreamParser:
    """Turns streamed text into emotion chunks and whole sentences."""

    def __init__(self):
        self.buf = ""
        self.emotion = ""

    def feed(self, text: str) -> Iterator[Chunk]:
        self.buf += text
        while True:
            m = _TAG.search(self.buf)
            if not m:
                break
            # everything before a tag is finished speech
            yield from self._sentences(self.buf[:m.start()], final=True)
            self.emotion = m.group(1).lower()
            self.buf = self.buf[m.end():]
            yield Chunk(kind="emotion", emotion=self.emotion)
        # a partially streamed tag at the end ("[hap") must wait for more text
        i = self.buf.rfind("[")
        if i != -1 and "]" not in self.buf[i:]:
            head, tail = self.buf[:i], self.buf[i:]
        else:
            head, tail = self.buf, ""
        yield from self._sentences(head, final=False)
        self.buf = self._rest + tail

    def _sentences(self, text: str, final: bool) -> Iterator[Chunk]:
        """Yield complete sentences from `text`; the incomplete remainder goes to self._rest."""
        self._rest = ""
        parts = [p for p in _SENTENCE_END.split(text) if p is not None]
        if not parts:
            return
        ends_clean = bool(re.search(r"[.!?]\s*$", text))
        if final or ends_clean:
            complete, self._rest = parts, ""
        else:
            complete, self._rest = parts[:-1], parts[-1]
        for s in complete:
            s = s.strip()
            if s:
                yield Chunk(kind="speech", text=s, emotion=self.emotion)

    def flush(self) -> Iterator[Chunk]:
        text = _TAG.sub("", self.buf).strip()
        self.buf = ""
        if text:
            yield Chunk(kind="speech", text=text, emotion=self.emotion)

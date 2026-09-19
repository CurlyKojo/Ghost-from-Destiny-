#!/usr/bin/env python3
"""Talk to the Ghost's brain in plain text (no audio, no hardware).  Needs ANTHROPIC_API_KEY."""
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from ghost.brain import Brain  # noqa: E402
from ghost.tools import TimerBook, ToolBox  # noqa: E402

logging.basicConfig(level=logging.INFO)
timers = TimerBook(on_fire=lambda label: print(f"\n*** timer '{label}' fired ***"))
brain = Brain(ToolBox(timers, set_volume=lambda v: print(f"(volume -> {v:.0%})")))
print("Chat with the Ghost. Ctrl-C to quit.")
while True:
    try:
        text = input("\nYou: ")
    except (EOFError, KeyboardInterrupt):
        break
    for c in brain.reply(text):
        if c.kind == "emotion":
            print(f"  ({c.emotion})", end=" ", flush=True)
        elif c.kind == "speech":
            print(c.text, end=" ", flush=True)
        elif c.kind == "tool":
            print(f"\n  [tool: {c.text}]", end=" ", flush=True)
    print()

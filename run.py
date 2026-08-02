# -*- coding: utf-8 -*-
import os
import sys
import time
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable

BUILD = os.path.join(HERE, "build_system_prompt.py")
SRC = os.path.join(HERE, "moodybot-system-prompt")
PROMPT = os.path.join(HERE, "system_prompt.txt")

BOT1 = os.path.join(HERE, "moodybot.py")
BOT2 = os.path.join(HERE, "moodybot_trialbot.py")


def should_rebuild_system_prompt():
    if not (os.path.exists(BUILD) and os.path.isdir(SRC)):
        return False
    if not os.path.exists(PROMPT):
        return True
    pm = os.path.getmtime(PROMPT)
    for r, _, files in os.walk(SRC):
        for f in files:
            if f.endswith(".md") and os.path.getmtime(os.path.join(r, f)) > pm:
                return True
    return False


if should_rebuild_system_prompt():
    print("Source changed, rebuilding system prompt...")
    subprocess.run([PY, BUILD], check=True, cwd=HERE)
    print("System prompt rebuilt.")
else:
    print("System prompt up to date or build script missing; skipping rebuild.")

# On hosts like Render, run only the main bot.
# Starting trial + main with the same TELEGRAM_BOT_TOKEN causes polling conflicts.
if os.getenv("RENDER") or os.getenv("RENDER_SERVICE_ID"):
    print("Render detected — starting main MoodyBot only.")
    raise SystemExit(subprocess.call([PY, BOT1], cwd=HERE))

print("Starting MoodyBot main bot...")
moodybot = subprocess.Popen([PY, BOT1], cwd=HERE)

trial_token = os.getenv("TELEGRAM_TRIAL_BOT_TOKEN")
trialbot = None
if trial_token and trial_token != os.getenv("TELEGRAM_BOT_TOKEN"):
    time.sleep(3)
    print("Starting MoodyBot trial bot...")
    trialbot = subprocess.Popen([PY, BOT2], cwd=HERE)
else:
    print("Skipping trial bot (set a distinct TELEGRAM_TRIAL_BOT_TOKEN to enable).")

try:
    print("Bots launched. Press Ctrl+C to terminate.")
    moodybot.wait()
    if trialbot:
        trialbot.wait()
except KeyboardInterrupt:
    print("Stopping…")
    moodybot.terminate()
    if trialbot:
        trialbot.terminate()
    moodybot.wait()
    if trialbot:
        trialbot.wait()

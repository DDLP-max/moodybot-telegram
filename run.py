# -*- coding: utf-8 -*-
import subprocess
import signal
import platform
import os
import time
# -*- coding: utf-8 -*-
# -*- coding: utf-8 -*-
import os, sys, time, platform, signal, subprocess

HERE  = os.path.dirname(os.path.abspath(__file__))      # ...\moodybot\replit
PY    = sys.executable

# 🔧 Everything is inside replit/
BUILD = os.path.join(HERE, "build_system_prompt.py")
SRC   = os.path.join(HERE, "moodybot-system-prompt")
PROMPT= os.path.join(HERE, "system_prompt.txt")         # output lives here too

BOT1  = os.path.join(HERE, "moodybot.py")
BOT2  = os.path.join(HERE, "moodybot_trialbot.py")

def should_rebuild_system_prompt():
    # Only rebuild if build script + source dir exist
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
    print("🧱 Source changed, rebuilding system prompt...")
    subprocess.run([PY, BUILD], check=True, cwd=HERE)   # run from replit/
    print("✅ System prompt rebuilt.")
else:
    print("📋 System prompt up to date or build script missing; skipping rebuild.")

moody_log = open(os.path.join(HERE, "moodybot.log"), "w")
trial_log = open(os.path.join(HERE, "trialbot.log"), "w")

print("Starting MoodyBot main bot...")
moodybot = subprocess.Popen([PY, BOT1], stdout=moody_log, stderr=subprocess.STDOUT, cwd=HERE)

time.sleep(3)
print("Starting MoodyBot trial bot...")
trialbot = subprocess.Popen([PY, BOT2], stdout=trial_log, stderr=subprocess.STDOUT, cwd=HERE)

try:
    print("🟢 Both bots launched. Press Ctrl+C to terminate.")
    moodybot.wait(); trialbot.wait()
except KeyboardInterrupt:
    print("⛔ Stopping…")
    moodybot.terminate(); trialbot.terminate()
    moodybot.wait(); trialbot.wait()
finally:
    moody_log.close(); trial_log.close()

# -*- coding: utf-8 -*-
import os
import openai
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENROUTER_API_KEY")
if not api_key:
    raise RuntimeError("Set OPENAI_API_KEY or OPENROUTER_API_KEY in the environment")

client = openai.OpenAI(api_key=api_key)

try:
    models = client.models.list()
    print("✅ Success! Got models:", [model.id for model in models.data[:3]])
except Exception as e:
    print("❌ Failed:", e)

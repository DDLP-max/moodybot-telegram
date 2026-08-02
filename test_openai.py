# -*- coding: utf-8 -*-
# test_openai.py

import openai
import os
from dotenv import load_dotenv

load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")
print("Using key:", openai.api_key)

try:
    models = openai.Model.list()
    print("✅ OpenAI connection successful! Models:", [m.id for m in models.data])
except Exception as e:
    print("❌ OpenAI error:", e)

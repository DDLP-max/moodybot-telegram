# -*- coding: utf-8 -*-
from postprocessing import strip_prefab_phrases

# Test cases
test_cases = [
    "ah, reckless mess, you did it again.",
    "ah, you beautiful mess, here's the truth.",
    "ah you did it again.",
    "Ah, this is important.",
]

for test in test_cases:
    result = strip_prefab_phrases(test)
    print(f"Input:  '{test}'")
    print(f"Output: '{result}'")
    print(f"Changed: {test != result}")
    print()


# -*- coding: utf-8 -*-
"""
Sample demonstration of the post-processing pipeline with logging.
Shows how 'Cialdini' is preserved through all stages.
"""

import os
import logging
from postprocessing import process_bot_output

# Set up logging to show debug output
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# Enable debug logging for post-processing
os.environ['DEBUG'] = 'bot:postprocess'
os.environ['SPELLCHECK_BOT_OUTPUT'] = 'false'

def demonstrate_pipeline():
    """Demonstrate the post-processing pipeline with sample text."""
    
    print("=== MoodyBot Post-Processing Pipeline Demo ===\n")
    
    # Sample text that would previously have been autocorrected
    sample_texts = [
        "Cialdini proved that influence works through psychological principles.",
        "The work of Kahneman and Tversky revolutionized behavioral economics.",
        "MoodyBot understands the *nuances* of human psychology.",
        "In Da Nang, the Ala Wai canal flows through the city.",
        "Donna Walden's research on _persuasion_ is groundbreaking."
    ]
    
    for i, text in enumerate(sample_texts, 1):
        print(f"--- Example {i} ---")
        print(f"Input:  {text}")
        
        # Process through the pipeline
        result = process_bot_output(text)
        
        print(f"Output: {result}")
        print(f"Changed: {text != result}")
        print()
    
    print("=== Demo Complete ===")
    print("Notice how proper nouns like 'Cialdini', 'Kahneman', etc. are preserved")
    print("while MarkdownV2 special characters are properly escaped.")

if __name__ == "__main__":
    demonstrate_pipeline()


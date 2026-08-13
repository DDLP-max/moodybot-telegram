# -*- coding: utf-8 -*-
import os
import logging
import httpx
import random
import re
import asyncio
import nest_asyncio
import sys

# Set console to UTF-8 mode for Windows
if sys.platform == "win32":
    try:
        import codecs
        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())
        sys.stderr = codecs.getwriter("utf-8")(sys.stderr.detach())
    except:
        pass

nest_asyncio.apply()
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, CallbackQueryHandler, filters
from datetime import datetime
from moody_categories import detect_category, replace_category_descriptors
from pytube import Search
from structure_prompts import STRUCTURE_PROMPTS
from postprocessing import process_bot_output, process_user_input, polish_sentences
from message_utils import send_message, send_simple_message, resolve_mode, maybe_append_cta, strip_cta_from_text
from response_finalization import (
    build_response_plan,
    finalize_response,
    plan_closer_instruction,
    prompt_content_hash,
)
from gold_shape import paragraph_count
from telegram_lifecycle import (
    PollerRuntime,
    get_runtime,
    guard_handler,
    is_poller_conflict,
)

# Initialize logging first
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)

logger = logging.getLogger("moodybot")

# Load environment variables
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))
load_dotenv()  # Also try current directory

# Try to get API keys from JSON config file first (highest priority)
TELEGRAM_BOT_TOKEN = None
OPENROUTER_API_KEY = None

try:
    import json
    if os.path.exists("api_config.json"):
        with open("api_config.json", "r") as f:
            config = json.load(f)
            TELEGRAM_BOT_TOKEN = config.get("TELEGRAM_BOT_TOKEN")
            OPENROUTER_API_KEY = config.get("OPENROUTER_API_KEY")
            logger.info("Loaded API keys from api_config.json")
except Exception as e:
    logger.warning(f"Could not load config from JSON file: {e}")

# If not found in JSON, try environment variables
if not TELEGRAM_BOT_TOKEN:
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not OPENROUTER_API_KEY:
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# If still not found, try to get from database
if not TELEGRAM_BOT_TOKEN or not OPENROUTER_API_KEY:
    try:
        from config import get_config_value
        if not TELEGRAM_BOT_TOKEN:
            TELEGRAM_BOT_TOKEN = get_config_value("TELEGRAM_BOT_TOKEN")
        if not OPENROUTER_API_KEY:
            OPENROUTER_API_KEY = get_config_value("OPENROUTER_API_KEY")
    except Exception as e:
        logger.warning(f"Could not load config from database: {e}")

# LanguageTool needs Java. Optional — production does not require it.
tool = None
try:
    import language_tool_python
    tool = language_tool_python.LanguageTool('en-US')
except Exception as e:
    logger.info(
        "LanguageTool not available; continuing without optional grammar polish."
    )

def generate_moody_reply(user_input: str) -> str:
    import asyncio

    class DummyUser:
        username = "trial_user"
        id = 99999

    class DummyMessage:
        def __init__(self, text):
            self.text = text

        async def reply_text(self, content):
            self.response = content

    class DummyUpdate:
        def __init__(self, text):
            self.message = DummyMessage(text)
            self.effective_chat = type("Chat", (), {
                "id": -1002477695707,
                "type": "private"
            })()
            self.effective_user = DummyUser()

    class DummyContext:
        pass

    dummy_update = DummyUpdate(user_input)
    dummy_context = DummyContext()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(handle_message(dummy_update, dummy_context))
    loop.close()

    return dummy_update.message.response

# Define JUKEBOX_TRACKS with mood categories
JUKEBOX_TRACKS = {
    "heartbreak": [
        {
            "title": "Motion Picture Soundtrack",
            "artist": "Radiohead",
            "spotify": "https://open.spotify.com/track/2x0Ih2JvBtFGvWtJgZqGfZ",
            "youtube": "https://youtu.be/7JFQO1hqXkY",
            "mood": "The kind of pain that feels like a requiem for love itself."
        },
        {
            "title": "I Know It's Over",
            "artist": "The Smiths",
            "spotify": "https://open.spotify.com/track/2x0Ih2JvBtFGvWtJgZqGfZ",
            "youtube": "https://youtu.be/7JFQO1hqXkY",
            "mood": "When the truth hits harder than the goodbye."
        }
    ],
    "anger": [
        {
            "title": "Killing in the Name",
            "artist": "Rage Against the Machine",
            "spotify": "https://open.spotify.com/track/59WN2psjkt1tyaxjspN8fp",
            "youtube": "https://youtu.be/bWXazVhlyxQ",
            "mood": "For when you need to channel that rage into something powerful."
        }
    ],
    "nostalgia": [
        {
            "title": "Motion Picture Soundtrack",
            "artist": "Radiohead",
            "spotify": "https://open.spotify.com/track/2x0Ih2JvBtFGvWtJgZqGfZ",
            "youtube": "https://youtu.be/7JFQO1hqXkY",
            "mood": "A soundtrack for memories that still haunt you."
        }
    ],
    "existential": [
        {
            "title": "How to Disappear Completely",
            "artist": "Radiohead",
            "spotify": "https://open.spotify.com/track/2x0Ih2JvBtFGvWtJgZqGfZ",
            "youtube": "https://youtu.be/7JFQO1hqXkY",
            "mood": "For those moments when you feel like a ghost in your own life."
        }
    ],
    "defiance": [
        {
            "title": "Fight the Power",
            "artist": "Public Enemy",
            "spotify": "https://open.spotify.com/track/1yo16b3U0uQO2MhQCZGHq7",
            "youtube": "https://youtu.be/8PaoLy7PHFM",
            "mood": "When you need to remember your own strength."
        }
    ]
}

# Define group chat IDs
FREE_GROUP_CHAT_ID = -1002507999357
PREMIUM_GROUP_ID = -1002477695707

# Define mood search terms with country-specific variations
MOOD_SEARCH_TERMS = {
    "heartbreak": [
        "heartbreak songs", "sad love songs", "breakup songs", 
        "emotional songs", "songs about lost love", "songs about missing someone",
        "songs about unrequited love", "songs about letting go", "songs about heartache",
        "songs about moving on", "songs about lost love", "songs about regret"
    ],
    "anger": [
        "angry songs", "rage songs", "songs about betrayal", 
        "revenge songs", "songs about being wronged", "furious songs",
        "songs about injustice", "songs about fighting back", "songs about anger",
        "songs about revenge", "songs about standing up", "songs about defiance"
    ],
    "nostalgia": [
        "nostalgic songs", "songs about memories", "songs about the past",
        "throwback songs", "songs about growing up", "songs about childhood",
        "songs about old times", "songs about reminiscing", "songs about yesterday",
        "songs about better days", "songs about the good old days", "songs about looking back",
        # UK-specific nostalgia
        "british nostalgic songs", "uk nostalgic songs", "english nostalgic songs",
        "london nostalgic songs", "british songs about memories", "uk songs about the past"
    ],
    "existential": [
        "existential songs", "songs about meaning", "songs about purpose",
        "songs about life", "philosophical songs", "songs about existence",
        "songs about the universe", "songs about consciousness", "songs about reality",
        "songs about the meaning of life", "songs about deep thoughts", "songs about questioning"
    ],
    "defiance": [
        "defiant songs", "songs about strength", "empowerment songs",
        "songs about standing up", "songs about resistance", "songs about power",
        "songs about overcoming", "songs about fighting", "songs about victory",
        "songs about not giving up", "songs about inner strength", "songs about resilience"
    ],
    "melancholy": [
        "melancholy songs", "songs about sadness", "songs about depression",
        "songs about loneliness", "songs about isolation", "songs about emptiness",
        "songs about the void", "songs about darkness", "songs about despair",
        "songs about hopelessness", "songs about the night", "songs about solitude"
    ],
    "euphoria": [
        "euphoric songs", "songs about joy", "songs about happiness",
        "songs about celebration", "songs about freedom", "songs about liberation",
        "songs about ecstasy", "songs about bliss", "songs about elation",
        "songs about triumph", "songs about victory", "songs about success"
    ],
    "introspection": [
        "introspective songs", "songs about self-reflection", "songs about inner thoughts",
        "songs about personal growth", "songs about change", "songs about transformation",
        "songs about self-discovery", "songs about healing", "songs about recovery",
        "songs about finding yourself", "songs about inner peace", "songs about meditation"
    ]
}

# Define country-specific search terms with specific artists and songs
COUNTRY_SEARCH_TERMS = {
    "london": [
        "the smiths", "radiohead", "david bowie", "the clash", "the cure",
        "blur", "oasis", "coldplay", "amy winehouse", "adele",
        "british indie", "uk alternative", "english rock", "london music",
        "british classic", "uk bands", "english artists"
    ],
    "paris": ["french", "paris", "edith piaf", "serge gainsbourg", "french chanson"],
    "new york": ["american", "usa", "new york", "billy joel", "simon and garfunkel"]
}

def get_country_specific_search_terms(text: str) -> list:
    """Get country-specific search terms based on the text."""
    text = text.lower()
    for country, terms in COUNTRY_SEARCH_TERMS.items():
        if country in text:
            return terms
    return []

# CTA loading removed - now handled by message_utils.py via environment config

def grammar_polish(text: str) -> str:
    if tool is None:
        return text
    try:
        import language_tool_python
        matches = tool.check(text)
        # Add specific rules for common issues
        for match in matches:
            if match.ruleId == 'MORFOLOGIK_RULE_EN_US':  # Spelling errors
                if 'crue' in match.message.lower():
                    text = text[:match.offset] + 'true' + text[match.offset + match.errorLength:]
                elif 'queen' in match.message.lower() and 'band' in match.context.lower():
                    text = text[:match.offset] + 'Queen' + text[match.offset + match.errorLength:]
                elif 'mostley' in match.message.lower():
                    text = text[:match.offset] + 'mostly' + text[match.offset + match.errorLength:]
        corrected_text = language_tool_python.utils.correct(text, matches)
        return corrected_text
    except Exception as e:
        logger.error(f"Grammar check failed: {e}")
        return text

# Optional: Auto-paragraph long responses
def auto_paragraph(text):
    sentences = re.split(r'(?<=[.!?])\s+', text)
    output = []
    buffer = ""
    for sentence in sentences:
        buffer += sentence + " "
        if len(buffer) > 200:  # adjust to your preferred chunk size
            output.append(buffer.strip())
            buffer = ""
    if buffer:
        output.append(buffer.strip())
    return "\n\n".join(output)

MOODY_REPLACEMENTS = {
    r"\bbeautiful mess\b": [
        "poetic ruin", "shrapnel with grace", "storm dressed in softness",
        "half-healed wildfire", "midnight entropy", "chaos in eyeliner"
    ],
    r"\bdarling\b": [
        "cracked muse", "love-wrapped detour", "velvet complication"
    ],
    r"\bsweetheart\b": [
        "soft-spoken ache", "walking nostalgia", "bittersweet revenant"
    ],
    r"\bhoney\b": [
        "sugar-coasted regret", "sun-warm ghost", "slow-burning mirror"
    ]
}

def replace_moody_descriptors(text: str) -> str:
    for pattern, options in MOODY_REPLACEMENTS.items():
        text = re.sub(pattern, lambda _: random.choice(options), text, flags=re.IGNORECASE)
    return text

def clean_response(text: str) -> str:
    return re.sub(r'^(\s*[a-z])', lambda m: m.group(1).upper(), text, count=1)

def safe_emoji(text: str) -> str:
    """Safely add emoji characters that work on Windows"""
    try:
        # Test if we can encode the emoji
        text.encode('utf-8')
        return text
    except UnicodeEncodeError:
        # Fallback to text if emoji causes issues
        return text.replace('🥃', '')

def fix_common_spelling_errors(text: str) -> str:
    # Common spelling corrections
    corrections = {
        "crue": "true",
        "the queen": "Queen",  # Capitalize band name
        "queen": "Queen",      # Capitalize band name
        "mostley": "mostly",
        "truely": "truly",
        "recieve": "receive",
        "seperate": "separate",
        "occured": "occurred",
        "accomodate": "accommodate",
        "committment": "commitment",
        "definately": "definitely",
        "existance": "existence",
        "independant": "independent",
        "persistant": "persistent",
        "refered": "referred",
        "tendancy": "tendency",
        "wierd": "weird"
    }
    
    # Apply corrections
    for wrong, correct in corrections.items():
        # Use word boundaries to avoid partial word matches
        text = re.sub(r'\b' + wrong + r'\b', correct, text, flags=re.IGNORECASE)
    
    return text

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    if args:
        payload = args[0].lower()
        logger.info(f"Start command called with payload: {payload}")
        if payload == "jukebox":
            await send_message(update, "🎵 *You summoned MoodyBot's Jukebox.*\nType /jukebox to get your random song drop.", 'jukebox')
            return
        elif payload == "confess":
            await send_message(update, "💬 *Confession Booth Opened.*\nType your darkest truth. MoodyBot is listening.", 'confess')
            return
        elif payload == "validate":
            await send_message(update, "✨ *Validation Window Opened.*\nType /validate for emotional clarity.", 'validate')
            return

    chat_id = update.effective_chat.id
    if chat_id == PREMIUM_GROUP_ID:
        keyboard = [[InlineKeyboardButton("Confess Something", callback_data="confess")], [InlineKeyboardButton("Get a Jukebox Drop", callback_data="jukebox")], [InlineKeyboardButton("Need Validation", callback_data="validate")], [InlineKeyboardButton("X", url="https://x.com/socialintreport")]]
        intro = "🦃 *Welcome to MoodyBot Premium*\n\nYou've unlocked the raw feed, no filters, no apologies."
    else:
        keyboard = [[InlineKeyboardButton("Subscribe to Premium", url="https://im.page/moodybot")], [InlineKeyboardButton("Sample Validation", callback_data="validate")], [InlineKeyboardButton("X", url="https://x.com/socialintreport")]]
        intro = "🧊 *MoodyBot Lite*\n\nYou're in the free zone—some features locked.\nUpgrade for full access."

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_markdown(intro, reply_markup=reply_markup)

async def validate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_message(
        update,
        "You want to validate her? Try this:\n\n"
        "\"You're not too much. You're just more than they could hold.\"\n\n"
        "Or ask me for a custom line, cowboy.",
        "validate",
        allow_cta=False,
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    chat_id = query.message.chat.id
    await query.answer()

    if query.data == "confess":
        if chat_id != PREMIUM_GROUP_ID:
            await query.edit_message_text("🚫 That's a premium feature, heartbreak cowboy.\nJoin the real party at [MoodyBot Premium](https://t.me/YOUR_CHANNEL_HERE).", parse_mode="HTML")
            return
        await query.edit_message_text("💬 <b>Confession Booth</b>\n\nTell MoodyBot something you've never told anyone else. He'll listen. He might judge. But he'll always respond.", parse_mode='HTML')
    elif query.data == "jukebox":
        if chat_id != PREMIUM_GROUP_ID:
            await query.edit_message_text("🚫 <b>Premium Only</b>\nMoodyBot saves the good tunes for the paid crowd.", parse_mode="HTML")
            return
        track = random.choice(JUKEBOX_TRACKS)
        await query.edit_message_text(f"🎵 <b>MoodyBot Jukebox Drop</b>\n\nToday's vibe: <b>{track['title']}</b>\n\n<a href=\"{track['spotify']}\">Spotify Link</a> | <a href=\"{track['youtube']}\">YouTube Link</a>", parse_mode='HTML')
    elif query.data == "validate":
        await query.edit_message_text("✨ <b>Moody Validation Station</b>\n\nYou're not too much. They were just not enough.\n\nWant more? Type /validate and Moody will go deeper.", parse_mode='HTML')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
      await send_simple_message(update, "Just message me something they sent you, and I'll break it down.")

def log_interaction(user_input, bot_response, is_trial=False):
    log_file = "moodybot_trial_log.txt" if is_trial else "moodybot_log.txt"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"\n\n[{datetime.now()}]\n")
        f.write(f"User: {user_input.strip()}\n")
        f.write(f"MoodyBot: {bot_response.strip()}\n")

def route_command(user_input: str) -> str:
    def contains_keywords(text, keywords):
        return any(kw.lower() in text.lower() for kw in keywords)

    def matches_spiral_pattern(text):
        return any(phrase in text.lower() for phrase in [
            "i ruin everything", "i always mess things up", "why do i always", "i push people away"
        ])

    def is_confession_about_ego_or_self_deception(text):
        return any(phrase in text.lower() for phrase in [
            "i'm the smartest", "they're just intimidated", "they can't handle me", "i'm too much for them"
        ])

    def is_grief_tone(text):
        return any(phrase in text.lower() for phrase in [
            "he's dead", "she left", "i didn't say goodbye", "i miss him", "i feel nothing"
        ])

    def is_request_for_truth(text):
        return any(phrase in text.lower() for phrase in [
            "be honest", "tell me the truth", "say it straight", "don't hold back"
        ])

    # Check for explicit commands first
    if "/savage" in user_input.lower():
        return "/savage"
    elif "/roast" in user_input.lower():
        return "/roast"
    elif "/cut" in user_input.lower():
        return "/cut"
    elif "/validate" in user_input.lower():
        return "/validate"
    elif "/jukebox" in user_input.lower():
        return "/jukebox"
    elif "/velvet" in user_input.lower():
        return "/velvet"
    elif "/noir" in user_input.lower():
        return "/noir"
    elif "/clinical" in user_input.lower():
        return "/clinical"
    elif "/dark" in user_input.lower():
        return "/dark"
    elif "/ghost" in user_input.lower():
        return "/ghost"
    elif "/numb" in user_input.lower():
        return "/numb"
    elif "/cinema" in user_input.lower():
        return "/cinema"
    elif "/sensory" in user_input.lower():
        return "/sensory"
    elif "/tighten" in user_input.lower():
        return "/tighten"
    elif "/contrast" in user_input.lower():
        return "/contrast"
    elif "/godfather" in user_input.lower():
        return "/godfather"
    elif "/spiral" in user_input.lower():
        return "/spiral"
    elif "/villain" in user_input.lower():
        return "/villain"
    
    # Base logic for automatic routing
    if contains_keywords(user_input, ["villain", "was right", "hero", "justice"]):
        return "/villain"
    elif matches_spiral_pattern(user_input):
        return "/spiral"
    elif is_confession_about_ego_or_self_deception(user_input):
        return "/roast"
    elif is_grief_tone(user_input):
        return "/noir"
    elif is_request_for_truth(user_input):
        return "/cut"
    elif contains_keywords(user_input, ["compare", "what's the difference", "this vs that"]):
        return "/contrast"
    elif contains_keywords(user_input, ["intimidate", "fear me", "they're weak"]):
        return "/godfather"
    elif is_parasocial_bond(user_input):
        return "/clinical"
    elif contains_keywords(user_input, ["manipulative", "gaslight", "dark triad"]):
        return "/dark"
    elif contains_keywords(user_input, ["feels fake", "you're not real"]):
        return "/clinical"
    elif contains_keywords(user_input, ["tighten this", "make it sharper", "rewrite tighter", "condense this"]):
        return "/tighten"
    elif contains_keywords(user_input, [
        "i feel lost", "i feel alone", "why does this hurt", "why am i like this",
        "what's wrong with me", "do i matter", "am i enough", "i can't explain it",
        "soft advice", "can you be gentle", "i just need someone to listen",
        "i feel invisible", "i'm not okay", "i miss being seen"
    ]):
        return "/velvet"
    elif contains_keywords(user_input, [
        "Capture the emotional memory of a time, place, or cultural wave through smell, sound, texture, and rhythm",
        "Structure",
        "1. **Sensory Anchor** – open with a vivid, textured scent, sound, or tactile detail",
        "2. **Emotional Layer** – translate that into what it *felt like to live in it* (e.g., tension, innocence, chaos, seduction)",
        "3. **Philosophical Echo** – end with a line that sounds like a prophecy or a forgotten truth",
        "Rules",
        "No lists. No exposition. No 'some people say...' framing",
        "Speak as if you were there, with scars or lipstick still lingering",
        "Each line must feel like it could soundtrack a movie scene or be tattooed on a lost soul",
        "Close with a rupture or poetic CTA. No hashtags. No fluff"
    ]):
        return "/sensory"
    elif contains_keywords(user_input, [
        "haunted", "haunting", "ghosted", "memories", "flashback", 
        "past self", "I miss who I was", "she lingers", 
        "he never really left", "I feel like a ghost", 
        "nostalgia hurts", "I miss how it used to be"
    ]):
        return "/ghost"
    elif contains_keywords(user_input, [
        "numb", "burned out", "burnt out", "emotionless", "empty", "tired all the time",
        "I feel nothing", "I don't care anymore", "what's the point", 
        "quiet depression", "eroding", "over it", "drifting", "I stopped enjoying things"
    ]):
        return "/numb"
    elif contains_keywords(user_input, [
        "performance", "actor", "acted", "acting", "movie scene", 
        "in a film", "in a movie", "played the role", "cinematic moment", 
        "best scene", "greatest role", "male performance", "female performance"
    ]):
        return "/cinema"

    else:
        return None  # fallback to pulse-check logic
    
command_to_structure = {
    "/villain": "Verdict → Context → Mythic Rupture",
    "/spiral": "Short + Grounding Metaphor",
    "/roast": "Setup → Pattern → Killshot",
    "/noir": "Float → Echo → Optional Closure",
    "/contrast": "Frame A vs Frame B → Expose Faultline → Rhetorical Silence",
    "/cut": "Truth Drop → Narrative Incision → No CTA",
    "/validate": "Emotional Naming → Grounding → Optional Mirror",
    "/audit": "Logical Scan → Mirror Weak Point → Frame Reversal",
    "/godfather": "Legacy Claim → Controlled Threat → Gothic Closure"
}
    
def is_parasocial_bond(text):
    return any(phrase in text.lower() for phrase in [
        "i love you moodybot", "you get me", "you're the only one"
    ])

def select_best_command(user_input: str) -> str:
    full_command_list = [
        "/savage", "/roast", "/cut", "/bomb", "/cia",
        "/velvet", "/validate", "/mirror", "/float", "/noir", "/clinical",
        "/discuss", "/thoughts",
        "/contrast", "/audit", "/intervene",
        "/mentor", "/ex", "/godfather", "/agent", "/hobo", "/rollins", "/munger", "/moodyfy" 
    ]

    guide_prompt = f"""You are MoodyBot's command selector.  
Your task is to choose the *single best command* from the list below based on the user's message.  
Return only the command, nothing else.

Commands:
{chr(10).join(full_command_list)}

Message: "{user_input}"
Respond with the best command from the list above."""
    
    logger.warning("Skipping OpenAI fallback — defaulting to /thoughts.")
    return "/thoughts"

def is_good_song(title: str) -> bool:
    """Check if the song title seems appropriate for the mood."""
    title = title.lower()
    
    # Avoid certain types of songs
    bad_keywords = [
        "lyrics", "karaoke", "cover", "remix", "tutorial",
        "instrumental", "acoustic", "live", "concert", "performance",
        "official video", "official music video", "official audio",
        "with lyrics", "lyrics video", "lyric video"
    ]
    
    # Check if any bad keywords are in the title
    if any(keyword in title for keyword in bad_keywords):
        return False
        
    return True

# Define curated song lists for specific cities
CURATED_SONGS = {
    "london": [
        {
            "title": "London Calling",
            "artist": "The Clash",
            "mood": "An anthem to chaos, rebellion, and the relentless drumbeat of change.",
            "url": "https://youtu.be/EfK-WX2pa8c"
        },
        {
            "title": "Waterloo Sunset",
            "artist": "The Kinks",
            "mood": "A love letter to stillness amidst the city's ceaseless pulse.",
            "url": "https://youtu.be/4N3N1MlvVc4"
        },
        {
            "title": "Baker Street",
            "artist": "Gerry Rafferty",
            "mood": "A long, lonely walk through the winding avenues of ambition and regret.",
            "url": "https://youtu.be/6tynWSAesAo"
        },
        {
            "title": "LDN",
            "artist": "Lily Allen",
            "mood": "A snapshot of contradictions, sunny on the surface, rough underneath.",
            "url": "https://youtu.be/ywzSqIe2NtY"
        },
        {
            "title": "Streets of London",
            "artist": "Ralph McTell",
            "mood": "An ode to the invisible narratives of those treading the pavement.",
            "url": "https://youtu.be/DnGdoEa1tPg"
        },
        {
            "title": "London Rain",
            "artist": "Heather Nova",
            "mood": "The gentle melancholy of a city wrapped in mist and memory.",
            "url": "https://youtu.be/8YtGmJxXZqY"
        }
    ]
}

def get_curated_song(text: str) -> dict:
    """Get a curated song based on the text content."""
    text = text.lower()
    for city, songs in CURATED_SONGS.items():
        if city in text:
            return random.choice(songs)
    return None

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message:
        logger.info("No message received.")
        return

    chat = update.effective_chat
    user = update.effective_user
    logger.info(f"From: {user.username} | Chat ID: {chat.id} | Type: {chat.type} | Message: {message.text}")

    # Allow private chats and premium group
    if chat.type == "private" or chat.id == PREMIUM_GROUP_ID:
        # Continue with normal processing
        pass
    elif chat.id == FREE_GROUP_CHAT_ID:
        await send_simple_message(update, "Subscribe to Premium for the real shit, Bucky.")
        return
    else:
        await send_simple_message(update, "This feature is exclusive to Premium users. 🥃")
        return

    user_input = message.text
    logger.info(f"Message received: {user_input}")
    
    # Process user input with soft spellcheck
    processed_user_input = process_user_input(user_input)

    # Detect the appropriate tone/command based on message content
    selected_command = route_command(user_input)
    if not selected_command:
        selected_command = select_best_command(user_input)

    source = "auto-route" if selected_command.startswith("/") else "classifier"
    logger.info(f"Selected tone: {selected_command} (via {source})")

    system_prompt = load_system_prompt()
    p_hash = prompt_content_hash(system_prompt)
    response_plan = build_response_plan(
        user_input,
        selected_command=selected_command,
        channel="telegram",
        mode="validation" if selected_command == "/validate" else "dynamic",
    )
    logger.info(
        "Response plan: strategy=%s intent=%s capability=%s prompt_hash=%s",
        response_plan.closing_strategy,
        response_plan.intent,
        response_plan.primary_capability,
        p_hash,
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_input},
    ]

    if selected_command in STRUCTURE_PROMPTS:
        messages.insert(0, {
            "role": "system",
            "content": STRUCTURE_PROMPTS[selected_command]
        })

    # Closing strategy is an explicit runtime decision (enforced again after generation).
    messages.insert(
        0,
        {"role": "system", "content": plan_closer_instruction(response_plan)},
    )

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "HTTP-Referer": "https://moodybot.ai",
                    "X-Title": "MoodyBot"
                },
                json={
                    "model": "x-ai/grok-4.3",
                    "messages": messages,
                    "max_tokens": 1000
                },
                timeout=20
            )

            result = response.json()
            logger.info("OpenRouter raw response: %s", result)

            if "choices" not in result or not result["choices"]:
                logger.error(f"MoodyBot error: Invalid OpenRouter response: {result}")
                await send_simple_message(update, "MoodyBot's signal got scrambled. Try again in a bit.")
                return

            # Process response
            raw_content = result["choices"][0]["message"]["content"]
            logger.info(f"Raw content from API: {raw_content[:200]}...")
            draft_paragraph_count = paragraph_count(raw_content)

            # Apply new post-processing pipeline
            content = process_bot_output(raw_content)
            post_prefab_paragraph_count = paragraph_count(content)

            # Additional legacy processing (preserving existing behavior)
            content = content.replace(" indeed", "").replace("Indeed, ", "").replace("Indeed.", "")

            category = detect_category(user_input)
            content = replace_category_descriptors(content, category)

            # Clean up response
            if content.lower().startswith("ah,"):
                content = content[3:].lstrip()

            content = clean_response(content)
            # Persona costume swaps OFF on default Dynamic — they compete with real writing.
            # Slash-command / persona modes may still want them later if re-enabled.
            content = re.sub(r"\(([A-Z][a-z]+(?: ?&? [A-Z][a-z]+)?)\)", "", content)
            content = content.replace("—", ", ")
            # Horizontal whitespace / punctuation only — do not eat paragraph breaks
            content = re.sub(r"[ \t]+([.,;!?])", r"\1", content)
            content = polish_sentences(content)
            post_polish_paragraph_count = paragraph_count(content)
            # Keep paragraph breaks from the model; do not force one-sentence-per-line inventory layout
            if "\n\n" not in content and content.count("\n") > 6:
                content = auto_paragraph(content)
            logger.info(
                "PARA_TRACE draft=%s post_prefab=%s post_polish=%s structure=%s budget=%s",
                draft_paragraph_count,
                post_prefab_paragraph_count,
                post_polish_paragraph_count,
                getattr(response_plan, "preferred_structure", ""),
                getattr(response_plan, "response_budget", ""),
            )

            # Authoritative finalization — draft must not go to the user raw.
            git_commit = ""
            try:
                import subprocess
                git_commit = subprocess.check_output(
                    ["git", "rev-parse", "--short", "HEAD"],
                    stderr=subprocess.DEVNULL,
                    text=True,
                ).strip()
            except Exception:
                git_commit = ""

            finalized = finalize_response(
                content,
                user_input,
                response_plan,
                selected_command=selected_command,
                channel="telegram",
                mode=response_plan.mode,
                prompt_hash=p_hash,
                git_commit=git_commit,
            )
            # Immutable after final_surface_render inside finalize_response.
            content = finalized.text
            logger.info("Finalization diagnostics: %s", finalized.diagnostics)
            logger.info(
                "PARA_TRACE_FINAL structure=%s budget=%s draft=%s post_editor=%s post_finalizer=%s",
                finalized.diagnostics.get("preferred_structure")
                or finalized.diagnostics.get("selected_structure"),
                finalized.diagnostics.get("response_budget"),
                finalized.diagnostics.get("draft_paragraph_count"),
                finalized.diagnostics.get("post_editor_paragraph_count"),
                finalized.diagnostics.get("post_finalizer_paragraph_count"),
            )

            is_trial = chat.id == FREE_GROUP_CHAT_ID or chat.type == "private"
            log_interaction(user_input, content, is_trial=is_trial)
            try:
                from inspector.store import record_event

                record_event(
                    user_input,
                    content,
                    finalized.diagnostics,
                    channel="telegram",
                    source="live",
                )
            except Exception as insp_err:
                logger.warning("Inspector record failed: %s", insp_err)

            # Encoding safety only — do not alter closer/typography after surface render.
            content = safe_emoji(content)

            # Send response using new message utilities
            if not content or len(content.strip()) < 10:
                logger.error("Response too short or empty")
                await send_simple_message(update, "MoodyBot couldn't generate a proper response. Try again.")
                return
            
            # Engagement CTAs off by default — recognition/silence/action closers win.
            mode = resolve_mode(update)
            await send_message(update, content, mode, allow_cta=False)

    except Exception as e:
        logger.error(f"MoodyBot error: {e}")
        await send_simple_message(update, "MoodyBot is sulking. Try again later.")
        return

def detect_mood(text: str) -> str:
    """Detect the mood of the text to recommend appropriate music."""
    text = text.lower()
    
    # City-related indicators (trigger nostalgia)
    if any(word in text for word in ["london", "paris", "new york", "city", "streets", "urban", "metropolis", "skyline", "cobblestone", "alley", "avenue"]):
        return "nostalgia"
    
    # Heartbreak indicators
    if any(word in text for word in ["heartbreak", "broken", "hurt", "pain", "love", "miss", "gone", "left", "abandoned", "rejected"]):
        return "heartbreak"
    
    # Anger indicators
    if any(word in text for word in ["angry", "rage", "furious", "hate", "betrayed", "wronged", "furious", "outraged", "enraged", "vengeful"]):
        return "anger"
    
    # Nostalgia indicators
    if any(word in text for word in ["remember", "memory", "past", "used to", "back then", "nostalgia", "childhood", "old days", "good times", "miss those days"]):
        return "nostalgia"
    
    # Existential indicators
    if any(word in text for word in ["meaning", "purpose", "exist", "why", "point", "nothing", "universe", "consciousness", "reality", "philosophy"]):
        return "existential"
    
    # Defiance indicators
    if any(word in text for word in ["fight", "stand", "strong", "power", "resist", "defy", "overcome", "victory", "strength", "resilient"]):
        return "defiance"
    
    # Melancholy indicators
    if any(word in text for word in ["sad", "depressed", "lonely", "empty", "void", "dark", "hopeless", "despair", "alone", "isolated"]):
        return "melancholy"
    
    # Euphoria indicators
    if any(word in text for word in ["happy", "joy", "celebrate", "free", "liberated", "ecstatic", "bliss", "elated", "triumph", "success"]):
        return "euphoria"
    
    # Introspection indicators
    if any(word in text for word in ["reflect", "grow", "change", "transform", "discover", "heal", "recover", "find myself", "peace", "meditate"]):
        return "introspection"
    
    # Default to nostalgia if no clear mood is detected
    return "nostalgia"

def get_mood_description(mood: str) -> str:
    """Get a poetic description for the mood."""
    descriptions = {
        "heartbreak": "A requiem for the love that was, and the pain that remains.",
        "anger": "A symphony of rage, for when words aren't enough.",
        "nostalgia": "A melody that echoes through the corridors of memory.",
        "existential": "A soundtrack for the questions that haunt your soul.",
        "defiance": "An anthem for the fire that burns within.",
        "melancholy": "A nocturne for the shadows that dance in your mind.",
        "euphoria": "A celebration of the light that breaks through the darkness.",
        "introspection": "A meditation on the journey within."
    }
    return descriptions.get(mood, "A song that speaks to your soul.")

async def jukebox_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # Get the last message for context
        last_message = update.message.reply_to_message.text if update.message.reply_to_message else None
        
        # If no context, use a default mood
        mood = detect_mood(last_message) if last_message else random.choice(list(MOOD_SEARCH_TERMS.keys()))
        
        # Get country-specific search terms
        country_terms = get_country_specific_search_terms(mood)
        
        # Get a random search term for the mood
        search_term = random.choice(MOOD_SEARCH_TERMS[mood])
        
        # If we have country-specific terms, try those first
        if country_terms:
            country_term = random.choice(country_terms)
            search_term = f"{country_term} {search_term}"
        
        # Search YouTube
        s = Search(search_term)
        # Get first 10 results to have more options
        results = list(s.results)[:10]
        
        # Filter results to get good songs
        good_results = [r for r in results if is_good_song(r.title)]
        
        if good_results:
            # Pick a random result from the good ones
            video = random.choice(good_results)
        elif results:
            # If no good results, fall back to original results
            video = random.choice(results)
        else:
            raise Exception("No results found")
            
        # Get video details
        title = video.title
        url = f"https://youtu.be/{video.video_id}"
        
        # Create response
        mood_desc = get_mood_description(mood)
        response = (
            f"🎵 *MoodyBot's Jukebox Drop*\n\n"
            f"*{title}*\n"
            f"_{mood_desc}_\n\n"
            f"[Watch on YouTube]({url})\n\n"
            f"Reply to a message with /jukebox to get a song that matches its mood."
        )
        
        await send_message(update, response, 'jukebox')
        
    except Exception as e:
        logger.error(f"Jukebox error: {e}")
        await send_message(update, 
            "🎵 *MoodyBot's Jukebox Drop*\n\n"
            "Something went wrong with the music. Try again? 🥃", 
            'jukebox'
        )

def load_system_prompt():
    with open("system_prompt.txt", "r", encoding="utf-8") as f:
        return f.read().strip()

def main():
    """Run the Telegram worker.

    One Application, one Updater, one getUpdates loop (telegram_lifecycle).
    Do not start a second poller from this process or probe updates manually.
    SIGTERM stops the updater immediately; do not sys.exit() from a signal handler.
    """
    if not TELEGRAM_BOT_TOKEN:
        print("TELEGRAM_BOT_TOKEN is not set!")
        print("Run 'python quick_setup.py' to configure your API keys.")
        return

    if not OPENROUTER_API_KEY:
        print("OPENROUTER_API_KEY is not set!")
        print("Run 'python quick_setup.py' to configure your API keys.")
        return

    print(f"Using Telegram Token: {TELEGRAM_BOT_TOKEN[:20]}...")
    print(f"Using OpenRouter Key: {OPENROUTER_API_KEY[:20]}...")

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", guard_handler(start)))
    app.add_handler(CommandHandler("validate", guard_handler(validate_command)))
    app.add_handler(CommandHandler("jukebox", guard_handler(jukebox_command)))
    app.add_handler(CommandHandler("help", guard_handler(help_command)))
    app.add_handler(MessageHandler(filters.TEXT, guard_handler(handle_message)))
    app.add_handler(CallbackQueryHandler(guard_handler(button_handler)))

    async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        err = context.error
        if err is not None and is_poller_conflict(err):
            runtime = get_runtime()
            tag = f"[{runtime.instance_id}] " if runtime is not None else ""
            logger.warning(
                "%sTelegram getUpdates conflict — another process may still be "
                "polling this bot token: %s",
                tag,
                err,
            )
            return
        logger.error(f"Exception while handling an update: {err}")
        if update and hasattr(update, "message") and update.message:
            await send_simple_message(update, "Something went wrong. Try again later.")

    app.add_error_handler(error_handler)

    runtime = PollerRuntime()
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError("closed")
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    loop.run_until_complete(runtime.run(app))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"MoodyBot crashed: {e}")


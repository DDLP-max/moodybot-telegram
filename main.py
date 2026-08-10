# -*- coding: utf-8 -*-
from flask import Flask, render_template, request, jsonify, url_for, redirect, session
import os
import threading
import time
import logging
import subprocess
import sys
from dotenv import load_dotenv

# Import database models
from models import db, User, Conversation, Message, BotConfig, BotStatistics

# Import authentication
from auth import login_required, admin_username, admin_password_hash, verify_password

# Load environment variables
load_dotenv()
print("ENV CHECK:", os.environ.get("SQLALCHEMY_DATABASE_URI"))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("SQLALCHEMY_DATABASE_URI", "sqlite:///db.sqlite3")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = os.environ.get("SESSION_SECRET", "moodybot-secret-key")

# Configure database
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle': 300,
}

# Initialize the database
db.init_app(app)

# Create tables if they don't exist
with app.app_context():
    db.create_all()
    logger.info("Database tables created or verified")

# Track bot status
bot_running = False
bot_process = None

def check_telegram_token():
    """Check if the Telegram token is available"""
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    return token is not None and token.strip() != ''

def check_openai_key():
    """Check if the OpenRouter API key is available"""
    key = os.environ.get('OPENROUTER_API_KEY')
    return key is not None and key.strip() != ''

@app.route('/')
def index():
    """Main page that displays information about the bot."""
    telegram_token_available = check_telegram_token()
    openai_key_available = check_openai_key()
    
    return render_template(
        'index.html',
        bot_running=bot_running,
        telegram_token_available=telegram_token_available,
        openai_key_available=openai_key_available
    )
    
@app.route('/stats')
def stats_page():
    """Statistics page with visualizations."""
    return render_template('statistics.html')

@app.route('/health')
def health_check():
    """Health check endpoint for the application."""
    return jsonify({
        "status": "healthy", 
        "message": "MoodyBot web interface is running",
        "bot_running": bot_running,
        "telegram_token_available": check_telegram_token(),
        "openai_key_available": check_openai_key()
    })


@app.route("/inspector", strict_slashes=False)
def inspector_home():
    """Moody Inspector — writer telemetry. Debugger, not another brain."""
    from inspector.score import aggregate_lens_stats, diff_events
    from inspector.store import get_event, load_all_events, load_events, load_hall_of_fame
    from inspector.telemetry import (
        card_summary,
        dashboard_stats,
        ensure_inspection,
        filter_events,
        hit_rate_by_month,
        sentence_teach,
        source_label,
    )

    lens_f = (request.args.get("lens") or "").strip()
    fail_f = (request.args.get("fail") or "").strip()
    tag_f = (request.args.get("tag") or "").strip()
    source_f = (request.args.get("source") or "").strip()
    since_f = (request.args.get("since") or "").strip()
    q_f = (request.args.get("q") or "").strip()
    day_f = (request.args.get("day") or "").strip() or None

    # Full corpus for dashboard / hit-rate; sidebar uses filtered recent window
    corpus = load_all_events()
    if not corpus:
        corpus = load_events(limit=500)

    hall = load_hall_of_fame(limit=2000)
    stats = dashboard_stats(corpus, hall, day=day_f)
    production = [e for e in corpus if not str(e.get("source") or "").startswith("seed")]
    hit_rate = hit_rate_by_month(production or corpus)

    filtered = filter_events(
        corpus,
        lens=lens_f,
        fail=fail_f,
        tag=tag_f,
        source=source_f,
        since=since_f,
        q=q_f,
    )
    # Default feed: highest stealability first (not "stuck on today / competent 6.0")
    sort_f = (request.args.get("sort") or "steal").strip().lower()
    if sort_f in {"steal", "stealability"}:
        filtered = sorted(
            filtered,
            key=lambda e: float(
                ((e.get("inspection") or {}).get("scores") or {}).get("stealability")
                or ((e.get("inspection") or {}).get("scores") or {}).get("memorability")
                or 0
            ),
            reverse=True,
        )
    # Sidebar: scannable window over the filtered corpus (filters still scan ALL)
    try:
        sidebar_limit = max(50, min(500, int(request.args.get("limit") or 200)))
    except ValueError:
        sidebar_limit = 200
    sidebar_events = filtered[:sidebar_limit]
    cards = [card_summary(e) for e in sidebar_events]

    selected_id = request.args.get("id")
    selected = None
    if selected_id:
        selected = next((e for e in sidebar_events if e.get("id") == selected_id), None)
        if selected is None:
            selected = get_event(selected_id)
    prev = None
    diff = None
    teach = None
    if selected:
        ensure_inspection(selected)
        for i, e in enumerate(sidebar_events):
            if e.get("id") == selected.get("id") and i + 1 < len(sidebar_events):
                prev = sidebar_events[i + 1]
                break
        if request.args.get("diff") and prev:
            diff = diff_events(prev, selected)
        sents = (selected.get("inspection") or {}).get("sentences") or []
        sent_i = request.args.get("sent")
        if sent_i is not None and str(sent_i).isdigit():
            idx = int(sent_i)
            if 0 <= idx < len(sents):
                s = sents[idx]
                teach = sentence_teach(s.get("verdict") or "ok", s.get("text") or "", s.get("note") or "")
                teach["index"] = idx
        elif sents:
            # Open on the weakest sentence so the page teaches immediately
            priority = {"mechanism_summary": 0, "ok": 1, "bridge": 2, "strong": 3, "spear": 4, "discovery": 5}
            idx = min(
                range(len(sents)),
                key=lambda i: priority.get(sents[i].get("verdict") or "ok", 9),
            )
            s = sents[idx]
            if s.get("verdict") in {"mechanism_summary", "discovery", "spear", "strong"}:
                teach = sentence_teach(s.get("verdict") or "ok", s.get("text") or "", s.get("note") or "")
                teach["index"] = idx

    filters = {
        "lens": lens_f,
        "fail": fail_f,
        "tag": tag_f,
        "source": source_f,
        "since": since_f,
        "q": q_f,
        "day": day_f or stats.get("day") or "",
    }

    return render_template(
        "inspector.html",
        events=sidebar_events,
        cards=cards,
        selected=selected,
        prev=prev,
        diff=diff,
        teach=teach,
        hall=hall,
        stats=stats,
        hit_rate=hit_rate,
        filters=filters,
        filter_count=len(filtered),
        lens_stats=aggregate_lens_stats(corpus[:400]),
        source_label=source_label,
    )


@app.route("/inspector/hall", strict_slashes=False)
def inspector_hall():
    from inspector.store import load_all_events, load_hall_of_fame
    from inspector.telemetry import hall_notebook

    hall = load_hall_of_fame(limit=5000)
    events = load_all_events()
    notebook = hall_notebook(hall, events)
    # Default to candidates — that's the 257, not the 3 manual stars
    bucket = (request.args.get("bucket") or "candidates").strip().lower()
    if bucket in {"discoveries", "starred"}:
        bucket = "starred"
    lens = (request.args.get("lens") or "").strip()
    lines = notebook["candidates"]
    if bucket == "starred":
        lines = notebook["starred"]
    elif bucket == "spears":
        lines = notebook["spears"]
    elif lens:
        lines = notebook["by_lens"].get(lens, [])
        bucket = lens
    elif bucket in notebook["by_lens"]:
        lines = notebook["by_lens"][bucket]

    return render_template(
        "inspector_hall.html",
        hall=lines,
        notebook=notebook,
        bucket=bucket,
        counts=notebook["counts"],
    )


@app.route("/inspector/star", methods=["POST"], strict_slashes=False)
def inspector_star():
    from inspector.store import star_discovery

    line = (request.form.get("line") or "").strip()
    if line:
        stars = request.form.get("stars") or "5"
        try:
            stars_i = int(stars)
        except ValueError:
            stars_i = 5
        star_discovery(
            line,
            event_id=request.form.get("event_id") or "",
            lens=request.form.get("lens") or "",
            note=request.form.get("note") or "",
            stars=stars_i,
        )
    return redirect(url_for("inspector_hall", bucket="starred"))

@app.route('/start-bot', methods=['POST'])
def start_bot():
    """Start the Telegram bot process."""
    global bot_running, bot_process
    
    if bot_running:
        return jsonify({"status": "error", "message": "Bot is already running"})
    
    if not check_telegram_token():
        return jsonify({"status": "error", "message": "Telegram bot token is missing"})
        
    if not check_openai_key():
        return jsonify({"status": "error", "message": "OpenAI API key is missing"})
    
    try:
        logger.info("Starting bot process...")
        bot_process = subprocess.Popen([sys.executable, 'run.py'])
        bot_running = True
        return jsonify({"status": "success", "message": "Bot started successfully"})
    except Exception as e:
        logger.error(f"Error starting bot: {str(e)}")
        return jsonify({"status": "error", "message": f"Failed to start bot: {str(e)}"})

@app.route('/stop-bot', methods=['POST'])
def stop_bot():
    """Stop the Telegram bot process."""
    global bot_running, bot_process
    
    if not bot_running:
        return jsonify({"status": "error", "message": "Bot is not running"})
    
    try:
        logger.info("Stopping bot process...")
        if bot_process:
            bot_process.terminate()
            bot_process.wait(timeout=5)
            bot_process = None
        bot_running = False
        return jsonify({"status": "success", "message": "Bot stopped successfully"})
    except Exception as e:
        logger.error(f"Error stopping bot: {str(e)}")
        return jsonify({"status": "error", "message": f"Failed to stop bot: {str(e)}"})

@app.route('/bot-status')
def bot_status():
    """Return the current status of the bot."""
    return jsonify({
        "running": bot_running,
        "telegram_token_available": check_telegram_token(),
        "openai_key_available": check_openai_key()
    })

@app.route('/statistics')
def statistics():
    """Get bot usage statistics."""
    try:
        # Get the latest statistics
        stats = BotStatistics.query.order_by(BotStatistics.date.desc()).first()
        
        # Get user count
        user_count = User.query.count()
        
        # Get message count
        message_count = Message.query.count()
        
        # Get conversation count
        conversation_count = Conversation.query.count()
        
        return jsonify({
            "status": "success",
            "data": {
                "total_users": user_count,
                "total_messages": message_count,
                "total_conversations": conversation_count,
                "latest_stats": stats.to_dict() if stats else None
            }
        })
    except Exception as e:
        logger.error(f"Error fetching statistics: {str(e)}")
        return jsonify({"status": "error", "message": f"Failed to fetch statistics: {str(e)}"}), 500
    
@app.route("/stats")
def stats():
    return "<p>📊 Stats page coming soon...</p>"

@app.route('/api/statistics/history')
@login_required
def statistics_history():
    """Get historical statistics data for charts."""
    try:
        # Get all statistics records ordered by date
        stats = BotStatistics.query.order_by(BotStatistics.date.asc()).all()
        
        # Convert to list of dictionaries
        stats_list = [stat.to_dict() for stat in stats]
        
        return jsonify({
            "status": "success",
            "data": stats_list
        })
    except Exception as e:
        logger.error(f"Error fetching statistics history: {str(e)}")
        return jsonify({"status": "error", "message": f"Failed to fetch statistics history: {str(e)}"}), 500

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Admin login page."""
    # If already logged in, redirect to admin panel
    if session.get('admin_logged_in'):
        return redirect(url_for('admin_panel'))
    
    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username == admin_username and verify_password(admin_password_hash, password):
            session['admin_logged_in'] = True
            next_page = request.args.get('next')
            if next_page and next_page.startswith('/'):
                return redirect(next_page)
            return redirect(url_for('admin_panel'))
        else:
            error = "Invalid username or password"
    
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    """Admin logout."""
    session.pop('admin_logged_in', None)
    return redirect(url_for('index'))

@app.route("/admin")
def admin_panel():
    return "<p>🔐 Admin panel coming soon...</p>"

@app.route('/admin/config', methods=['GET', 'POST'])
@login_required
def bot_config():
    """View and update bot configuration."""
    if request.method == 'GET':
        try:
            configs = BotConfig.query.all()
            config_dict = {config.key: config.value for config in configs}
            return jsonify({"status": "success", "data": config_dict})
        except Exception as e:
            logger.error(f"Error fetching config: {str(e)}")
            return jsonify({"status": "error", "message": f"Failed to fetch config: {str(e)}"}), 500
    
    elif request.method == 'POST':
        try:
            data = request.json
            
            for key, value in data.items():
                # Check if config already exists
                config = BotConfig.query.filter_by(key=key).first()
                
                if config:
                    config.value = value
                else:
                    new_config = BotConfig(key=key, value=value)
                    db.session.add(new_config)
            
            db.session.commit()
            return jsonify({"status": "success", "message": "Configuration updated successfully"})
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error updating config: {str(e)}")
            return jsonify({"status": "error", "message": f"Failed to update config: {str(e)}"}), 500

@app.route('/admin/reset-config', methods=['POST'])
@login_required
def reset_config():
    """Reset configuration to default values."""
    try:
        # Delete all existing configurations
        BotConfig.query.delete()
        
        # Set default configurations
        default_configs = {
            'system_prompt': """You are MoodyBot, an emotional intelligence system.
You help users see situations more accurately: feelings, patterns, power, boundaries, incentives, and next actions.
Style is secondary to insight. Inspiration sources may color voice, but never replace analysis.
Evidence and inference must stay distinct. If the user asks what to do, give a usable next move.

Be honest, precise, and useful. Prefer clarity over costume. Memorable language is allowed only when it serves judgment.
""",
            'model': 'gpt-4o',
            'temperature': '0.85',
            'max_tokens': '1000',
            'history_limit': '10',
            'enable_logging': 'true',
            'explicit_content': 'false',
        }
        
        for key, value in default_configs.items():
            new_config = BotConfig(key=key, value=value)
            db.session.add(new_config)
            
        db.session.commit()
        return jsonify({"status": "success", "message": "Configuration reset to defaults"})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error resetting config: {str(e)}")
        return jsonify({"status": "error", "message": f"Failed to reset config: {str(e)}"}), 500
        
@app.route('/admin/clear-conversations', methods=['POST'])
@login_required
def clear_conversations():
    """Clear all conversation history."""
    try:
        # Delete all messages first to avoid foreign key constraints
        Message.query.delete()
        
        # Then delete all conversations
        Conversation.query.delete()
        
        # Commit the changes
        db.session.commit()
        return jsonify({"status": "success", "message": "All conversations cleared successfully"})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error clearing conversations: {str(e)}")
        return jsonify({"status": "error", "message": f"Failed to clear conversations: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
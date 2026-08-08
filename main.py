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
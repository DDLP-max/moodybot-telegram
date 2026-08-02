# -*- coding: utf-8 -*-
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

# Initialize SQLAlchemy
db = SQLAlchemy()

class User(db.Model):
    """Model for Telegram users interacting with the bot"""
    __tablename__ = 'users'
    
    # Telegram user ID as primary key
    id = db.Column(db.BigInteger, primary_key=True)
    username = db.Column(db.String(255), nullable=True)
    first_name = db.Column(db.String(255), nullable=True)
    last_name = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_interaction = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship with conversations
    conversations = db.relationship('Conversation', backref='user', lazy=True)
    
    def __repr__(self):
        return f'<User {self.id} {self.username}>'

class Conversation(db.Model):
    """Model for storing conversation history"""
    __tablename__ = 'conversations'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.BigInteger, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship with messages
    messages = db.relationship('Message', backref='conversation', lazy=True, cascade="all, delete-orphan")
    
    def __repr__(self):
        return f'<Conversation {self.id} for User {self.user_id}>'

class Message(db.Model):
    """Model for storing individual messages in a conversation"""
    __tablename__ = 'messages'
    
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversations.id'), nullable=False)
    role = db.Column(db.String(50), nullable=False)  # 'user' or 'assistant'
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Message {self.id} {self.role} in Conversation {self.conversation_id}>'

class BotConfig(db.Model):
    """Model for storing bot configuration"""
    __tablename__ = 'bot_config'
    
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(255), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<BotConfig {self.key}>'

class UserMood(db.Model):
    """Model for tracking user's emotional state and context over time"""
    __tablename__ = 'user_moods'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.BigInteger, db.ForeignKey('users.id'), nullable=False)
    mood = db.Column(db.String(50), nullable=True)  # e.g., 'anxious', 'hopeful', 'angry'
    topic = db.Column(db.String(100), nullable=True)  # e.g., 'dating', 'work', 'family'
    context = db.Column(db.Text, nullable=True)  # Additional context about their situation
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship with users
    user = db.relationship('User', backref=db.backref('moods', lazy=True, order_by='UserMood.created_at.desc()'))
    
    def __repr__(self):
        return f'<UserMood {self.id} {self.mood} for User {self.user_id}>'
        
    def to_dict(self):
        """Convert model to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'mood': self.mood,
            'topic': self.topic,
            'context': self.context,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class BotStatistics(db.Model):
    """Model for tracking bot usage statistics"""
    __tablename__ = 'bot_statistics'
    
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, default=datetime.utcnow().date, nullable=False)
    message_count = db.Column(db.Integer, default=0)
    user_count = db.Column(db.Integer, default=0)
    response_time_avg = db.Column(db.Float, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<BotStatistics {self.date}>'
        
    def to_dict(self):
        """Convert model to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'date': self.date.isoformat() if self.date else None,
            'message_count': self.message_count,
            'user_count': self.user_count,
            'response_time_avg': self.response_time_avg,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
# -*- coding: utf-8 -*-
from models import db, BotConfig

def get_config_value(key, default=None):
    """
    Get a configuration value from the database.
    If not found, return the default value.
    """
    try:
        config = BotConfig.query.filter_by(key=key).first()
        return config.value if config else default
    except Exception as e:
        print(f"Error getting config value: {str(e)}")
        return default

def get_all_config():
    """
    Get all configuration values as a dictionary.
    """
    try:
        configs = BotConfig.query.all()
        return {config.key: config.value for config in configs}
    except Exception as e:
        print(f"Error getting all config values: {str(e)}")
        return {}

def set_config_value(key, value):
    """
    Set a configuration value in the database.
    If the key already exists, update the value.
    If the key doesn't exist, create a new entry.
    """
    try:
        config = BotConfig.query.filter_by(key=key).first()
        if config:
            config.value = value
        else:
            config = BotConfig(key=key, value=value)
            db.session.add(config)
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        print(f"Error setting config value: {str(e)}")
        return False
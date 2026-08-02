# -*- coding: utf-8 -*-
from functools import wraps
from flask import request, redirect, url_for, flash, session
import os
import hashlib
import secrets
import string

# Admin authentication implementation
# This is a simple implementation - in a production app, use Flask-Login

# Default admin credentials (can be overridden in .env)
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "moodybot"

def generate_password_hash(password, salt=None):
    """Generate a salted password hash."""
    if not salt:
        # Generate a random salt
        salt = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(16))
    
    # Encode password and salt
    password_bytes = password.encode('utf-8')
    salt_bytes = salt.encode('utf-8')
    
    # Create hash
    hash_obj = hashlib.sha256(salt_bytes + password_bytes)
    password_hash = hash_obj.hexdigest()
    
    # Return the salt and hash separated by a colon
    return f"{salt}:{password_hash}"

def verify_password(stored_hash, provided_password):
    """Verify a password against a stored hash."""
    try:
        # Split the stored hash into salt and hash
        salt, stored_password_hash = stored_hash.split(':', 1)
        
        # Generate a hash of the provided password with the same salt
        provided_password_bytes = provided_password.encode('utf-8')
        salt_bytes = salt.encode('utf-8')
        hash_obj = hashlib.sha256(salt_bytes + provided_password_bytes)
        provided_password_hash = hash_obj.hexdigest()
        
        # Compare the hashes
        return provided_password_hash == stored_password_hash
    except Exception:
        return False

def get_admin_credentials():
    """Get admin credentials from environment variables or use defaults."""
    username = os.environ.get('ADMIN_USERNAME', DEFAULT_ADMIN_USERNAME)
    
    # Check if we have a stored password hash
    stored_hash = os.environ.get('ADMIN_PASSWORD_HASH')
    if stored_hash:
        # We have a stored hash, use it
        password_hash = stored_hash
    else:
        # No stored hash, use the default password or the one from env
        password = os.environ.get('ADMIN_PASSWORD', DEFAULT_ADMIN_PASSWORD)
        password_hash = generate_password_hash(password)
    
    return username, password_hash

def login_required(f):
    """Decorator to protect routes with admin login."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

# Initialize admin credentials
admin_username, admin_password_hash = get_admin_credentials()
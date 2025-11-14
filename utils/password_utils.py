"""Utility functions for password management."""
import secrets
import time

def generate_reset_token():
    """Generate a secure random token for password reset."""
    return secrets.token_urlsafe(32)

def get_token_expiry(hours=24):
    """Get expiry timestamp for a token (default 24 hours from now)."""
    return int(time.time()) + (hours * 3600)

def is_token_valid(token_expiry):
    """Check if a token is still valid (not expired)."""
    if token_expiry is None:
        return False
    return int(time.time()) < token_expiry

def get_reset_token_expiry_hours(token_expiry):
    """Get how many hours until token expires."""
    if token_expiry is None:
        return 0
    hours_remaining = (token_expiry - int(time.time())) / 3600
    return max(0, hours_remaining)










# List of inappropriate words/slugs that should not be allowed
# This is a basic list - you can expand it as needed

PROFANITY_LIST = {
    # System reserved words
    'admin', 'superadmin', 'api', 'static', 'login', 'logout', 'register',
    'settings', 'config', 'system', 'wizard', 'setup', 'install',
    
    # Common inappropriate words (keeping it minimal and professional)
    'test', 'demo', 'example', 'null', 'undefined', 'root', 'user',
    
    # Add more as needed
}

def is_slug_appropriate(slug):
    """
    Check if a slug is appropriate and not in the profanity/reserved list.
    
    Args:
        slug (str): The slug to check
        
    Returns:
        tuple: (is_valid, message)
    """
    slug_lower = slug.lower()
    
    if slug_lower in PROFANITY_LIST:
        return False, "This URL is reserved or not available"
    
    return True, "URL is available"


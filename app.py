import logging
import os
import sys
import sqlite3
import time
from flask import Flask, request, jsonify, session, render_template, render_template_string, send_file, redirect, url_for, g, flash, Response
from superadmin_routes import superadmin
from flask_babel import Babel, format_datetime
import threading
import requests
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from flask_babel import gettext as _
import re  
import subprocess
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash
from spotipy import Spotify
from spotipy.oauth2 import SpotifyClientCredentials
from flask_mail import Mail
from dotenv import load_dotenv
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
# Read SECRET_KEY from environment variable for security
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')

# Configure session to persist across browser tabs/closing
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)  # Session expires after 7 days
app.config['SESSION_COOKIE_HTTPONLY'] = True  # Prevent XSS attacks
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('FLASK_ENV') == 'production'  # HTTPS only in production
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # Allow cookies when navigating from external sites

# Configure Rate Limiting
# Note: Read-only GET endpoints are exempted individually
# Default limits apply only to POST/PUT/DELETE endpoints that modify data
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["10000 per day", "2000 per hour"],  # Very high limits - most GET endpoints are exempted
    storage_uri="memory://",
    strategy="fixed-window"
)

# Exempt static files and all GET requests from rate limiting
# GET requests are read-only and should not be rate limited
@limiter.request_filter
def exempt_static_files_and_get():
    # Exempt static files
    if request.path.startswith('/static/'):
        return True
    # Exempt all GET requests (read-only operations)
    if request.method == 'GET':
        return True
    return False

# Rate Limit Error Handler
@app.errorhandler(429)
def ratelimit_handler(e):
    """Handle rate limit exceeded errors."""
    if request.path.startswith('/api/') or request.is_json:
        return jsonify({
            'error': 'Rate limit exceeded',
            'message': 'Too many requests. Please try again later.',
            'retry_after': e.description
        }), 429
    
    # For regular web requests, show a friendly page
    return render_template_string('''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Too Many Requests</title>
            <style>
                body { font-family: Arial, sans-serif; text-align: center; padding: 50px; background: #f5f5f5; }
                .container { background: white; padding: 40px; border-radius: 10px; max-width: 500px; margin: 0 auto; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
                h1 { color: #e74c3c; margin-bottom: 20px; }
                p { color: #666; line-height: 1.6; }
                .retry { color: #3498db; font-weight: bold; margin-top: 20px; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>⏱️ Too Many Requests</h1>
                <p>You've made too many requests in a short period. Please wait a moment before trying again.</p>
                <p class="retry">{{ retry_after }}</p>
                <p><a href="javascript:history.back()">← Go Back</a></p>
            </div>
        </body>
        </html>
    ''', retry_after=e.description), 429

# Global dictionary to track background jobs
background_jobs = {}

# Flask-Mail configuration
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', 'on', '1']
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@setly.app')

# Initialize Flask-Mail
mail = Mail(app)

# Register the superadmin blueprint
app.register_blueprint(superadmin)


# Spotify API credentials - read from environment variables for security
# Set these in .env file: SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET
client_id = os.environ.get('SPOTIFY_CLIENT_ID')
client_secret = os.environ.get('SPOTIFY_CLIENT_SECRET')

if not client_id or not client_secret:
    app.logger.error("SPOTIFY_CLIENT_ID or SPOTIFY_CLIENT_SECRET not set in environment variables")
    app.logger.error("Spotify integration will not work. Please set these in your .env file.")


babel = Babel(app)

# Context processor to make app_name available to all templates
def get_system_setting(key, default=None, value_type=str):
    """Get a system setting from the database."""
    try:
        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM system_settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            value = row['value']
            if value_type == int:
                return int(value)
            elif value_type == float:
                return float(value)
            elif value_type == bool:
                return value.lower() in ('true', '1', 'yes')
            return value
        return default
    except Exception as e:
        app.logger.error(f"Error getting system setting {key}: {e}")
        return default

@app.context_processor
def inject_app_settings():
    """Inject app-wide settings into all templates."""
    conn = create_connection()
    cursor = conn.cursor()
    
    # Get all relevant settings
    cursor.execute("SELECT key, value FROM system_settings WHERE key IN ('app_name', 'favicon', 'app_icon', 'auto_refresh_interval')")
    rows = cursor.fetchall()
    
    settings = {row['key']: row['value'] for row in rows}
    app_name = settings.get('app_name', 'Setly')
    favicon = settings.get('favicon', 'favicon.ico')
    app_icon = settings.get('app_icon', 'app-icon.png')
    auto_refresh_interval = int(settings.get('auto_refresh_interval', '30'))
    
    conn.close()
    return dict(app_name=app_name, favicon=favicon, app_icon=app_icon, auto_refresh_interval=auto_refresh_interval)

# Read ADMIN_PASSWORD from environment variable for security
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'change-this-password')
MAX_TIME_TO_REQUEST = 12

app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'static', 'author_images')
# Base directory for all tenant data
app.config['TENANTS_BASE_DIR'] = os.path.join(os.path.dirname(__file__), 'static', 'tenants')

# For backwards compatibility
app.config['TENANT_LOGOS_FOLDER'] = app.config['TENANTS_BASE_DIR']


# Default venue name
venue_name = "Sergio Chiappa Live"

# Set supported languages
app.config['BABEL_DEFAULT_LOCALE'] = 'it'
app.config['LANGUAGES'] = {
    'en': 'English',
    'it': 'Italian',
    'es': 'Spanish',
    'de': 'German',
    'fr': 'French'
}

# Configure logging at the start of the application
log_filename = os.path.join(os.path.dirname(__file__), 'app.log')
logging.basicConfig(level=logging.DEBUG, filename=log_filename, filemode='w',
                    format='%(name)s - %(levelname)s - %(message)s')

# Ensure logs are flushed immediately
logging.shutdown()

# Initialize SQLAlchemy
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///songs.db'
db = SQLAlchemy(app)


def get_locale():
    return session.get('language', request.accept_languages.best_match(app.config['LANGUAGES'].keys()))

babel.init_app(app, locale_selector=get_locale)

#--------------------------------------------- ADMIN Entry Points ---------------------------------------------
@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per 15 minutes", methods=['POST'])
def login():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == ADMIN_PASSWORD:
            session['is_admin'] = True
            return redirect(url_for('songs'))
        else:
            flash(_('Incorrect password. Please try again.'), 'error')
            return redirect(url_for('login'))
    
    tenant = None
    if session.get('tenant_id'):
        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM tenants WHERE id = ?', (session.get('tenant_id'),))
        tenant = cursor.fetchone()
        conn.close()
    return render_template('login.html', tenant=tenant)

@app.route('/songs')
def songs():
    if not session.get('is_admin'):
        return redirect(url_for('login'))
    return render_template('songs.html')

@app.route('/queue', methods=['GET', 'POST'])
def queue():
    if not session.get('is_admin'):
        return redirect(url_for('login'))
    return render_queue()
    return render_template('queue.html')

@app.route('/admin')
def admin():
    if not session.get('is_admin'):
        return redirect(url_for('login'))
    return render_template('admin.html')

@app.route('/logout')
def logout():
    session.pop('is_admin', None)
    return redirect(url_for('login'))

def render_queue():
    is_admin = session.get('is_admin', False)  # Default to False if not set
    current_datetime = format_datetime(datetime.now())
    tenant_id = session.get('tenant_id')
    
    # Get tenant info if tenant_id is available
    tenant = None
    if tenant_id:
        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM tenants WHERE id = ? AND active = 1', (tenant_id,))
        tenant = cursor.fetchone()
        conn.close()
    
    venue_name = get_venue_name(tenant_id)
    max_requests = get_setting('max_requests_per_user', tenant_id)
    
    # Get active gig info
    active_gig = get_active_gig(tenant_id)
    
    return render_template('queue.html', is_admin=is_admin, current_datetime=current_datetime, venue_name=venue_name, max_requests=max_requests, tenant=tenant, active_gig=active_gig)


#--------------------------------------------- Gig Management Functions ---------------------------------------------

def get_active_gig(tenant_id):
    """Get the currently active gig for a tenant, if any."""
    if not tenant_id:
        return None
    
    conn = create_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT * FROM gigs 
            WHERE tenant_id = ? AND is_active = 1 
            ORDER BY start_time DESC 
            LIMIT 1
        """, (tenant_id,))
        gig = cursor.fetchone()
        return dict(gig) if gig else None
    except sqlite3.OperationalError:
        # Table doesn't exist yet - return None (gig system not initialized)
        return None
    finally:
        conn.close()

def has_active_gig(tenant_id):
    """Check if a tenant has an active gig."""
    return get_active_gig(tenant_id) is not None

def start_gig(tenant_id, gig_name=None, tip_enabled=True):
    """Start a new gig for a tenant. Returns the gig ID if successful, None otherwise."""
    if not tenant_id:
        return None
    
    conn = create_connection()
    cursor = conn.cursor()
    try:
        # First, end any existing active gigs for this tenant
        cursor.execute("""
            UPDATE gigs 
            SET is_active = 0, end_time = CURRENT_TIMESTAMP 
            WHERE tenant_id = ? AND is_active = 1
        """, (tenant_id,))
        
        # Check if tip_enabled column exists, if not add it
        try:
            cursor.execute("PRAGMA table_info(gigs)")
            columns = [col[1] for col in cursor.fetchall()]
            if 'tip_enabled' not in columns:
                cursor.execute("ALTER TABLE gigs ADD COLUMN tip_enabled INTEGER DEFAULT 1")
                conn.commit()
                app.logger.info("Added tip_enabled column to gigs table")
        except sqlite3.OperationalError as e:
            app.logger.warning(f"Could not check/add tip_enabled column: {e}")
        
        # Create new active gig
        tip_enabled_int = 1 if tip_enabled else 0
        try:
            if gig_name:
                cursor.execute("""
                    INSERT INTO gigs (tenant_id, name, start_time, is_active, tip_enabled)
                    VALUES (?, ?, CURRENT_TIMESTAMP, 1, ?)
                """, (tenant_id, gig_name, tip_enabled_int))
            else:
                # Generate default name from timestamp
                default_name = f"Gig {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                cursor.execute("""
                    INSERT INTO gigs (tenant_id, name, start_time, is_active, tip_enabled)
                    VALUES (?, ?, CURRENT_TIMESTAMP, 1, ?)
                """, (tenant_id, default_name, tip_enabled_int))
        except sqlite3.OperationalError as e:
            # If tip_enabled column still doesn't exist, try without it
            if 'tip_enabled' in str(e).lower():
                app.logger.warning(f"tip_enabled column issue, trying without it: {e}")
                if gig_name:
                    cursor.execute("""
                        INSERT INTO gigs (tenant_id, name, start_time, is_active)
                        VALUES (?, ?, CURRENT_TIMESTAMP, 1)
                    """, (tenant_id, gig_name))
                else:
                    default_name = f"Gig {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                    cursor.execute("""
                        INSERT INTO gigs (tenant_id, name, start_time, is_active)
                        VALUES (?, ?, CURRENT_TIMESTAMP, 1)
                    """, (tenant_id, default_name))
            else:
                raise
        
        gig_id = cursor.lastrowid
        conn.commit()
        return gig_id
    except sqlite3.OperationalError as e:
        # Table doesn't exist yet
        app.logger.error(f"Gigs table error: {e}")
        return None
    except Exception as e:
        app.logger.error(f"Error starting gig: {e}")
        conn.rollback()
        return None
    finally:
        conn.close()

def end_gig(tenant_id):
    """End the currently active gig for a tenant. Returns True if successful."""
    if not tenant_id:
        return False
    
    conn = create_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE gigs 
            SET is_active = 0, end_time = CURRENT_TIMESTAMP 
            WHERE tenant_id = ? AND is_active = 1
        """, (tenant_id,))
        conn.commit()
        return cursor.rowcount > 0
    except sqlite3.OperationalError:
        # Table doesn't exist yet
        return False
    except Exception as e:
        app.logger.error(f"Error ending gig: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


#--------------------------------------------- Utility functions to inspect the database table ---------------------------------------------


# SECURITY: /fetch_table endpoint REMOVED
# This endpoint had no authentication and was vulnerable to SQL injection.
# It allowed anyone to dump any table from the database.
# If debugging is needed, use superadmin-only routes with proper auth and input validation.

@app.route('/generate_pdf')
def generate_pdf():
    try:
        # Change the working directory to the correct path
        script_dir = os.path.join(os.path.dirname(__file__))
        script_path = os.path.join(script_dir, "generate_pdf.py")
        
        # Call the Python script to generate the PDF using the same Python interpreter
        result = subprocess.run([sys.executable, script_path], check=True, capture_output=True, text=True, cwd=script_dir)
        
        # Log the output and error messages
        app.logger.debug(f"generate_pdf.py output: {result.stdout}")
        app.logger.debug(f"generate_pdf.py error: {result.stderr}")
        
        # Define the absolute path to the PDF file
        pdf_path = os.path.join(script_dir, "Sergio Chiappa Repertorio.pdf")
        
        # Check if the file exists
        if not os.path.exists(pdf_path):
            app.logger.error(f"File not found: {pdf_path}")
            return jsonify({'error': 'File not found'}), 404
        
        # Serve the generated PDF file
        return send_file(pdf_path, as_attachment=True, download_name="Sergio Chiappa Songs.pdf")
    except subprocess.CalledProcessError as e:
        app.logger.error(f"Error generating PDF: {e}")
        app.logger.error(f"generate_pdf.py output: {e.stdout}")
        app.logger.error(f"generate_pdf.py error: {e.stderr}")
        return jsonify({'error': 'Error generating PDF'}), 500
    except Exception as e:
        app.logger.error(f"Unexpected error: {e}")
        return jsonify({'error': 'Unexpected error occurred'}), 500

@app.route('/<tenant_slug>/print_qr')
def tenant_print_qr(tenant_slug):
    """Display a printable QR code for the tenant."""
    # Get language from query parameter
    lang = request.args.get('lang')
    if lang and lang in ['it', 'en', 'fr', 'de', 'es']:
        session['language'] = lang
        g.lang_code = lang
    
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM tenants WHERE slug = ? AND active = 1', (tenant_slug,))
    tenant = cursor.fetchone()
    conn.close()
    
    if not tenant:
        return "Tenant not found", 404
    
    # Get app URL from settings
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM system_settings WHERE key = 'app_url'")
    result = cursor.fetchone()
    base_url = result['value'] if result else request.host_url.rstrip('/')
    conn.close()
    
    qr_url = f"{base_url}/{tenant_slug}"
    
    return render_template('print_qr.html', tenant=tenant, qr_url=qr_url)

@app.route('/<tenant_slug>/generate_pdf')
def tenant_generate_pdf(tenant_slug):
    try:
        # Get tenant info
        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id, name FROM tenants WHERE slug = ?', (tenant_slug,))
        tenant = cursor.fetchone()
        
        if not tenant:
            conn.close()
            return jsonify({'error': 'Tenant not found'}), 404
        
        tenant_id = tenant['id']
        tenant_name = tenant['name']
        conn.close()
        
        # Change the working directory to the correct path
        script_dir = os.path.join(os.path.dirname(__file__))
        script_path = os.path.join(script_dir, "generate_pdf.py")
        
        # Find the correct Python interpreter
        # On PythonAnywhere/WSGI, sys.executable might point to uwsgi, not python
        python_executable = sys.executable
        if 'uwsgi' in python_executable.lower() or not python_executable.endswith(('python', 'python3')):
            # Try to find python from virtualenv first
            venv_python = os.path.join(os.path.dirname(sys.executable), 'python3')
            if os.path.exists(venv_python):
                python_executable = venv_python
            else:
                # Fallback to system python3
                python_executable = 'python3'
        
        # Call the Python script to generate the PDF with tenant_id
        app.logger.info(f"Using Python executable: {python_executable}")
        result = subprocess.run(
            [python_executable, script_path, str(tenant_id)], 
            check=True, 
            capture_output=True, 
            text=True, 
            cwd=script_dir
        )
        
        # Log the output and error messages
        app.logger.debug(f"generate_pdf.py output: {result.stdout}")
        app.logger.debug(f"generate_pdf.py error: {result.stderr}")
        
        # Define the absolute path to the PDF file
        pdf_path = os.path.join(script_dir, f"{tenant_name} Repertorio.pdf")
        
        # Check if the file exists
        if not os.path.exists(pdf_path):
            app.logger.error(f"File not found: {pdf_path}")
            return jsonify({'error': 'File not found'}), 404
        
        # Serve the generated PDF file
        return send_file(pdf_path, as_attachment=True, download_name=f"{tenant_name} Songs.pdf")
    except subprocess.CalledProcessError as e:
        app.logger.error(f"Error generating PDF: {e}")
        app.logger.error(f"generate_pdf.py output: {e.stdout}")
        app.logger.error(f"generate_pdf.py error: {e.stderr}")
        return jsonify({'error': 'Error generating PDF'}), 500
    except Exception as e:
        app.logger.error(f"Unexpected error: {e}")
        return jsonify({'error': 'Unexpected error occurred'}), 500
 
@app.route('/generate_pdf_old')
def generate_pdf_old() :
    # Call the Python script to generate the PDF
    subprocess.run(["python", "generate_pdf.py"])
    
    # Serve the generated PDF file
    return send_file("Sergio Chiappa Repertorio.pdf", as_attachment=True, download_name="Sergio Chiappa Songs.pdf")


#--------------------------------------------- Spotify  functions  ---------------------------------------------
def get_spotify_image(author_name):
    """
    Get Spotify artist image URL, genre, and language.
    Returns a dict with 'image_url', 'genre', and 'language', or None if not found.
    """
    # Check if credentials are available
    if not client_id or not client_secret:
        app.logger.error("Cannot fetch Spotify data: credentials not configured")
        return None
    
    try:
        # Set timeout for Spotify API calls
        # Note: Cache warnings are expected on PythonAnywhere and can be ignored
        # Spotify API will still work without cache, just slightly slower
        # PythonAnywhere has a 30-second limit, so use shorter timeout
        # Set timeout for Spotify API calls - use values that worked before
        timeout = 20  # Standard timeout
        retries = 2  # Standard retries
        
        sp = Spotify(
            auth_manager=SpotifyClientCredentials(
                client_id=client_id, 
                client_secret=client_secret
            ),
            requests_timeout=timeout,
            retries=retries
        )
        results = sp.search(q=author_name, type="artist", limit=1)
        items = results.get("artists", {}).get("items", [])
    except Exception as e:
        error_str = str(e).lower()
        
        # Check for rate limiting (429) or quota exceeded
        if '429' in error_str or 'too many requests' in error_str or 'rate limit' in error_str:
            app.logger.warning(f"Spotify API rate limit hit for '{author_name}': {str(e)}")
            return {'rate_limited': True}
        
        # Check for authentication errors (401, 403)
        if '401' in error_str or '403' in error_str or 'unauthorized' in error_str or 'forbidden' in error_str:
            app.logger.error(f"Spotify API authentication error for '{author_name}': {str(e)}")
            return None
        
        # Other errors
        app.logger.error(f"Spotify API error for '{author_name}': {str(e)}")
        return None

    if items:
        artist_data = items[0]
        images = artist_data.get("images", [])
        genres = artist_data.get("genres", [])
        
        app.logger.info(f"Spotify artist '{author_name}': Found {len(genres)} genres: {genres}")
        
        image_url = images[0]["url"] if images else None
        genre = genres[0] if genres else None
        
        app.logger.info(f"Selected genre for '{author_name}': {genre}")
        
        # Infer language from genre only (removed top_tracks call to avoid timeout)
        # The artist_top_tracks() call was causing timeouts on PythonAnywhere
        language = None
        genre_lower = genre.lower() if genre else ''
        
        try:
            # Check genre for language hints (faster, no additional API call)
            if 'italian' in genre_lower or 'italiano' in genre_lower:
                language = 'it'
                app.logger.info(f"Language detected from genre: {language}")
            elif 'spanish' in genre_lower or 'latin' in genre_lower or 'latino' in genre_lower:
                language = 'es'
                app.logger.info(f"Language detected from genre: {language}")
            elif 'german' in genre_lower or 'deutsch' in genre_lower:
                language = 'de'
                app.logger.info(f"Language detected from genre: {language}")
            elif 'french' in genre_lower or 'chanson' in genre_lower:
                language = 'fr'
                app.logger.info(f"Language detected from genre: {language}")
            else:
                # Default to English if no genre hint
                language = 'en'
                app.logger.info(f"No language detected from genre, defaulting to: {language}")
        except Exception as e:
            app.logger.error(f"Error inferring language: {e}")
            language = 'en'  # Default to English on error
        
        result = {
            'image_url': image_url,
            'genre': genre,
            'language': language
        }
        app.logger.info(f"Returning data for '{author_name}': {result}")
        return result
    
    app.logger.warning(f"No artist found on Spotify for: {author_name}")
    return None

def normalize_artist_filename(artist_name):
    """
    Normalize artist name to a safe filename.
    Handles special characters, multiple artists, abbreviations, etc.
    """
    if not artist_name:
        return "unknown_artist"
    
    # Convert to lowercase
    normalized = artist_name.lower().strip()
    
    # Replace common separators with underscore
    # Handle "/", ",", "&", "feat.", "featuring", etc.
    normalized = normalized.replace('/', ' ')
    normalized = normalized.replace(',', ' ')
    normalized = normalized.replace('&', ' ')
    normalized = normalized.replace('feat.', ' ')
    normalized = normalized.replace('featuring', ' ')
    normalized = normalized.replace('ft.', ' ')
    normalized = normalized.replace('with', ' ')
    
    # Replace multiple spaces/underscores with single underscore
    normalized = re.sub(r'[\s_]+', '_', normalized)
    
    # Remove trailing underscores
    normalized = normalized.strip('_')
    
    # Remove special characters except underscore, dash, and alphanumeric
    normalized = re.sub(r'[^a-z0-9_-]', '', normalized)
    
    # Collapse multiple underscores to single underscore
    normalized = re.sub(r'_+', '_', normalized)
    
    # If empty after normalization, use default
    if not normalized:
        normalized = "unknown_artist"
    
    return normalized

def download_image(url, filename, tenant_slug=None):
    """Download image from URL and save to tenant-specific or shared directory."""
    from utils.tenant_utils import get_tenant_dir
    
    if not url or not filename:
        app.logger.error(f"Invalid parameters: url={url}, filename={filename}")
        return None
    
    try:
        # Add timeout and disable SSL verification if needed (for compatibility)
        # PythonAnywhere has stricter limits, use shorter timeout
        is_pythonanywhere = (
            'pythonanywhere.com' in os.environ.get('PYTHONANYWHERE_DOMAIN', '') or
            'pythonanywhere' in os.environ.get('HOME', '').lower() or
            os.path.exists('/var/www/.pythonanywhere_com')
        )
        timeout = 8 if is_pythonanywhere else 15  # Shorter timeout on PythonAnywhere
        response = requests.get(url, stream=True, timeout=timeout, verify=True)
        if response.status_code == 200:
            try:
                safe_filename = secure_filename(filename)
                
                # Use tenant-specific directory if tenant_slug is provided
                try:
                    if tenant_slug:
                        image_dir = get_tenant_dir(app, tenant_slug, 'author_images')
                    else:
                        image_dir = app.config.get('UPLOAD_FOLDER', 'static/uploads')
                except Exception as dir_error:
                    app.logger.error(f"Error getting image directory: {dir_error}")
                    # Fallback to default directory
                    image_dir = app.config.get('UPLOAD_FOLDER', 'static/uploads')
                
                # Ensure directory exists
                os.makedirs(image_dir, exist_ok=True)
                
                filepath = os.path.join(image_dir, safe_filename)
                with open(filepath, 'wb') as f:
                    for chunk in response.iter_content(1024):
                        if chunk:  # Filter out keep-alive chunks
                            f.write(chunk)
                return safe_filename
            except (OSError, IOError) as file_error:
                app.logger.error(f"Error saving image file: {file_error}")
                return None
    except requests.exceptions.SSLError as e:
        app.logger.error(f"SSL Error downloading image from {url}: {e}")
        # Try again without SSL verification as fallback
        try:
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            timeout = 15  # Standard timeout that worked before
            response = requests.get(url, stream=True, timeout=timeout, verify=False)
            if response.status_code == 200:
                try:
                    safe_filename = secure_filename(filename)
                    try:
                        if tenant_slug:
                            image_dir = get_tenant_dir(app, tenant_slug, 'author_images')
                        else:
                            image_dir = app.config.get('UPLOAD_FOLDER', 'static/uploads')
                    except Exception as dir_error:
                        app.logger.error(f"Error getting image directory (fallback): {dir_error}")
                        image_dir = app.config.get('UPLOAD_FOLDER', 'static/uploads')
                    
                    os.makedirs(image_dir, exist_ok=True)
                    
                    filepath = os.path.join(image_dir, safe_filename)
                    with open(filepath, 'wb') as f:
                        for chunk in response.iter_content(1024):
                            if chunk:
                                f.write(chunk)
                    return safe_filename
                except (OSError, IOError) as file_error:
                    app.logger.error(f"Error saving image file (fallback): {file_error}")
                    return None
        except Exception as fallback_error:
            app.logger.error(f"Fallback download also failed: {fallback_error}", exc_info=True)
            return None
    except requests.exceptions.Timeout as e:
        app.logger.error(f"Timeout downloading image from {url}: {e}")
        return None
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Error downloading image from {url}: {e}")
        return None
    except Exception as e:
        app.logger.error(f"Unexpected error downloading image: {e}", exc_info=True)
        return None
    
    return None

@app.route('/fetch_spotify_image', methods=['POST'])
@limiter.limit("10 per minute")  # Limit to 10 requests per minute per IP
def fetch_spotify_image():
    """Fetch image from Spotify (legacy route)."""
    try:
        author = request.form.get('author')
        if not author:
            return jsonify({'message': 'Author name is required'}), 400

        # Check if Spotify credentials are configured
        if not client_id or not client_secret:
            app.logger.error("Spotify credentials not configured")
            return jsonify({'message': 'Spotify integration not configured. Please contact the administrator.'}), 500

        # Get tenant_slug from session if available
        tenant_slug = session.get('tenant_slug')
        
        # If tenant_slug is not in session, try to get it from the request URL or form
        if not tenant_slug:
            # Try to extract from referrer or form data
            referrer = request.headers.get('Referer', '')
            if '/vittorio/' in referrer:
                tenant_slug = 'vittorio'
            elif '/roberto/' in referrer:
                tenant_slug = 'roberto'
            else:
                # Try to get from form data
                tenant_slug = request.form.get('tenant_slug')
        
        app.logger.info(f"Fetching Spotify data for: {author}, tenant_slug: {tenant_slug}")
        
        try:
            artist_data = get_spotify_image(author)
        except Exception as spotify_error:
            app.logger.error(f"Error calling get_spotify_image for '{author}': {spotify_error}", exc_info=True)
            return jsonify({'message': 'Spotify API error. Please try again later.'}), 500
        
        if artist_data is None:
            app.logger.warning(f"No Spotify data returned for: {author}")
            return jsonify({'message': 'Spotify API timeout or error. Please check your internet connection and try again.'}), 408
        
        # Check for rate limiting
        if artist_data and artist_data.get('rate_limited'):
            app.logger.warning(f"Spotify API rate limited for: {author}")
            return jsonify({'message': 'Spotify API rate limit reached. Please wait a moment and try again.'}), 429
            
        if artist_data and artist_data.get('image_url'):
            # Normalize filename: lowercase, replace spaces with underscores
            try:
                normalized_author = author.lower().replace(' ', '_')
                filename = f"{normalized_author}.jpg"
                saved_filename = download_image(artist_data['image_url'], filename, tenant_slug)
            except Exception as download_error:
                app.logger.error(f"Error downloading image for '{author}': {download_error}", exc_info=True)
                return jsonify({'message': 'Failed to download image. Please try again.'}), 500
            
            if saved_filename:
                try:
                    response_data = {
                        'message': 'Image fetched successfully', 
                        'image': saved_filename
                    }
                    if artist_data.get('genre'):
                        response_data['genre'] = artist_data['genre']
                        app.logger.info(f"Adding genre to response: {artist_data['genre']}")
                    else:
                        app.logger.warning(f"No genre found in artist_data for: {author}")
                        
                    if artist_data.get('language'):
                        response_data['language'] = artist_data['language']
                        app.logger.info(f"Adding language to response: {artist_data['language']}")
                    else:
                        app.logger.warning(f"No language found in artist_data for: {author}")
                    
                    app.logger.info(f"Final response data: {response_data}")
                    return jsonify(response_data), 200
                except Exception as response_error:
                    app.logger.error(f"Error building response for '{author}': {response_error}", exc_info=True)
                    return jsonify({'message': 'Error processing response. Please try again.'}), 500
            else:
                return jsonify({'message': 'Failed to download image due to SSL/connection error. Image URL found but download failed.'}), 500
        return jsonify({'message': 'Artist not found on Spotify. Check the spelling or try a different name.'}), 404
    except TimeoutError:
        app.logger.error(f"Request timeout for '{author}' on PythonAnywhere")
        return jsonify({'message': 'Request timeout. Please try again with a shorter artist name or try again later.'}), 408
    except Exception as e:
        app.logger.error(f"Unexpected error in fetch_spotify_image: {e}", exc_info=True)
        import traceback
        app.logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({'message': f'Unexpected error: {str(e)}'}), 500
    finally:
        # Always cancel timeout (if signal module is available)
        try:
            import signal
            if hasattr(signal, 'SIGALRM'):
                try:
                    signal.alarm(0)
                except:
                    pass
        except ImportError:
            # signal module not available on all platforms (e.g., Windows)
            pass

def process_bulk_fetch_job(job_id, tenant_id, tenant_slug, batch_size):
    """Background worker function to process bulk Spotify fetch."""
    import time
    import json
    
    def update_job_status(job_id, **kwargs):
        """Helper to update job status in database."""
        try:
            conn = create_connection()
            cursor = conn.cursor()
            
            updates = []
            params = []
            for key, value in kwargs.items():
                if key == 'stats':
                    value = json.dumps(value)
                updates.append(f"{key} = ?")
                params.append(value)
            
            params.append(job_id)
            query = f"UPDATE background_jobs SET {', '.join(updates)}, updated_at = CURRENT_TIMESTAMP WHERE job_id = ?"
            cursor.execute(query, tuple(params))
            conn.commit()
            conn.close()
        except Exception as e:
            app.logger.error(f"Error updating job status: {e}")
    
    app.logger.info(f"Starting bulk fetch job {job_id} for tenant {tenant_slug}")
    update_job_status(job_id, status='processing', progress=0)
    
    try:
        conn = create_connection()
        cursor = conn.cursor()
        
        # Get songs for this tenant that need data (missing image, genre, or language)
        cursor.execute('''
            SELECT id, title, author, image, genre, language 
            FROM songs 
            WHERE tenant_id = ?
            AND (
                image IS NULL OR image = '' OR
                image LIKE '%placeholder%' OR
                image LIKE 'http%' OR
                image LIKE '%setly%' OR
                image LIKE '%music-icon%' OR
                image LIKE '%default%' OR
                genre IS NULL OR genre = '' OR
                language IS NULL OR language = '' OR language = 'unknown'
            )
            LIMIT ?
        ''', (tenant_id, batch_size))
        
        songs = cursor.fetchall()
        total_songs = len(songs)
        
        stats = {
            'total': total_songs,
            'images_fetched': 0,
            'genres_added': 0,
            'languages_added': 0,
            'errors': 0,
            'skipped': 0
        }
        
        update_job_status(job_id, stats=stats)
        
        # Track unique artists to avoid duplicate API calls
        processed_artists = {}
        
        for idx, song in enumerate(songs):
            try:
                # Update progress
                progress = int((idx / total_songs) * 100)
                current_song = f"{song['title']} - {song['author']}"
                update_job_status(job_id, progress=progress, current_song=current_song)
                
                # Check if song needs any data
                # First check if image field is empty or has placeholder
                needs_image = (not song['image'] or song['image'] == '' or 
                              (song['image'] and (
                                  'placeholder' in song['image'].lower() or 
                                  song['image'].startswith('http') or
                                  'setly' in song['image'].lower() or
                                  'music-icon' in song['image'].lower() or
                                  'default' in song['image'].lower()
                              )))
                
                # If image field has a value, check if file actually exists on disk
                if not needs_image and song['image']:
                    import os
                    # Use absolute path for file check
                    app_dir = os.path.dirname(os.path.abspath(__file__))
                    image_path = os.path.join(app_dir, 'static', 'tenants', tenant_slug, 'author_images', song['image'])
                    if not os.path.exists(image_path):
                        app.logger.info(f"Image file missing for {song['title']}: {image_path}")
                        needs_image = True  # File doesn't exist, need to download
                
                needs_genre = not song['genre'] or song['genre'] == ''
                needs_language = not song['language'] or song['language'] in ['', 'unknown']
                
                if not (needs_image or needs_genre or needs_language):
                    stats['skipped'] += 1
                    continue
                
                # Check if we already processed this artist
                artist_name = song['author']
                if artist_name in processed_artists:
                    artist_data = processed_artists[artist_name]
                else:
                    # Fetch from Spotify with minimal delay to avoid rate limiting
                    artist_data = get_spotify_image(artist_name)
                    processed_artists[artist_name] = artist_data
                    
                    # Very small delay to avoid hammering Spotify API
                    time.sleep(0.1)
                
                if artist_data:
                    updates = []
                    params = []
                    
                    # Update image if needed
                    if needs_image and artist_data.get('image_url'):
                        # Normalize filename: handle special characters, multiple artists, etc.
                        normalized_artist = normalize_artist_filename(artist_name)
                        filename = f"{normalized_artist}.jpg"
                        saved_filename = download_image(artist_data['image_url'], filename, tenant_slug)
                        if saved_filename:
                            updates.append('image = ?')
                            params.append(saved_filename)
                            stats['images_fetched'] += 1
                    
                    # Update genre if needed
                    if needs_genre and artist_data.get('genre'):
                        updates.append('genre = ?')
                        params.append(artist_data['genre'])
                        stats['genres_added'] += 1
                    
                    # Update language if needed  
                    if needs_language and artist_data and artist_data.get('language'):
                        updates.append('language = ?')
                        params.append(artist_data['language'])
                        stats['languages_added'] += 1
                    
                    # Perform update if we have changes
                    if updates:
                        params.append(song['id'])
                        query = f"UPDATE songs SET {', '.join(updates)} WHERE id = ?"
                        cursor.execute(query, tuple(params))
                        conn.commit()  # Commit after each song to avoid losing progress
                else:
                    stats['errors'] += 1
                    
            except Exception as e:
                app.logger.error(f"Error processing song {song['id']}: {e}")
                stats['errors'] += 1
                continue
        
        conn.close()
        
        # Mark job as complete
        message = f"Processed {stats['total']} songs: {stats['images_fetched']} images, {stats['genres_added']} genres, {stats['languages_added']} languages"
        update_job_status(job_id, status='completed', progress=100, stats=stats, message=message)
        app.logger.info(f"Bulk fetch job {job_id} completed: {message}")
        
    except Exception as e:
        update_job_status(job_id, status='error', error=str(e))
        app.logger.error(f"Error in bulk fetch job {job_id}: {e}")

@app.route('/<tenant_slug>/bulk_fetch_count', methods=['GET'])
def tenant_bulk_fetch_count(tenant_slug):
    """Count how many songs need data from Spotify - includes physical file check."""
    import os
    
    try:
        # Check if tenant admin is logged in
        if not session.get('is_tenant_admin') or session.get('tenant_slug') != tenant_slug:
            return jsonify({'success': False, 'message': 'Unauthorized'}), 403
        
        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM tenants WHERE slug = ? AND active = 1', (tenant_slug,))
        tenant = cursor.fetchone()
        
        if not tenant:
            conn.close()
            return jsonify({'success': False, 'message': 'Tenant not found'}), 404
        
        tenant_id = tenant['id']
        
        # Get absolute path to the app directory
        app_dir = os.path.dirname(os.path.abspath(__file__))
        app.logger.info(f"[Tenant Bulk] app_dir: {app_dir}")
        
        # First, count TOTAL songs in database for this tenant
        cursor.execute('SELECT COUNT(*) as total FROM songs WHERE tenant_id = ?', (tenant_id,))
        total_result = cursor.fetchone()
        total_songs_in_db = total_result['total'] if total_result else 0
        
        # Get all songs for this tenant
        cursor.execute('''
            SELECT id, image, genre, language 
            FROM songs 
            WHERE tenant_id = ?
        ''', (tenant_id,))
        songs = cursor.fetchall()
        
        # Count what's actually missing (including physical file check)
        missing_images = 0
        missing_genres = 0
        missing_languages = 0
        total_needing_data = 0
        
        for song in songs:
            needs_image = (not song['image'] or song['image'] == '' or 
                          (song['image'] and (
                              'placeholder' in song['image'].lower() or 
                              song['image'].startswith('http') or
                              'setly' in song['image'].lower() or
                              'music-icon' in song['image'].lower() or
                              'default' in song['image'].lower()
                          )))
            
            # Check if image file actually exists on disk (use absolute path)
            if not needs_image and song['image']:
                image_path = os.path.join(app_dir, 'static', 'tenants', tenant_slug, 'author_images', song['image'])
                if not os.path.exists(image_path):
                    needs_image = True
            
            needs_genre = not song['genre'] or song['genre'] == ''
            needs_language = not song['language'] or song['language'] in ['', 'unknown']
            
            if needs_image:
                missing_images += 1
            if needs_genre:
                missing_genres += 1
            if needs_language:
                missing_languages += 1
            
            if needs_image or needs_genre or needs_language:
                total_needing_data += 1
        
        conn.close()
        
        return jsonify({
            'success': True,
            'total_songs': total_songs_in_db,  # Total songs in database
            'missing_images': missing_images,
            'missing_genres': missing_genres,
            'missing_languages': missing_languages
        })
    except Exception as e:
        app.logger.error(f"Error in tenant_bulk_fetch_count for {tenant_slug}: {e}")
        if 'conn' in locals():
            conn.close()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/<tenant_slug>/bulk_fetch_spotify', methods=['POST'])
def tenant_bulk_fetch_spotify(tenant_slug):
    """Fetch images, genres, and languages from Spotify synchronously."""
    import time
    import os
    
    # Check if tenant admin is logged in
    if not session.get('is_tenant_admin') or session.get('tenant_slug') != tenant_slug:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    # Get tenant info
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM tenants WHERE slug = ? AND active = 1', (tenant_slug,))
    tenant = cursor.fetchone()
    
    if not tenant:
        conn.close()
        return jsonify({'success': False, 'message': 'Tenant not found'}), 404
    
    tenant_id = tenant['id']
    
    # Get absolute path to the app directory
    app_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Get max batch size from system settings (default 20 for safety, can be increased)
    # User can set spotify_batch_size in superadmin settings
    # PythonAnywhere needs smaller batches due to 30-second timeout limit
    max_batch_size = get_system_setting('spotify_batch_size', default=20, value_type=int)
    request_data = request.json if request.json else {}
    requested_batch_size = int(request_data.get('batch_size', max_batch_size))
    
    # Detect PythonAnywhere and limit batch size to prevent timeouts
    # PythonAnywhere has strict 30-second timeout, so we cap at 50 to be safe
    # (with multiplier of 2x, that's 100 songs max, which should complete in ~25-28 seconds)
    is_pythonanywhere = (
        'pythonanywhere.com' in request.host or 
        os.environ.get('PYTHONANYWHERE', '').lower() == 'true' or
        os.path.exists('/home/vittorioviarengo')  # PythonAnywhere user directory
    )
    
    if is_pythonanywhere:
        # Cap at 50 for PythonAnywhere to avoid timeouts (30s server limit)
        # With multiplier of 2x, that's 100 songs max per batch
        max_batch_size = min(max_batch_size, 50)
        app.logger.info(f"[Tenant Bulk] PythonAnywhere detected - capping batch size at {max_batch_size} (requested: {requested_batch_size}, original max: {get_system_setting('spotify_batch_size', default=20, value_type=int)})")
    
    # Use the batch size from settings directly (user can configure it)
    batch_size = min(requested_batch_size, max_batch_size)
    
    # Log the batch size being used
    app.logger.info(f"[Tenant Bulk] Final batch size: {batch_size} (requested: {requested_batch_size}, max: {max_batch_size})")
    
    try:
        # First, count total songs that might need data
        cursor.execute('SELECT COUNT(*) as total FROM songs WHERE tenant_id = ?', (tenant_id,))
        total_result = cursor.fetchone()
        total_in_db = total_result['total'] if total_result else 0
        
        # Get more songs than batch_size to compensate for skips
        # Many songs match the query but get skipped (e.g., already have images, Spotify returns no genre, etc.)
        # Use multiplier from settings (default 2x for safety, can be increased)
        batch_multiplier = get_system_setting('spotify_batch_multiplier', default=2, value_type=int)
        
        extended_batch = int(batch_size * batch_multiplier)
        app.logger.info(f"[Tenant Bulk] Extended batch: {extended_batch} (batch_size: {batch_size}, multiplier: {batch_multiplier})")
        
        # First, get songs that match the obvious patterns OR have missing genre/language
        # This query finds songs with obvious missing data
        cursor.execute('''
            SELECT id, title, author, image, genre, language 
            FROM songs 
            WHERE tenant_id = ?
            AND (
                image IS NULL OR image = '' OR
                image LIKE '%placeholder%' OR
                image LIKE 'http%' OR
                image LIKE '%setly%' OR
                image LIKE '%music-icon%' OR
                image LIKE '%default%' OR
                genre IS NULL OR genre = '' OR
                language IS NULL OR language = '' OR language = 'unknown'
            )
            LIMIT ?
        ''', (tenant_id, extended_batch))
        
        songs = cursor.fetchall()
        
        # Also get songs that have missing genre/language (they might also have missing image files)
        if len(songs) < extended_batch:
            remaining = extended_batch - len(songs)
            song_ids = [song['id'] for song in songs] if songs else []
            
            if song_ids:
                placeholders = ','.join(['?'] * len(song_ids))
                cursor.execute(f'''
                    SELECT id, title, author, image, genre, language 
                    FROM songs 
                    WHERE tenant_id = ?
                    AND id NOT IN ({placeholders})
                    AND (genre IS NULL OR genre = '' OR language IS NULL OR language = '' OR language = 'unknown')
                    LIMIT ?
                ''', [tenant_id] + song_ids + [remaining])
            else:
                cursor.execute('''
                    SELECT id, title, author, image, genre, language 
                    FROM songs 
                    WHERE tenant_id = ?
                    AND (genre IS NULL OR genre = '' OR language IS NULL OR language = '' OR language = 'unknown')
                    LIMIT ?
                ''', (tenant_id, remaining))
            
            additional_songs = cursor.fetchall()
            if additional_songs:
                songs.extend(additional_songs)
                app.logger.info(f"[Tenant Bulk] Added {len(additional_songs)} more songs with missing genre/language")
        
        # If still not enough, also get songs that have image values (even if they don't match patterns)
        # These might have images in DB but missing physical files
        if len(songs) < extended_batch:
            remaining = extended_batch - len(songs)
            song_ids = [song['id'] for song in songs] if songs else []
            
            if song_ids:
                placeholders = ','.join(['?'] * len(song_ids))
                cursor.execute(f'''
                    SELECT id, title, author, image, genre, language 
                    FROM songs 
                    WHERE tenant_id = ?
                    AND id NOT IN ({placeholders})
                    AND image IS NOT NULL 
                    AND image != ''
                    LIMIT ?
                ''', [tenant_id] + song_ids + [remaining])
            else:
                cursor.execute('''
                    SELECT id, title, author, image, genre, language 
                    FROM songs 
                    WHERE tenant_id = ?
                    AND image IS NOT NULL 
                    AND image != ''
                    LIMIT ?
                ''', (tenant_id, remaining))
            
            more_songs = cursor.fetchall()
            if more_songs:
                songs.extend(more_songs)
                app.logger.info(f"[Tenant Bulk] Added {len(more_songs)} more songs with image values (will check if files exist)")
        
        total_songs = len(songs)
        
        app.logger.info(f"[Tenant Bulk] Found {total_songs} songs to check for tenant {tenant_slug}")
        
        stats = {
            'total': total_songs,
            'images_fetched': 0,
            'genres_added': 0,
            'languages_added': 0,
            'errors': 0,
            'skipped': 0
        }
        
        # Track unique artists to avoid duplicate API calls
        processed_artists = {}
        
        for idx, song in enumerate(songs):
            try:
                # Check if song needs any data
                needs_image = (not song['image'] or song['image'] == '' or 
                              (song['image'] and (
                                  'placeholder' in song['image'].lower() or 
                                  song['image'].startswith('http') or
                                  'setly' in song['image'].lower() or
                                  'music-icon' in song['image'].lower() or
                                  'default' in song['image'].lower()
                              )))
                
                # If image field has a value, check if file actually exists on disk
                image_file_missing = False
                if not needs_image and song['image']:
                    image_path = os.path.join(app_dir, 'static', 'tenants', tenant_slug, 'author_images', song['image'])
                    if not os.path.exists(image_path):
                        needs_image = True
                        image_file_missing = True
                
                needs_genre = not song['genre'] or song['genre'] == ''
                needs_language = not song['language'] or song['language'] in ['', 'unknown']
                
                if not (needs_image or needs_genre or needs_language):
                    stats['skipped'] += 1
                    continue
                
                # Log what we're processing (only first few to avoid spam)
                if idx < 3:
                    app.logger.info(f"[Tenant Bulk] Processing song {song['id']} ({song['title']}): needs_image={needs_image} (file_missing={image_file_missing}), needs_genre={needs_genre}, needs_language={needs_language}")
                
                # Check if we already processed this artist
                artist_name = song['author']
                if artist_name in processed_artists:
                    artist_data = processed_artists[artist_name]
                else:
                    # Fetch from Spotify
                    artist_data = get_spotify_image(artist_name)
                    processed_artists[artist_name] = artist_data
                    
                    # Check for rate limiting
                    if artist_data and artist_data.get('rate_limited'):
                        app.logger.warning(f"[Tenant Bulk] Spotify rate limit hit, waiting 30 seconds...")
                        stats['errors'] += 1  # Count as error
                        time.sleep(30)  # Wait 30 seconds for rate limit to reset
                        # Don't cache rate_limited result, try again next time
                        del processed_artists[artist_name]
                        continue
                    
                    time.sleep(0.1)  # Standard delay between calls (increased slightly to avoid rate limits)
                
                if artist_data and not artist_data.get('rate_limited'):
                    updates = []
                    params = []
                    
                    # Update image if needed
                    if needs_image:
                        if artist_data.get('image_url'):
                            normalized_artist = normalize_artist_filename(artist_name)
                            filename = f"{normalized_artist}.jpg"
                            saved_filename = download_image(artist_data['image_url'], filename, tenant_slug)
                            if saved_filename:
                                updates.append('image = ?')
                                params.append(saved_filename)
                                stats['images_fetched'] += 1
                                app.logger.info(f"[Tenant Bulk] Downloaded image for '{artist_name}' (song: {song['title']})")
                            else:
                                app.logger.warning(f"[Tenant Bulk] Failed to download image for '{artist_name}' (song: {song['title']}, URL: {artist_data.get('image_url')})")
                        else:
                            app.logger.warning(f"[Tenant Bulk] Spotify found artist '{artist_name}' but no image_url available (song: {song['title']})")
                    
                    # Update genre if needed
                    if needs_genre and artist_data and artist_data.get('genre'):
                        updates.append('genre = ?')
                        params.append(artist_data['genre'])
                        stats['genres_added'] += 1
                    
                    # Update language if needed  
                    if needs_language and artist_data and artist_data.get('language'):
                        updates.append('language = ?')
                        params.append(artist_data['language'])
                        stats['languages_added'] += 1
                    
                    # Perform update if we have changes
                    if updates:
                        params.append(song['id'])
                        query = f"UPDATE songs SET {', '.join(updates)} WHERE id = ?"
                        cursor.execute(query, tuple(params))
                        conn.commit()
                        app.logger.info(f"[Tenant Bulk] Updated song {song['id']} ({song['title']}): {', '.join(updates)}")
                    else:
                        # Spotify returned data but no updates were made
                        # This could mean: artist found but missing the specific data we need
                        if needs_image and not artist_data.get('image_url'):
                            app.logger.warning(f"[Tenant Bulk] Artist '{artist_name}' found but no image available (song: {song['title']})")
                            stats['errors'] += 1
                        elif needs_genre and not artist_data.get('genre'):
                            app.logger.warning(f"[Tenant Bulk] Artist '{artist_name}' found but no genre available (song: {song['title']})")
                            stats['errors'] += 1
                        elif needs_language and not artist_data.get('language'):
                            app.logger.warning(f"[Tenant Bulk] Artist '{artist_name}' found but no language detected (song: {song['title']})")
                            stats['errors'] += 1
                        # If we got something but didn't need it, don't count as error
                else:
                    # Spotify returned no data for this artist
                    if artist_data is None:
                        error_msg = f"Spotify did NOT find artist '{artist_name}' (song: {song['title']})"
                        app.logger.warning(f"[Tenant Bulk] {error_msg}")
                        # Store error message for debugging
                        if 'error_details' not in stats:
                            stats['error_details'] = []
                        stats['error_details'].append({
                            'artist': artist_name,
                            'song': song['title'],
                            'reason': 'artist_not_found'
                        })
                        stats['errors'] += 1
                    elif artist_data.get('rate_limited'):
                        app.logger.warning(f"[Tenant Bulk] Spotify rate limited for artist '{artist_name}' (song: {song['title']})")
                        # Don't count rate limit as error (already handled above with continue)
                        stats['errors'] += 1
                    
            except Exception as e:
                app.logger.error(f"Error processing song {song['id']}: {e}")
                stats['errors'] += 1
                continue
        
        conn.close()
        
        # Log final summary
        missing_files = stats.get('missing_files_count', 0)
        app.logger.info(f"[Tenant Bulk] Tenant {tenant_slug} batch complete: " +
                       f"Total={stats['total']}, Images={stats['images_fetched']}, " +
                       f"Genres={stats['genres_added']}, Languages={stats['languages_added']}, " +
                       f"Skipped={stats['skipped']}, Errors={stats['errors']}, MissingFiles={missing_files}")
        
        # Build message with info about remaining songs
        message = f"Processed {stats['total']} songs: {stats['images_fetched']} images, {stats['genres_added']} genres, {stats['languages_added']} languages"
        
        # Check if there are more songs to process - must check physical files!
        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, image, genre, language 
            FROM songs 
            WHERE tenant_id = ?
        ''', (tenant_id,))
        all_songs = cursor.fetchall()
        conn.close()
        
        # Count what's actually missing (including physical file check)
        remaining_images = 0
        remaining_genres = 0
        remaining_languages = 0
        
        for song in all_songs:
            needs_image = (not song['image'] or song['image'] == '' or 
                          (song['image'] and (
                              'placeholder' in song['image'].lower() or 
                              song['image'].startswith('http') or
                              'setly' in song['image'].lower() or
                              'music-icon' in song['image'].lower() or
                              'default' in song['image'].lower()
                          )))
            
            # Check if image file actually exists on disk
            if not needs_image and song['image']:
                image_path = os.path.join(app_dir, 'static', 'tenants', tenant_slug, 'author_images', song['image'])
                if not os.path.exists(image_path):
                    needs_image = True
            
            needs_genre = not song['genre'] or song['genre'] == ''
            needs_language = not song['language'] or song['language'] in ['', 'unknown']
            
            if needs_image:
                remaining_images += 1
            if needs_genre:
                remaining_genres += 1
            if needs_language:
                remaining_languages += 1
        
        # Use remaining_images as the primary count (since that's usually what's missing)
        remaining = remaining_images
        has_more = remaining_images > 0 or remaining_genres > 0 or remaining_languages > 0
        
        app.logger.info(f"Bulk fetch completed for {tenant_slug}: {message}")
        app.logger.info(f"[Tenant Bulk] Remaining: {remaining_images} images, {remaining_genres} genres, {remaining_languages} languages. Has more: {has_more}")
        
        # Include error details (limit to first 20 for performance)
        error_details = stats.get('error_details', [])[:20]
        
        return jsonify({
            'success': True,
            'message': message,
            'stats': stats,
            'total_in_db': total_in_db,
            'has_more': has_more,
            'remaining': remaining,
            'remaining_images': remaining_images,
            'remaining_genres': remaining_genres,
            'remaining_languages': remaining_languages,
            'error_details': error_details  # First 20 artists not found by Spotify
        })
        
    except Exception as e:
        conn.close()
        app.logger.error(f"Error in bulk fetch for {tenant_slug}: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/<tenant_slug>/check_image_sync', methods=['GET'])
def tenant_check_image_sync(tenant_slug):
    """Check if images in database match files in filesystem."""
    import os
    
    # Check if tenant admin is logged in
    if not session.get('is_tenant_admin') or session.get('tenant_slug') != tenant_slug:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM tenants WHERE slug = ? AND active = 1', (tenant_slug,))
    tenant = cursor.fetchone()
    
    if not tenant:
        conn.close()
        return jsonify({'success': False, 'message': 'Tenant not found'}), 404
    
    tenant_id = tenant['id']
    app_dir = os.path.dirname(os.path.abspath(__file__))
    images_dir = os.path.join(app_dir, 'static', 'tenants', tenant_slug, 'author_images')
    
    # Get all songs with image values
    cursor.execute('''
        SELECT id, title, author, image 
        FROM songs 
        WHERE tenant_id = ? 
        AND image IS NOT NULL 
        AND image != ''
    ''', (tenant_id,))
    songs = cursor.fetchall()
    conn.close()
    
    stats = {
        'total_with_image_in_db': len(songs),
        'files_exist': 0,
        'files_missing': 0,
        'missing_files': []
    }
    
    for song in songs:
        image_path = os.path.join(images_dir, song['image'])
        if os.path.exists(image_path):
            stats['files_exist'] += 1
        else:
            stats['files_missing'] += 1
            stats['missing_files'].append({
                'id': song['id'],
                'title': song['title'],
                'author': song['author'],
                'image': song['image']
            })
            # Limit to first 50 for performance
            if len(stats['missing_files']) >= 50:
                break
    
    return jsonify({
        'success': True,
        'tenant_name': tenant['name'],
        'tenant_slug': tenant_slug,
        'images_directory': images_dir,
        'stats': stats
    })

@app.route('/<tenant_slug>/bulk_fetch_status/<job_id>', methods=['GET'])
def tenant_bulk_fetch_status(tenant_slug, job_id):
    """Check the status of a background bulk fetch job."""
    import json
    
    # Check if tenant admin is logged in
    if not session.get('is_tenant_admin') or session.get('tenant_slug') != tenant_slug:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    # Read job status from DATABASE
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM background_jobs WHERE job_id = ?', (job_id,))
    job = cursor.fetchone()
    conn.close()
    
    if not job:
        return jsonify({'success': False, 'message': 'Job not found'}), 404
    
    return jsonify({
        'success': True,
        'status': job['status'],
        'progress': job['progress'],
        'current_song': job['current_song'],
        'stats': json.loads(job['stats']) if job['stats'] else {},
        'message': job['message'],
        'error': job['error']
    })




def reload_webapp():
    # Read PythonAnywhere credentials from environment variables for security
    api_token = os.environ.get('PYTHONANYWHERE_API_TOKEN')
    username = os.environ.get('PYTHONANYWHERE_USERNAME', 'vittorioviarengo')
    domain_name = os.environ.get('PYTHONANYWHERE_DOMAIN', 'vittorioviarengo.pythonanywhere.com')
    
    if not api_token:
        logging.error("PYTHONANYWHERE_API_TOKEN not set in environment variables")
        return
    
    url = f"https://www.pythonanywhere.com/api/v0/user/{username}/webapps/{domain_name}/reload/"
    headers = {"Authorization": f"Token {api_token}"}
    response = requests.post(url, headers=headers)
    if response.status_code == 200:
        logging.info("Web app reloaded successfully.")
    else:
        logging.error(f"Failed to reload web app. Status code: {response.status_code}, Response: {response.text}")

def async_reload():
    thread = threading.Thread(target=reload_webapp)
    thread.start()

@app.route('/reload')
def reload_route():
    # SECURITY: Restrict to superadmin only
    # This endpoint triggers a reload of the entire web app on PythonAnywhere
    # Without auth, anyone could trigger continuous reloads (potential DOS)
    if not session.get('is_superadmin'):
        return jsonify({"error": "Unauthorized. Superadmin access required."}), 403
    
    async_reload()
    return jsonify({"message": "Reload initiated. Please wait for the application to restart."})


#--------------------------------------------- Main Functions  ---------------------------------------------
@app.route("/")
def index():
    """Default index - redirect to super admin login"""
    return redirect(url_for('superadmin.login'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    """Public signup page for new musicians (with referral tracking)."""
    import secrets
    from utils.password_utils import generate_reset_token, get_token_expiry
    from utils.tenant_utils import get_tenant_dir
    
    ref_code = request.args.get('ref') or request.form.get('ref')
    referrer = None
    
    # Validate referral code if provided
    if ref_code:
        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM tenants WHERE referral_code = ?', (ref_code,))
        referrer = cursor.fetchone()
        conn.close()
    
    if request.method == 'POST':
        name = request.form.get('name')
        slug = request.form.get('slug')
        email = request.form.get('email')
        preferred_language = request.form.get('preferred_language', 'en')
        
        # Validate required fields
        if not all([name, slug, email]):
            flash('Please fill in all required fields', 'error')
            form_data = {'name': name, 'slug': slug, 'email': email}
            return render_template('signup.html', form_data=form_data, ref_code=ref_code, referrer=referrer)
        
        conn = create_connection()
        cursor = conn.cursor()
        
        try:
            # Check if slug is unique
            cursor.execute('SELECT id FROM tenants WHERE slug = ?', (slug,))
            if cursor.fetchone():
                flash('This URL is already taken. Please choose another.', 'error')
                form_data = {'name': name, 'slug': slug, 'email': email}
                return render_template('signup.html', form_data=form_data, ref_code=ref_code, referrer=referrer)
            
            # Check if email is unique
            cursor.execute('SELECT id FROM tenants WHERE email = ?', (email,))
            if cursor.fetchone():
                flash('This email is already registered. Please use another or login.', 'error')
                form_data = {'name': name, 'slug': slug, 'email': email}
                return render_template('signup.html', form_data=form_data, ref_code=ref_code, referrer=referrer)
            
            # Generate setup token and referral code
            reset_token = generate_reset_token()
            token_expiry = get_token_expiry(hours=48)  # 48 hours for signup
            referral_code = secrets.token_urlsafe(8)
            
            # Ensure referral code is unique
            while True:
                cursor.execute('SELECT id FROM tenants WHERE referral_code = ?', (referral_code,))
                if cursor.fetchone() is None:
                    break
                referral_code = secrets.token_urlsafe(8)
            
            # Create tenant directories
            get_tenant_dir(app, slug, 'logos')
            get_tenant_dir(app, slug, 'images')
            get_tenant_dir(app, slug, 'author_images')
            
            # Get referrer ID if valid
            referred_by = referrer['id'] if referrer else None
            
            # Create new tenant
            cursor.execute('''
                INSERT INTO tenants (
                    name, slug, email, password, preferred_language, active,
                    reset_token, reset_token_expiry, password_set, referral_code, referred_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (name, slug, email, '', preferred_language, 1, reset_token, token_expiry, 0, referral_code, referred_by))
            
            # Mark any pending invitations to this email as completed
            cursor.execute('''
                UPDATE invitations 
                SET status = 'completed', completed_at = CURRENT_TIMESTAMP
                WHERE email = ? AND status = 'pending'
            ''', (email,))
            
            conn.commit()
            
            # TODO: Send welcome email with setup link
            setup_url = request.url_root + slug + '/reset-password/' + reset_token
            
            flash(f'Account created successfully! Check your email for setup instructions.', 'success')
            flash(f'Setup link: {setup_url}', 'info')
            
            conn.close()
            return redirect(url_for('tenant_login', tenant_slug=slug))
            
        except Exception as e:
            conn.close()
            flash(f'Error creating account: {str(e)}', 'error')
            form_data = {'name': name, 'slug': slug, 'email': email}
            return render_template('signup.html', form_data=form_data, ref_code=ref_code, referrer=referrer)
    
    # GET request - show signup form
    return render_template('signup.html', ref_code=ref_code, referrer=referrer)

@app.route('/<tenant_slug>/')
def tenant_home(tenant_slug):
    """Display the home page for a specific tenant."""
    conn = create_connection()
    cursor = conn.cursor()
    
    # Check if tenant exists and is active
    cursor.execute('SELECT * FROM tenants WHERE slug = ? AND active = 1', (tenant_slug,))
    tenant = cursor.fetchone()
    conn.close()
    
    if not tenant:
        flash('Tenant not found or inactive')
        return redirect(url_for('index'))
    
    # Store tenant info in session
    session['tenant_slug'] = tenant_slug
    session['tenant_id'] = tenant['id']
    session['tenant_name'] = tenant['name']
    
    # Check if there's an active gig (only if gigs table exists)
    # If no active gig, redirect to scan_qr page with message
    try:
        active_gig = get_active_gig(tenant['id'])
        if not active_gig:
            flash(_('No active gig. Please wait for the musician to start the gig.'), 'info')
            return redirect(url_for('tenant_scan_qr', tenant_slug=tenant_slug))
        else:
            # Verify user has scanned QR code for the current active gig
            # Don't auto-update gig_id - user must scan QR code to verify presence
            session_gig_id = session.get('gig_id')
            if session_gig_id != active_gig['id']:
                # User hasn't scanned QR code for this gig - redirect to scan_qr
                flash(_('A new musical event has started. Please scan the QR code to participate.'), 'info')
                return redirect(url_for('tenant_scan_qr', tenant_slug=tenant_slug))
    except Exception:
        # If gigs table doesn't exist yet, allow access (backward compatibility)
        pass
    
    # Generate unique session_id for tracking user activity
    # Format: tenant_id-YYYYMMDDHHMMSS-random
    if 'user_session_id' not in session:
        try:
            from utils.audit_logger import log_event
        except ImportError:
            log_event = None
        import secrets
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        random_suffix = secrets.token_hex(4)
        session['user_session_id'] = f"{tenant['id']}-{timestamp}-{random_suffix}"
        
        # Log session start (async - non-blocking)
        if log_event:
            log_event(
                action='user_session_start',
                entity_type='session',
                tenant_id=tenant['id'],
                user_type='end_user',
                user_session_id=session['user_session_id'],
                details={
                'tenant_slug': tenant_slug,
                'entry_point': 'home',
                'user_name': request.args.get('user', '')
            }
        )
    
    user_name = request.args.get('user', '')
    return render_template('index.html', user_name=user_name, tenant=tenant)

@app.route('/<tenant_slug>/logout')
def tenant_logout(tenant_slug):
    """Tenant admin logout."""
    session.pop('is_tenant_admin', None)
    session.pop('tenant_id', None)
    session.pop('tenant_slug', None)
    flash('You have been logged out successfully.')
    return redirect(url_for('tenant_login', tenant_slug=tenant_slug))

@app.route('/<tenant_slug>/login', methods=['GET', 'POST'])
@limiter.limit("5 per 15 minutes", methods=['POST'])
def tenant_login(tenant_slug):
    """Tenant admin login page."""
    conn = create_connection()
    cursor = conn.cursor()
    
    # Check if tenant exists and is active
    cursor.execute('SELECT * FROM tenants WHERE slug = ? AND active = 1', (tenant_slug,))
    tenant = cursor.fetchone()
    
    print(f"DEBUG tenant_login: tenant_slug={tenant_slug}, tenant={tenant}")
    
    if not tenant:
        conn.close()
        flash('Tenant not found or inactive')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        try:
            from utils.audit_logger import log_event
        except ImportError:
            log_event = None
        
        email = request.form.get('email')
        password = request.form.get('password')
        
        print(f"DEBUG tenant_login POST: email={email}, tenant_email={tenant['email']}")
        
        if email == tenant['email'] and check_password_hash(tenant['password'], password):
            # Make session permanent so it persists across browser tabs/closing
            session.permanent = True
            
            session['is_tenant_admin'] = True
            session['tenant_id'] = tenant['id']
            session['tenant_slug'] = tenant_slug
            # Set default language to tenant's preferred language
            try:
                session['language'] = tenant['preferred_language'] if tenant['preferred_language'] else 'en'
            except (KeyError, IndexError):
                session['language'] = 'en'
            
            # Clear reset link if present
            session.pop('reset_link', None)
            
            # Update last login time
            cursor.execute('UPDATE tenants SET last_login_at = CURRENT_TIMESTAMP WHERE id = ?', (tenant['id'],))
            conn.commit()
            
            # Check if wizard needs to be completed
            wizard_completed = tenant['wizard_completed'] if tenant['wizard_completed'] else 0
            has_essential_data = tenant['slug'] and tenant['name']
            
            conn.close()
            
            # Log successful login (async - non-blocking)
            if log_event:
                log_event(
                    action='tenant_login',
                entity_type='tenant',
                entity_id=tenant['id'],
                tenant_id=tenant['id'],
                user_type='tenant_admin',
                details={
                    'tenant_slug': tenant_slug,
                    'login_method': 'password',
                    'success': True,
                        'wizard_completed': bool(wizard_completed and has_essential_data)
                    }
                )
            
            # Redirect to wizard if not completed or missing essential data
            if not wizard_completed or not has_essential_data:
                return redirect(url_for('wizard', tenant_slug=tenant_slug))
            
            return redirect(url_for('tenant_admin', tenant_slug=tenant_slug))
        else:
            # Log failed login attempt (async - non-blocking)
            if log_event:
                log_event(
                    action='tenant_login_failed',
                entity_type='tenant',
                tenant_id=tenant['id'],
                user_type='tenant_admin',
                details={
                    'tenant_slug': tenant_slug,
                    'email_attempted': email,
                    'failure_reason': 'invalid_credentials'
                }
            )
            flash('Invalid email or password')
    
    conn.close()
    return render_template('login.html', tenant=tenant)

@app.route('/<tenant_slug>/forgot-password', methods=['GET', 'POST'])
def tenant_forgot_password(tenant_slug):
    """Tenant forgot password page - request password reset."""
    from utils.password_utils import generate_reset_token, get_token_expiry
    from flask_mail import Message
    
    conn = create_connection()
    cursor = conn.cursor()
    
    # Check if tenant exists and is active
    cursor.execute('SELECT * FROM tenants WHERE slug = ? AND active = 1', (tenant_slug,))
    tenant = cursor.fetchone()
    
    if not tenant:
        conn.close()
        flash('Tenant not found or inactive')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        
        # Check if email matches tenant
        if email == tenant['email']:
            # Generate reset token
            reset_token = generate_reset_token()
            token_expiry = get_token_expiry(hours=2)  # 2 hour expiry for password resets
            
            # Update database with reset token
            cursor.execute('''
                UPDATE tenants 
                SET reset_token = ?, reset_token_expiry = ?
                WHERE id = ?
            ''', (reset_token, token_expiry, tenant['id']))
            conn.commit()
            
            # Send reset email if email is configured
            if app.config.get('MAIL_USERNAME') and app.config.get('MAIL_PASSWORD'):
                try:
                    reset_url = url_for('tenant_reset_password', tenant_slug=tenant_slug, token=reset_token, _external=True)
                    
                    msg = Message(
                        subject=f"Password Reset - {tenant['name']}",
                        sender=app.config['MAIL_DEFAULT_SENDER'],
                        recipients=[email]
                    )
                    
                    msg.body = f"""Hi {tenant['name']},

You requested to reset your password for your music request management system.

Click the link below to reset your password (valid for 2 hours):
{reset_url}

If you didn't request this, please ignore this email.

Best regards,
Music Request System
"""
                    
                    msg.html = f"""
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <h2 style="color: #2c3e50;">Password Reset Request</h2>
    <p>Hi <strong>{tenant['name']}</strong>,</p>
    <p>You requested to reset your password for your music request management system.</p>
    <p>Click the button below to reset your password:</p>
    <p style="margin: 30px 0;">
        <a href="{reset_url}" style="background-color: #3498db; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; display: inline-block;">Reset Password</a>
    </p>
    <p style="color: #7f8c8d; font-size: 14px;">This link will expire in 2 hours.</p>
    <p style="color: #7f8c8d; font-size: 14px;">If you didn't request this, please ignore this email.</p>
    <hr style="border: none; border-top: 1px solid #ecf0f1; margin: 30px 0;">
    <p style="color: #95a5a6; font-size: 12px;">Music Request System</p>
</body>
</html>
"""
                    
                    mail.send(msg)
                    flash(_('Password reset email sent! Check your inbox.'), 'success')
                except Exception as e:
                    print(f"Error sending reset email: {e}")
                    # Store the reset link in session to display it properly on login page
                    session['reset_link'] = f'/{tenant_slug}/reset-password/{reset_token}'
                    flash(_('Email system not configured. Your reset link is shown below.'), 'info')
            else:
                # Store the reset link in session to display it properly on login page
                session['reset_link'] = f'/{tenant_slug}/reset-password/{reset_token}'
                flash(_('Email system not configured. Your reset link is shown below.'), 'info')
        else:
            # Don't reveal if email exists or not (security best practice)
            flash(_('If that email is registered, a password reset link has been sent.'), 'success')
        
        conn.close()
        return redirect(url_for('tenant_login', tenant_slug=tenant_slug))
    
    conn.close()
    return render_template('forgot_password.html', tenant=tenant)

@app.route('/<tenant_slug>/reset-password/<token>', methods=['GET', 'POST'])
def tenant_reset_password(tenant_slug, token):
    """Tenant reset password page - set new password with token."""
    from utils.password_utils import is_token_valid
    from werkzeug.security import generate_password_hash
    
    # Clear reset link from session since user is using it now
    session.pop('reset_link', None)
    
    conn = create_connection()
    cursor = conn.cursor()
    
    # Check if tenant exists and is active
    cursor.execute('''
        SELECT * FROM tenants 
        WHERE slug = ? AND active = 1 AND reset_token = ?
    ''', (tenant_slug, token))
    tenant = cursor.fetchone()
    
    if not tenant:
        conn.close()
        flash('Invalid or expired reset link')
        return redirect(url_for('index'))
    
    # Check if token is expired
    if not is_token_valid(tenant['reset_token_expiry']):
        conn.close()
        flash('Reset link has expired. Please request a new one.')
        return redirect(url_for('tenant_forgot_password', tenant_slug=tenant_slug))
    
    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if not password or len(password) < 6:
            flash('Password must be at least 6 characters long')
        elif password != confirm_password:
            flash('Passwords do not match')
        else:
            # Update password and clear reset token
            hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
            cursor.execute('''
                UPDATE tenants 
                SET password = ?, reset_token = NULL, reset_token_expiry = NULL, password_set = 1
                WHERE id = ?
            ''', (hashed_password, tenant['id']))
            conn.commit()
            conn.close()
            
            flash('Password successfully set! You can now log in.')
            return redirect(url_for('tenant_login', tenant_slug=tenant_slug))
    
    conn.close()
    return render_template('reset_password.html', tenant=tenant, token=token)

@app.route('/<tenant_slug>/change-password', methods=['POST'])
def tenant_change_password(tenant_slug):
    """Change password for logged-in tenant admin."""
    from werkzeug.security import generate_password_hash, check_password_hash
    
    if not session.get('is_tenant_admin') or session.get('tenant_slug') != tenant_slug:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    data = request.get_json()
    current_password = data.get('current_password', '')
    new_password = data.get('new_password', '')
    confirm_password = data.get('confirm_password', '')
    
    if not current_password or not new_password or not confirm_password:
        return jsonify({'success': False, 'message': 'All fields are required'}), 400
    
    if len(new_password) < 6:
        return jsonify({'success': False, 'message': 'Password must be at least 6 characters'}), 400
    
    if new_password != confirm_password:
        return jsonify({'success': False, 'message': 'New passwords do not match'}), 400
    
    conn = create_connection()
    cursor = conn.cursor()
    
    try:
        tenant_id = session.get('tenant_id')
        cursor.execute('SELECT password FROM tenants WHERE id = ?', (tenant_id,))
        tenant = cursor.fetchone()
        
        if not tenant or not check_password_hash(tenant['password'], current_password):
            return jsonify({'success': False, 'message': 'Current password is incorrect'}), 400
        
        # Update password
        hashed_password = generate_password_hash(new_password, method='pbkdf2:sha256')
        cursor.execute('UPDATE tenants SET password = ?, password_set = 1 WHERE id = ?', (hashed_password, tenant_id))
        conn.commit()
        
        return jsonify({'success': True, 'message': 'Password changed successfully'})
    except Exception as e:
        print(f"Error changing password: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        conn.close()

@app.route('/<tenant_slug>/wizard')
def wizard(tenant_slug):
    """Setup wizard for tenant onboarding."""
    if not session.get('is_tenant_admin') or session.get('tenant_slug') != tenant_slug:
        return redirect(url_for('tenant_login', tenant_slug=tenant_slug))
    
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM tenants WHERE slug = ? AND active = 1', (tenant_slug,))
    tenant = cursor.fetchone()
    conn.close()
    
    if not tenant:
        return redirect(url_for('index'))
    
    return render_template('wizard.html', tenant=tenant)

@app.route('/<tenant_slug>/wizard/save', methods=['POST'])
def wizard_save(tenant_slug):
    """Save wizard progress."""
    if not session.get('is_tenant_admin') or session.get('tenant_slug') != tenant_slug:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    conn = create_connection()
    cursor = conn.cursor()
    
    try:
        tenant_id = session.get('tenant_id')
        
        # Get form data
        artist_name = request.form.get('artist_name', '').strip()
        bio = request.form.get('bio', '').strip()
        website = request.form.get('website', '').strip()
        event_calendar = request.form.get('event_calendar', '').strip()
        venue = request.form.get('venue', '').strip()
        max_requests = request.form.get('max_requests', '3')
        default_language = request.form.get('default_language', 'en')
        
        # Build update query for text fields
        update_fields = []
        update_params = []
        
        if artist_name:
            update_fields.append('name = ?')
            update_params.append(artist_name)
        
        if bio is not None:  # Allow empty string to clear bio
            update_fields.append('bio = ?')
            update_params.append(bio)
        
        if website:
            update_fields.append('website_url = ?')
            update_params.append(website)
        
        if event_calendar:
            update_fields.append('events_link = ?')
            update_params.append(event_calendar)
        
        if venue is not None:  # Allow empty string
            update_fields.append('venue_name = ?')
            update_params.append(venue)
        
        if max_requests:
            update_fields.append('max_requests = ?')
            update_params.append(int(max_requests))
        
        if default_language:
            update_fields.append('default_language = ?')
            update_params.append(default_language)
        
        # Handle file uploads
        logo_file = request.files.get('logo_image')
        banner_file = request.files.get('banner_image')
        
        if logo_file and logo_file.filename:
            # Save logo file
            import os
            filename = secure_filename(logo_file.filename)
            tenant_dir = os.path.join('static', 'tenants', tenant_slug)
            os.makedirs(tenant_dir, exist_ok=True)
            filepath = os.path.join(tenant_dir, f'logo_{filename}')
            logo_file.save(filepath)
            
            update_fields.append('logo_image = ?')
            update_params.append(f'tenants/{tenant_slug}/logo_{filename}')
        
        if banner_file and banner_file.filename:
            # Save banner file
            import os
            filename = secure_filename(banner_file.filename)
            tenant_dir = os.path.join('static', 'tenants', tenant_slug)
            os.makedirs(tenant_dir, exist_ok=True)
            filepath = os.path.join(tenant_dir, f'banner_{filename}')
            banner_file.save(filepath)
            
            update_fields.append('banner_image = ?')
            update_params.append(f'tenants/{tenant_slug}/banner_{filename}')
        
        # Execute update if there are fields to update
        if update_fields:
            update_params.append(tenant_id)
            update_query = f"UPDATE tenants SET {', '.join(update_fields)} WHERE id = ?"
            cursor.execute(update_query, update_params)
            conn.commit()
        
        conn.close()
        return jsonify({'success': True})
    
    except Exception as e:
        conn.close()
        print(f"Error saving wizard progress: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/<tenant_slug>/wizard/complete', methods=['POST'])
def wizard_complete(tenant_slug):
    """Mark wizard as completed."""
    if not session.get('is_tenant_admin') or session.get('tenant_slug') != tenant_slug:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    conn = create_connection()
    cursor = conn.cursor()
    
    try:
        # Mark wizard as completed
        cursor.execute('UPDATE tenants SET wizard_completed = 1 WHERE slug = ?', (tenant_slug,))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/validate-slug', methods=['POST'])
def validate_slug():
    """Validate slug availability and appropriateness."""
    from profanity_list import is_slug_appropriate
    
    data = request.get_json()
    slug = data.get('slug', '').lower().strip()
    
    if not slug:
        return jsonify({'available': False, 'message': 'Slug is required'})
    
    # Check format
    if not re.match(r'^[a-z0-9-]+$', slug):
        return jsonify({'available': False, 'message': 'Only lowercase letters, numbers, and hyphens allowed'})
    
    # Check profanity/reserved words
    is_appropriate, message = is_slug_appropriate(slug)
    if not is_appropriate:
        return jsonify({'available': False, 'message': message})
    
    # Check database for uniqueness
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM tenants WHERE slug = ?', (slug,))
    existing = cursor.fetchone()
    conn.close()
    
    if existing:
        return jsonify({'available': False, 'message': 'This URL is already taken'})
    
    return jsonify({'available': True, 'message': 'Available'})

# Alias for wizard - route name used in template
@app.route('/add_sample_songs', methods=['POST'])
def add_sample_songs_route():
    """Add sample songs - wizard alias."""
    tenant_slug = session.get('tenant_slug')
    if not tenant_slug:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    # Call the existing route function
    return tenant_populate_sample_songs(tenant_slug)

@app.route('/download_csv_template')
def download_csv_template():
    """Download CSV template for song import."""
    from io import StringIO
    import csv
    
    # Create CSV in memory
    output = StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['Title', 'Author', 'Language', 'Genre', 'Playlist'])
    
    # Write example rows
    writer.writerow(['Imagine', 'John Lennon', 'en', 'Pop', 'Classic Hits'])
    writer.writerow(['La Vie en Rose', 'Edith Piaf', 'fr', 'Chanson', 'French Classics'])
    writer.writerow(['Hotel California', 'Eagles', 'en', 'Rock', ''])
    
    # Create response
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=songs_template.csv'}
    )

@app.route('/<tenant_slug>/insights')
def tenant_insights(tenant_slug):
    """Tenant insights dashboard - analytics and statistics."""
    if not session.get('is_tenant_admin') or session.get('tenant_slug') != tenant_slug:
        return redirect(url_for('tenant_login', tenant_slug=tenant_slug))
    
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM tenants WHERE slug = ? AND active = 1', (tenant_slug,))
    tenant = cursor.fetchone()
    
    if not tenant:
        session.clear()
        conn.close()
        flash('This tenant account has been deactivated')
        return redirect(url_for('index'))
    
    tenant_id = tenant['id']
    
    # Get request statistics from requests table
    cursor.execute('SELECT COUNT(*) as total FROM requests WHERE tenant_id = ?', (tenant_id,))
    total_requests = cursor.fetchone()['total']
    
    cursor.execute('SELECT COUNT(*) as fulfilled FROM requests WHERE tenant_id = ? AND status = ?', (tenant_id, 'fulfilled'))
    fulfilled_requests = cursor.fetchone()['fulfilled']
    
    cursor.execute('SELECT COUNT(*) as pending FROM requests WHERE tenant_id = ? AND status = ?', (tenant_id, 'pending'))
    pending_requests = cursor.fetchone()['pending']
    
    # If no requests in requests table, try to get historical data from songs table
    # This handles cases where old requests were deleted but songs.requests counter remains
    if total_requests == 0:
        cursor.execute('SELECT SUM(requests) as total FROM songs WHERE tenant_id = ? AND requests > 0', (tenant_id,))
        result = cursor.fetchone()
        historical_total = result['total'] if result['total'] else 0
        if historical_total > 0:
            # Use historical data as fallback
            total_requests = historical_total
            # We can't know the breakdown, so assume all are fulfilled (historical data)
            fulfilled_requests = historical_total
            pending_requests = 0
    
    # Calculate conversion rate
    conversion_rate = (fulfilled_requests / total_requests * 100) if total_requests > 0 else 0
    
    # Get total tips (if any)
    cursor.execute('SELECT SUM(tip_amount) as total_tips FROM requests WHERE tenant_id = ?', (tenant_id,))
    result = cursor.fetchone()
    total_tips = result['total_tips'] if result['total_tips'] else 0.0
    
    # Get most requested songs
    # First try from requests table, if empty use songs.requests as fallback
    cursor.execute('''
        SELECT s.title, s.author, COUNT(r.id) as request_count
        FROM requests r
        JOIN songs s ON r.song_id = s.id
        WHERE r.tenant_id = ?
        GROUP BY s.id
        ORDER BY request_count DESC
        LIMIT 10
    ''', (tenant_id,))
    top_songs = cursor.fetchall()
    
    # If no songs from requests table, use songs.requests as fallback
    if not top_songs:
        cursor.execute('''
            SELECT title, author, requests as request_count
            FROM songs
            WHERE tenant_id = ? AND requests > 0
            ORDER BY requests DESC
            LIMIT 10
        ''', (tenant_id,))
        top_songs = cursor.fetchall()
    
    # Get recent fulfilled requests
    cursor.execute('''
        SELECT s.title, s.author, r.requester, r.played_at
        FROM requests r
        JOIN songs s ON r.song_id = s.id
        WHERE r.tenant_id = ? AND r.status = ?
        ORDER BY r.played_at DESC
        LIMIT 10
    ''', (tenant_id, 'fulfilled'))
    recent_fulfilled = cursor.fetchall()
    
    conn.close()
    
    stats = {
        'total_requests': total_requests,
        'fulfilled_requests': fulfilled_requests,
        'pending_requests': pending_requests,
        'conversion_rate': round(conversion_rate, 1),
        'total_tips': total_tips,
        'top_songs': top_songs,
        'recent_fulfilled': recent_fulfilled
    }
    
    return render_template('tenant_insights.html', tenant=tenant, stats=stats)

@app.route('/<tenant_slug>/admin')
def tenant_admin(tenant_slug):
    """Tenant admin dashboard."""
    if not session.get('is_tenant_admin') or session.get('tenant_slug') != tenant_slug:
        return redirect(url_for('tenant_login', tenant_slug=tenant_slug))
    
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM tenants WHERE slug = ? AND active = 1', (tenant_slug,))
    tenant = cursor.fetchone()
    
    if not tenant:
        # Tenant was deactivated while admin was logged in
        session.clear()
        conn.close()
        flash('This tenant account has been deactivated')
        return redirect(url_for('index'))
    
    # Get referral stats
    referral_stats = {
        'total': 0,
        'referred_artists': []
    }
    
    cursor.execute('''
        SELECT COUNT(*) as total FROM tenants WHERE referred_by = ?
    ''', (tenant['id'],))
    referral_stats['total'] = cursor.fetchone()['total']
    
    cursor.execute('''
        SELECT name, slug, created_at FROM tenants 
        WHERE referred_by = ? 
        ORDER BY created_at DESC
        LIMIT 10
    ''', (tenant['id'],))
    referral_stats['referred_artists'] = cursor.fetchall()
    
    conn.close()
    
    # Get app URL for referral link display
    app_url = get_app_url()
    
    return render_template('admin.html', tenant=tenant, referral_stats=referral_stats, app_url=app_url)

@app.route('/<tenant_slug>/send_invitation', methods=['POST'])
def tenant_send_invitation(tenant_slug):
    """Send email invitation to a musician."""
    try:
        if not session.get('is_tenant_admin') or session.get('tenant_slug') != tenant_slug:
            return jsonify({'success': False, 'message': 'Unauthorized'}), 403
        
        data = request.get_json()
        if not data or 'email' not in data:
            return jsonify({'success': False, 'message': 'Email address required'}), 400
        
        email = data['email'].strip()
        
        # Validate email format
        import re
        email_regex = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
        if not re.match(email_regex, email):
            return jsonify({'success': False, 'message': 'Invalid email address'}), 400
        
        conn = create_connection()
        cursor = conn.cursor()
        
        # Check if email already exists
        cursor.execute('SELECT id, name FROM tenants WHERE email = ?', (email,))
        existing_user = cursor.fetchone()
        if existing_user:
            conn.close()
            return jsonify({'success': False, 'message': f'This email is already registered by {existing_user["name"]}'}), 400
        
        # Get tenant info
        cursor.execute('SELECT * FROM tenants WHERE slug = ? AND active = 1', (tenant_slug,))
        tenant = cursor.fetchone()
        
        if not tenant:
            conn.close()
            return jsonify({'success': False, 'message': 'Tenant not found'}), 400
        
        # Check if referral code exists
        referral_code = tenant['referral_code'] if 'referral_code' in tenant.keys() else None
        if not referral_code:
            conn.close()
            return jsonify({'success': False, 'message': 'Referral code not available'}), 400
        
        # Build invitation link
        invitation_link = get_app_url() + 'signup?ref=' + referral_code
        
        # Log the invitation
        cursor.execute('''
            INSERT INTO invitations (invited_by, email, status)
            VALUES (?, ?, 'pending')
        ''', (tenant['id'], email))
        conn.commit()
        
        # Close connection
        conn.close()
        
        # Try to send email, but if it fails just return the link
        email_sent = False
        
        try:
            from flask_mail import Message
            
            subject = f"{tenant['name']} invites you to try Setly!"
            body = f"""Hi!

{tenant['name']} thinks you would love Setly - the platform that lets musicians manage their song requests and connect with fans.

Click here to create your free account:
{invitation_link}

Best regards,
The Setly Team
"""
            
            html_body = f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #2c3e50;">You're Invited to Setly!</h2>
                    <p>Hi!</p>
                    <p><strong>{tenant['name']}</strong> thinks you would love <strong>Setly</strong> - the platform that lets musicians manage their song requests and connect with fans.</p>
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{invitation_link}" style="display: inline-block; padding: 15px 30px; background-color: #2c3e50; color: white; text-decoration: none; border-radius: 5px; font-weight: bold;">Create Your Free Account</a>
                    </div>
                    <p style="color: #7f8c8d; font-size: 14px;">Or copy and paste this link: <a href="{invitation_link}">{invitation_link}</a></p>
                    <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
                    <p style="color: #95a5a6; font-size: 12px;">Best regards,<br>The Setly Team</p>
                </div>
            </body>
            </html>
            """
            
            msg = Message(
                subject=subject,
                recipients=[email],
                body=body,
                html=html_body
            )
            
            try:
                mail.send(msg)
                email_sent = True
            except Exception as mail_error:
                # Email sending failed (likely not configured in dev), but link is still valid
                app.logger.warning(f'Email not sent (mail server not configured): {str(mail_error)}')
            
        except Exception as e:
            app.logger.error(f'Error preparing email: {str(e)}')
        
        # Return appropriate response
        if email_sent:
            return jsonify({'success': True, 'message': f'Invitation email sent to {email}! They will appear in your referrals list once they sign up.'})
        else:
            return jsonify({
                'success': True, 
                'message': f'Invitation link created! Share this link with {email}: {invitation_link} (They will appear in your referrals list once they sign up)'
            })
            
    except Exception as e:
        # Catch ANY exception and always return JSON
        app.logger.error(f'Unexpected error in send_invitation: {str(e)}')
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Server error: {str(e)}'}), 500


@app.route('/<tenant_slug>/populate_sample_songs', methods=['POST'])
def tenant_populate_sample_songs(tenant_slug):
    """Populate tenant's database with sample songs."""
    if not session.get('is_tenant_admin') or session.get('tenant_slug') != tenant_slug:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    import csv
    
    conn = create_connection()
    cursor = conn.cursor()
    
    # Get tenant info
    cursor.execute('SELECT * FROM tenants WHERE slug = ? AND active = 1', (tenant_slug,))
    tenant = cursor.fetchone()
    
    if not tenant:
        conn.close()
        return jsonify({'success': False, 'message': 'Tenant not found'}), 404
    
    tenant_id = tenant['id']
    
    # Read sample songs from CSV
    sample_songs_file = os.path.join(os.path.dirname(__file__), 'sample_songs.csv')
    
    try:
        with open(sample_songs_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            songs_added = 0
            for row in reader:
                # Insert sample song for this tenant with empty image string
                # This allows Spotify bulk fetch to download real images
                cursor.execute('''
                    INSERT INTO songs (title, author, language, genre, image, tenant_id, is_sample, popularity)
                    VALUES (?, ?, ?, ?, '', ?, 1, 0)
                ''', (row['title'], row['author'], row['language'], row['genre'], tenant_id))
                songs_added += 1
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True, 
            'message': f'{songs_added} sample songs added successfully!',
            'count': songs_added
        })
        
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500

@app.route('/<tenant_slug>/delete_sample_songs', methods=['POST'])
def tenant_delete_sample_songs(tenant_slug):
    """Delete all sample songs for this tenant."""
    if not session.get('is_tenant_admin') or session.get('tenant_slug') != tenant_slug:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    conn = create_connection()
    cursor = conn.cursor()
    
    # Get tenant info
    cursor.execute('SELECT * FROM tenants WHERE slug = ? AND active = 1', (tenant_slug,))
    tenant = cursor.fetchone()
    
    if not tenant:
        conn.close()
        return jsonify({'success': False, 'message': 'Tenant not found'}), 404
    
    tenant_id = tenant['id']
    
    # Delete sample songs for this tenant
    cursor.execute('DELETE FROM songs WHERE tenant_id = ? AND is_sample = 1', (tenant_id,))
    deleted_count = cursor.rowcount
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'success': True, 
        'message': f'{deleted_count} sample songs deleted successfully!',
        'count': deleted_count
    })

@app.route('/<tenant_slug>/delete_all_songs', methods=['POST'])
def tenant_delete_all_songs(tenant_slug):
    """Delete all songs for this tenant."""
    if not session.get('is_tenant_admin') or session.get('tenant_slug') != tenant_slug:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    conn = create_connection()
    cursor = conn.cursor()
    
    # Get tenant info
    cursor.execute('SELECT * FROM tenants WHERE slug = ? AND active = 1', (tenant_slug,))
    tenant = cursor.fetchone()
    
    if not tenant:
        conn.close()
        return jsonify({'success': False, 'message': 'Tenant not found'}), 404
    
    tenant_id = tenant['id']
    
    try:
        # Get count before deletion
        cursor.execute('SELECT COUNT(*) as count FROM songs WHERE tenant_id = ?', (tenant_id,))
        count = cursor.fetchone()['count']
        
        # Delete all requests for this tenant's songs first
        cursor.execute('DELETE FROM requests WHERE tenant_id = ?', (tenant_id,))
        
        # Delete all songs for this tenant
        cursor.execute('DELETE FROM songs WHERE tenant_id = ?', (tenant_id,))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True, 
            'message': f'Successfully deleted {count} song(s) and all associated requests',
            'count': count
        })
        
    except Exception as e:
        conn.close()
        return jsonify({
            'success': False, 
            'message': f'Error deleting songs: {str(e)}'
        }), 500

@app.route('/<tenant_slug>/remove_duplicates', methods=['POST'])
def tenant_remove_duplicates(tenant_slug):
    """Find and remove duplicate songs for this tenant (keeps oldest entry)."""
    if not session.get('is_tenant_admin') or session.get('tenant_slug') != tenant_slug:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    conn = create_connection()
    cursor = conn.cursor()
    
    # Get tenant info
    cursor.execute('SELECT * FROM tenants WHERE slug = ? AND active = 1', (tenant_slug,))
    tenant = cursor.fetchone()
    
    if not tenant:
        conn.close()
        return jsonify({'success': False, 'message': 'Tenant not found'}), 404
    
    tenant_id = tenant['id']
    
    try:
        # Find duplicates: songs with same title and author (case-insensitive)
        # Keep the oldest (MIN(id)), delete the rest
        cursor.execute('''
            SELECT LOWER(title) as title_lower, LOWER(author) as author_lower, 
                   COUNT(*) as count, GROUP_CONCAT(id) as ids,
                   GROUP_CONCAT(title) as titles,
                   GROUP_CONCAT(author) as authors
            FROM songs 
            WHERE tenant_id = ?
            GROUP BY LOWER(title), LOWER(author)
            HAVING COUNT(*) > 1
        ''', (tenant_id,))
        
        duplicates = cursor.fetchall()
        
        if not duplicates:
            conn.close()
            return jsonify({
                'success': True,
                'message': 'No duplicate songs found!',
                'count': 0,
                'duplicates': []
            })
        
        deleted_songs = []
        total_deleted = 0
        
        for dup in duplicates:
            ids = [int(x) for x in dup['ids'].split(',')]
            titles = dup['titles'].split(',')
            authors = dup['authors'].split(',')
            
            # Keep the first (oldest) ID, delete the rest
            keep_id = min(ids)
            delete_ids = [x for x in ids if x != keep_id]
            
            if delete_ids:
                # Delete associated requests first
                placeholders = ','.join('?' * len(delete_ids))
                cursor.execute(f'DELETE FROM requests WHERE song_id IN ({placeholders})', delete_ids)
                
                # Delete duplicate songs
                cursor.execute(f'DELETE FROM songs WHERE id IN ({placeholders})', delete_ids)
                
                deleted_songs.append({
                    'title': titles[0],
                    'author': authors[0],
                    'kept_id': keep_id,
                    'deleted_ids': delete_ids,
                    'count': len(delete_ids)
                })
                
                total_deleted += len(delete_ids)
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'Successfully removed {total_deleted} duplicate song(s) across {len(duplicates)} group(s)',
            'count': total_deleted,
            'groups': len(duplicates),
            'duplicates': deleted_songs[:10]  # Return first 10 for display
        })
        
    except Exception as e:
        conn.close()
        app.logger.error(f"Error removing duplicates: {e}")
        return jsonify({
            'success': False,
            'message': f'Error removing duplicates: {str(e)}'
        }), 500

@app.route('/<tenant_slug>/update_logo', methods=['POST'])
def tenant_update_logo(tenant_slug):
    """Update tenant logo image."""
    if not session.get('is_tenant_admin') or session.get('tenant_slug') != tenant_slug:
        return redirect(url_for('tenant_login', tenant_slug=tenant_slug))
    
    if 'logo' not in request.files:
        flash('No logo file uploaded', 'error')
        return redirect(url_for('tenant_admin', tenant_slug=tenant_slug))
    
    file = request.files['logo']
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('tenant_admin', tenant_slug=tenant_slug))
    
    if file:
        # Validate file type
        allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
        if '.' not in file.filename or file.filename.rsplit('.', 1)[1].lower() not in allowed_extensions:
            flash('Invalid file type. Please upload an image file.', 'error')
            return redirect(url_for('tenant_admin', tenant_slug=tenant_slug))
        
        # Get tenant info
        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM tenants WHERE slug = ?', (tenant_slug,))
        tenant = cursor.fetchone()
        
        if not tenant:
            flash('Tenant not found', 'error')
            conn.close()
            return redirect(url_for('tenant_admin', tenant_slug=tenant_slug))
        
        tenant_id = tenant['id']
        
        # Generate unique filename
        file_ext = file.filename.rsplit('.', 1)[1].lower()
        unique_filename = f"logo_{int(time.time())}.{file_ext}"
        
        # Save to tenant-specific logos directory
        from utils.tenant_utils import get_tenant_dir
        logos_dir = get_tenant_dir(app, tenant_slug, 'logos')
        file_path = os.path.join(logos_dir, unique_filename)
        file.save(file_path)
        
        # Update database with relative path
        relative_path = f"tenants/{tenant_slug}/logos/{unique_filename}"
        cursor.execute('UPDATE tenants SET logo_image = ? WHERE id = ?', (relative_path, tenant_id))
        conn.commit()
        conn.close()
        
        flash('Logo updated successfully!', 'success')
    
    return redirect(url_for('tenant_admin', tenant_slug=tenant_slug))

@app.route('/<tenant_slug>/update_banner', methods=['POST'])
def tenant_update_banner(tenant_slug):
    """Update tenant welcome banner image."""
    if not session.get('is_tenant_admin') or session.get('tenant_slug') != tenant_slug:
        return redirect(url_for('tenant_login', tenant_slug=tenant_slug))
    
    if 'banner' not in request.files:
        flash('No banner file uploaded', 'error')
        return redirect(url_for('tenant_admin', tenant_slug=tenant_slug))
    
    file = request.files['banner']
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('tenant_admin', tenant_slug=tenant_slug))
    
    if file:
        # Validate file type
        allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
        if '.' not in file.filename or file.filename.rsplit('.', 1)[1].lower() not in allowed_extensions:
            flash('Invalid file type. Please upload an image file.', 'error')
            return redirect(url_for('tenant_admin', tenant_slug=tenant_slug))
        
        # Get tenant info
        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM tenants WHERE slug = ?', (tenant_slug,))
        tenant = cursor.fetchone()
        
        if not tenant:
            flash('Tenant not found', 'error')
            conn.close()
            return redirect(url_for('tenant_admin', tenant_slug=tenant_slug))
        
        tenant_id = tenant['id']
        
        # Generate unique filename
        file_ext = file.filename.rsplit('.', 1)[1].lower()
        unique_filename = f"banner_{int(time.time())}.{file_ext}"
        
        # Save to tenant-specific images directory
        from utils.tenant_utils import get_tenant_dir
        images_dir = get_tenant_dir(app, tenant_slug, 'images')
        file_path = os.path.join(images_dir, unique_filename)
        file.save(file_path)
        
        # Update database with relative path
        relative_path = f"tenants/{tenant_slug}/images/{unique_filename}"
        cursor.execute('UPDATE tenants SET banner_image = ? WHERE id = ?', (relative_path, tenant_id))
        conn.commit()
        conn.close()
        
        flash('Banner updated successfully!', 'success')
    
    return redirect(url_for('tenant_admin', tenant_slug=tenant_slug))

@app.route('/<tenant_slug>/update_website', methods=['POST'])
def tenant_update_website(tenant_slug):
    """Update tenant website URL."""
    if not session.get('is_tenant_admin') or session.get('tenant_slug') != tenant_slug:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    data = request.get_json()
    website_url = data.get('website_url', '').strip()
    
    conn = create_connection()
    cursor = conn.cursor()
    
    try:
        tenant_id = session.get('tenant_id')
        cursor.execute('UPDATE tenants SET website_url = ? WHERE id = ?', (website_url, tenant_id))
        conn.commit()
        return jsonify({'success': True, 'message': 'Website URL updated successfully'})
    except Exception as e:
        print(f"Error updating website URL: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        conn.close()

@app.route('/<tenant_slug>/update_events', methods=['POST'])
def tenant_update_events(tenant_slug):
    """Update tenant events link."""
    if not session.get('is_tenant_admin') or session.get('tenant_slug') != tenant_slug:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    data = request.get_json()
    events_link = data.get('events_link', '').strip()
    
    conn = create_connection()
    cursor = conn.cursor()
    
    try:
        tenant_id = session.get('tenant_id')
        cursor.execute('UPDATE tenants SET events_link = ? WHERE id = ?', (events_link, tenant_id))
        conn.commit()
        return jsonify({'success': True, 'message': 'Events link updated successfully'})
    except Exception as e:
        print(f"Error updating events link: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        conn.close()

@app.route('/<tenant_slug>/update_bio', methods=['POST'])
def tenant_update_bio(tenant_slug):
    """Update tenant artist name and bio/description."""
    if not session.get('is_tenant_admin') or session.get('tenant_slug') != tenant_slug:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    data = request.get_json()
    artist_name = data.get('artist_name', '').strip()
    bio = data.get('bio', '').strip()
    
    conn = create_connection()
    cursor = conn.cursor()
    
    try:
        tenant_id = session.get('tenant_id')
        cursor.execute('UPDATE tenants SET name = ?, bio = ? WHERE id = ?', (artist_name, bio, tenant_id))
        conn.commit()
        return jsonify({'success': True, 'message': 'Artist info updated successfully'})
    except Exception as e:
        print(f"Error updating artist info: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        conn.close()

@app.route('/<tenant_slug>/start_gig', methods=['POST'])
def tenant_start_gig(tenant_slug):
    """Start a new gig for the tenant."""
    try:
        from utils.audit_logger import log_tenant_admin_action
    except ImportError:
        log_tenant_admin_action = None
        app.logger.warning("audit_logger not available, skipping logging")
    
    # Always return JSON, even on errors
    try:
        if not session.get('is_tenant_admin') or session.get('tenant_slug') != tenant_slug:
            return jsonify({'success': False, 'message': 'Unauthorized'}), 403
        
        data = request.get_json()
        if data and data.get('gig_name'):
            gig_name = str(data.get('gig_name')).strip() or None
        else:
            gig_name = None
        
        # Get tip_enabled from request (default to True if not provided)
        tip_enabled = True
        if data and 'tip_enabled' in data:
            tip_enabled = bool(data.get('tip_enabled'))
        
        tenant_id = session.get('tenant_id')
        if not tenant_id:
            return jsonify({'success': False, 'message': 'Tenant ID not found'}), 400
        
        # Ensure gigs table exists before trying to start gig
        try:
            ensure_gigs_table_once()
            # Also ensure tip_intents table exists
            ensure_tip_intents_table_once()
        except Exception as ensure_error:
            app.logger.error(f"Error ensuring tables: {ensure_error}")
            # Continue anyway, start_gig will handle the error
        
        # If tips are enabled, check PayPal configuration
        if tip_enabled:
            paypal_client_id = os.environ.get('PAYPAL_CLIENT_ID')
            paypal_client_secret = os.environ.get('PAYPAL_CLIENT_SECRET')
            if not paypal_client_id or not paypal_client_secret:
                app.logger.warning("PayPal not configured but tips are enabled for this gig")
                # Don't fail, just warn - tips will fail when user tries to use them
        
        gig_id = start_gig(tenant_id, gig_name if gig_name else None, tip_enabled)
        
        if gig_id:
            # Retrieve the gig directly by ID instead of using get_active_gig
            conn = create_connection()
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT * FROM gigs WHERE id = ?", (gig_id,))
                gig = cursor.fetchone()
                if gig:
                    active_gig = dict(gig)
                else:
                    app.logger.error(f"Gig {gig_id} was created but could not be retrieved")
                    conn.close()
                    return jsonify({'success': False, 'message': 'Gig started but could not be retrieved. Please refresh the page.'}), 500
            except Exception as db_error:
                app.logger.error(f"Error retrieving gig {gig_id}: {db_error}", exc_info=True)
                conn.close()
                return jsonify({'success': False, 'message': f'Error retrieving gig details: {str(db_error)}'}), 500
            finally:
                conn.close()
            
            # Log gig started (async - non-blocking)
            if log_tenant_admin_action:
                try:
                    log_tenant_admin_action(
                        action='gig_started',
                        entity_type='gig',
                        entity_id=gig_id,
                        gig_name=active_gig['name'],
                        gig_start_time=active_gig['start_time']
                    )
                except Exception as log_error:
                    # Don't fail the request if logging fails
                    app.logger.warning(f"Failed to log gig started: {log_error}")
            
            return jsonify({
                'success': True, 
                'message': 'Gig started successfully',
                'gig': {
                    'id': active_gig['id'],
                    'name': active_gig['name'],
                    'start_time': active_gig['start_time'],
                    'tip_enabled': active_gig.get('tip_enabled', 1) == 1
                }
            })
        else:
            return jsonify({'success': False, 'message': 'Failed to start gig. The gigs table may not exist. Please run the migration script.'}), 500
    except Exception as e:
        app.logger.error(f"Error in tenant_start_gig: {e}", exc_info=True)
        import traceback
        app.logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({'success': False, 'message': f'Error starting gig: {str(e)}'}), 500

@app.route('/<tenant_slug>/end_gig', methods=['POST'])
def tenant_end_gig(tenant_slug):
    """End the currently active gig for the tenant."""
    try:
        from utils.audit_logger import log_tenant_admin_action
    except ImportError:
        log_tenant_admin_action = None
    
    if not session.get('is_tenant_admin') or session.get('tenant_slug') != tenant_slug:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    tenant_id = session.get('tenant_id')
    if not tenant_id:
        return jsonify({'success': False, 'message': 'Tenant ID not found'}), 400
    
    # Get gig info before ending
    active_gig = get_active_gig(tenant_id)
    gig_id = active_gig['id'] if active_gig else None
    gig_name = active_gig['name'] if active_gig else None
    
    success = end_gig(tenant_id)
    
    if success:
        # Get request count for this gig
        request_count = None
        if gig_id:
            conn = create_connection()
            cursor = conn.cursor()
            try:
                cursor.execute('SELECT COUNT(*) as count FROM requests WHERE gig_id = ?', (gig_id,))
                result = cursor.fetchone()
                request_count = result['count'] if result else 0
            except:
                request_count = None
            finally:
                conn.close()
        
        # Log gig ended (async - non-blocking)
        if log_tenant_admin_action:
            log_tenant_admin_action(
                action='gig_ended',
            entity_type='gig',
            entity_id=gig_id,
                gig_name=gig_name,
                total_requests=request_count
            )
        
        return jsonify({'success': True, 'message': 'Gig ended successfully'})
    else:
        return jsonify({'success': False, 'message': 'No active gig to end or gigs table does not exist'}), 400

@app.route('/<tenant_slug>/get_active_gig', methods=['GET'])
def tenant_get_active_gig(tenant_slug):
    """Get the currently active gig for the tenant."""
    # Get tenant_id from slug (more reliable than session)
    conn = create_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT id FROM tenants WHERE slug = ? AND active = 1', (tenant_slug,))
        tenant = cursor.fetchone()
        if not tenant:
            conn.close()
            return jsonify({'success': False, 'message': 'Tenant not found'}), 404
        
        tenant_id = tenant['id']
        
        # Also update session for consistency
        session['tenant_id'] = tenant_id
        session['tenant_slug'] = tenant_slug
        
        active_gig = get_active_gig(tenant_id)
        
        # Get tenant PayPal link
        cursor.execute('SELECT paypal_link FROM tenants WHERE id = ?', (tenant_id,))
        tenant_data = cursor.fetchone()
        paypal_link = tenant_data['paypal_link'] if tenant_data else None
        
        if active_gig:
            return jsonify({
                'success': True,
                'gig': {
                    'id': active_gig['id'],
                    'name': active_gig['name'],
                    'start_time': active_gig['start_time'],
                    'announcement': active_gig.get('announcement', ''),
                    'tip_enabled': active_gig.get('tip_enabled', 1) == 1
                },
                'paypal_link': paypal_link
            })
        else:
            return jsonify({
                'success': True, 
                'gig': None,
                'paypal_link': paypal_link
            })
    finally:
        conn.close()

@app.route('/<tenant_slug>/send_announcement', methods=['POST'])
def tenant_send_announcement(tenant_slug):
    """Send an announcement message to the current audience."""
    if not session.get('is_tenant_admin') or session.get('tenant_slug') != tenant_slug:
        return jsonify({'success': False, 'message': _('Unauthorized')}), 403
    
    data = request.get_json()
    announcement = data.get('announcement', '').strip() if data else ''
    
    tenant_id = session.get('tenant_id')
    if not tenant_id:
        return jsonify({'success': False, 'message': _('Tenant ID not found')}), 400
    
    # Get active gig
    active_gig = get_active_gig(tenant_id)
    if not active_gig:
        return jsonify({'success': False, 'message': _('No active gig. Start a gig first.')}), 400
    
    # Update announcement in the active gig
    conn = create_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE gigs 
            SET announcement = ? 
            WHERE id = ? AND tenant_id = ? AND is_active = 1
        """, (announcement if announcement else None, active_gig['id'], tenant_id))
        conn.commit()
        
        if announcement:
            return jsonify({
                'success': True, 
                'message': _('Announcement sent successfully')
            })
        else:
            return jsonify({
                'success': True, 
                'message': _('Announcement cleared')
            })
    except Exception as e:
        app.logger.error(f"Error updating announcement: {e}", exc_info=True)
        conn.rollback()
        return jsonify({'success': False, 'message': _('Error sending announcement')}), 500
    finally:
        conn.close()

@app.route('/<tenant_slug>/update_tip_enabled', methods=['POST'])
def tenant_update_tip_enabled(tenant_slug):
    """Update tip_enabled setting for the active gig."""
    if not session.get('is_tenant_admin') or session.get('tenant_slug') != tenant_slug:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    tenant_id = session.get('tenant_id')
    if not tenant_id:
        return jsonify({'success': False, 'message': 'Tenant ID not found'}), 400
    
    try:
        data = request.get_json()
        tip_enabled = bool(data.get('tip_enabled', True))
        
        active_gig = get_active_gig(tenant_id)
        if not active_gig:
            return jsonify({'success': False, 'message': 'No active gig found'}), 404
        
        gig_id = active_gig['id']
        tip_enabled_int = 1 if tip_enabled else 0
        
        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE gigs 
            SET tip_enabled = ?
            WHERE id = ? AND tenant_id = ?
        """, (tip_enabled_int, gig_id, tenant_id))
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True, 
            'message': 'Tip setting updated successfully',
            'tip_enabled': tip_enabled
        })
    except Exception as e:
        app.logger.error(f"Error updating tip_enabled: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/<tenant_slug>/update_default_language', methods=['POST'])
def tenant_update_default_language(tenant_slug):
    """Update tenant default language."""
    if not session.get('is_tenant_admin') or session.get('tenant_slug') != tenant_slug:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    data = request.get_json()
    default_language = data.get('default_language', 'en').strip()
    
    # Validate language code
    valid_languages = ['en', 'it', 'fr', 'de', 'es']
    if default_language not in valid_languages:
        return jsonify({'success': False, 'message': 'Invalid language code'}), 400
    
    conn = create_connection()
    cursor = conn.cursor()
    
    try:
        tenant_id = session.get('tenant_id')
        cursor.execute('UPDATE tenants SET default_language = ? WHERE id = ?', (default_language, tenant_id))
        conn.commit()
        return jsonify({'success': True, 'message': 'Default language updated successfully'})
    except Exception as e:
        print(f"Error updating default language: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        conn.close()

@app.route('/<tenant_slug>/songs')
def tenant_songs(tenant_slug):
    """Tenant-specific songs management page."""
    if not session.get('is_tenant_admin') or session.get('tenant_slug') != tenant_slug:
        return redirect(url_for('tenant_login', tenant_slug=tenant_slug))
    
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM tenants WHERE slug = ? AND active = 1', (tenant_slug,))
    tenant = cursor.fetchone()
    
    if not tenant:
        # Tenant was deactivated while admin was logged in
        session.clear()
        conn.close()
        flash('This tenant account has been deactivated')
        return redirect(url_for('index'))
    
    # Ensure tenant_id is in session for API endpoints
    session['tenant_id'] = tenant['id']
    session['tenant_slug'] = tenant_slug
    
    conn.close()
    return render_template('songs.html', tenant=tenant)

@app.route('/<tenant_slug>/queue', methods=['GET', 'POST'])
def tenant_queue(tenant_slug):
    """Tenant-specific queue page."""
    if not session.get('is_tenant_admin') or session.get('tenant_slug') != tenant_slug:
        return redirect(url_for('tenant_login', tenant_slug=tenant_slug))
    
    is_admin = True
    current_datetime = format_datetime(datetime.now())
    
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM tenants WHERE slug = ? AND active = 1', (tenant_slug,))
    tenant = cursor.fetchone()
    
    if not tenant:
        # Tenant was deactivated while admin was logged in
        session.clear()
        conn.close()
        flash('This tenant account has been deactivated')
        return redirect(url_for('index'))
    
    conn.close()
    
    tenant_id = tenant['id']
    venue_name = get_venue_name(tenant_id)
    max_requests = get_setting('max_requests_per_user', tenant_id)
    
    # Get active gig info
    active_gig = get_active_gig(tenant_id)
    
    return render_template('queue.html', is_admin=is_admin, current_datetime=current_datetime, venue_name=venue_name, max_requests=max_requests, tenant=tenant, active_gig=active_gig)

@app.route('/<tenant_slug>/help')
def tenant_help(tenant_slug):
    """Tenant-specific help page."""
    # Get tenant info
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM tenants WHERE slug = ? AND active = 1', (tenant_slug,))
    tenant = cursor.fetchone()
    conn.close()
    
    if not tenant:
        flash('Tenant not found or inactive')
        return redirect(url_for('index'))
    
    # Get user_name from session
    user_name = session.get('user_name', '')
    # Get language from request parameter or session
    language = request.args.get('lang', session.get('language', 'en'))
    session['language'] = language
    
    return render_template('help.html', tenant=tenant, user_name=user_name, language=language)

@app.route('/<tenant_slug>/logout_user', methods=['GET', 'POST'])
def tenant_logout_user(tenant_slug):
    """Logout end user - clear name and return to home."""
    try:
        from utils.audit_logger import log_event
    except ImportError:
        log_event = None
    
    # Get session info before clearing
    user_session_id = session.get('user_session_id')
    tenant_id = session.get('tenant_id')
    user_name = session.get('user_name')
    
    # Calculate session duration if we have session start time
    session_duration = None
    if user_session_id and 'user_session_id' in session:
        try:
            # Extract timestamp from session_id (format: tenant_id-YYYYMMDDHHMMSS-random)
            timestamp_str = user_session_id.split('-')[1] if len(user_session_id.split('-')) > 1 else None
            if timestamp_str and len(timestamp_str) == 14:
                from datetime import datetime
                session_start = datetime.strptime(timestamp_str, '%Y%m%d%H%M%S')
                session_duration = int((datetime.now() - session_start).total_seconds())
        except:
            pass
    
    # Log session end before clearing (async - non-blocking)
    if user_session_id and log_event:
        log_event(
            action='user_session_end',
            entity_type='session',
            tenant_id=tenant_id,
            user_type='end_user',
            user_session_id=user_session_id,
            details={
                'tenant_slug': tenant_slug,
                'user_name': user_name,
                'session_duration_seconds': session_duration
            }
        )
    
    # Clear user name from session
    session.pop('user_name', None)
    session.pop('last_visited', None)
    session.pop('user_session_id', None)
    
    # Redirect to home page
    return redirect(url_for('tenant_home', tenant_slug=tenant_slug))

@app.route('/<tenant_slug>/search', methods=['GET', 'POST'])
def tenant_search(tenant_slug):
    """Tenant-specific search page."""
    try:
        from utils.audit_logger import log_user_action
    except ImportError:
        log_user_action = None
        app.logger.warning("audit_logger not available, skipping logging")
    import time
    
    start_time = time.time()
    
    # Get tenant info
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM tenants WHERE slug = ? AND active = 1', (tenant_slug,))
    tenant = cursor.fetchone()
    conn.close()
    
    if not tenant:
        flash('Tenant not found or inactive')
        return redirect(url_for('index'))
    
    # Ensure tenant_id is in session
    session['tenant_id'] = tenant['id']
    session['tenant_slug'] = tenant_slug
    
    # Get active gig info (for displaying status to users)
    active_gig = get_active_gig(tenant['id'])
    
    # Check if there's an active gig when user tries to access search page
    # If no active gig and user has a name (wants to request songs), redirect to scan_qr
    try:
        if not active_gig:
            user_name = request.form.get('user_name', request.args.get('user_name', session.get('user_name', '')))
            # If user has a name, they're trying to request songs - redirect them
            if user_name:
                flash(_('No active gig. Please wait for the musician to start the gig.'), 'info')
                session['user_name'] = ''  # Clear user name to force re-scan
                return redirect(url_for('tenant_scan_qr', tenant_slug=tenant_slug))
            # If no name, allow access to see the page (they need to enter name first)
        else:
            # Verify user has scanned QR code for the current active gig
            session_gig_id = session.get('gig_id')
            if session_gig_id != active_gig['id']:
                # User hasn't scanned QR code for this gig - redirect to scan_qr
                flash(_('A new musical event has started. Please scan the QR code to participate.'), 'info')
                session.pop('user_name', None)  # Clear user name to force re-entry
                return redirect(url_for('tenant_scan_qr', tenant_slug=tenant_slug))
    except Exception:
        # If gigs table doesn't exist yet, allow access (backward compatibility)
        pass
    
    user_name = request.form.get('user_name', request.args.get('user_name', session.get('user_name', '')))
    language = request.form.get('lang', request.args.get('lang', session.get('language', 'en')))
    search_query = request.args.get('s', '')
    
    # Set session variables
    session['user_name'] = user_name
    session['language'] = language
    
    app.logger.debug(f'Loading Search.html for tenant: {tenant_slug}, user: {user_name}, tenant_id: {tenant["id"]}')
    
    # Check if the username is empty
    if user_name == '':
        app.logger.debug(f'Rendering Search.html without request ability for tenant_id: {tenant["id"]}')
        songs = fetch_songs('all', search_query, language, tenant_id=tenant['id'])
        app.logger.debug(f'Found {len(songs)} songs for tenant_id: {tenant["id"]}')
        
        # Log search if query is provided (async - non-blocking)
        if search_query and log_user_action:
            duration_ms = int((time.time() - start_time) * 1000)
            log_user_action(
                action='search_performed',
                entity_type='search',
                search_query=search_query,
                language=language,
                results_count=len(songs),
                duration_ms=duration_ms
            )
        
        return render_template('search.html', user_name=user_name, language=language, songs=songs, can_request_songs=False, tenant=tenant, active_gig=active_gig)
    
    # If username is not empty, check if the session is valid
    if not is_session_valid():
        # Reset username and redirect if session is not valid
        app.logger.debug(f'redirecting to scan_qr for user: {user_name}')
        session['user_name'] = ''
        return redirect(url_for('scan_qr'))
    
    # If session is valid and username is not empty, fetch and render the search page with song data
    # Pass user_name to exclude songs already requested by this user
    songs = fetch_songs('all', search_query, language, tenant_id=tenant['id'], user_name=user_name)
    
    # Log search if query is provided (async - non-blocking)
    if search_query and log_user_action:
        duration_ms = int((time.time() - start_time) * 1000)
        log_user_action(
            action='search_performed',
            entity_type='search',
            search_query=search_query,
            language=language,
            results_count=len(songs),
            duration_ms=duration_ms
        )
    
    return render_template('search.html', user_name=user_name, language=language, songs=songs, can_request_songs=True, tenant=tenant, active_gig=active_gig)


@app.route('/popular')
def popular():
    return render_template('popular.html')  # Ensure you have a popular.html template

@app.route('/about.html')
def about():
    return render_template('about.html')  # Ensure you have an about.html template

@app.before_request
def before_request():
    g.lang_code = session.get('language', 'en')
    

#--------------------------------------------- Database management Functions  ---------------------------------------------
def create_connection():
    """Create a database connection to the SQLite database."""
    database_path = os.path.join(os.path.dirname(__file__), 'songs.db')
    conn = None
    try:
        conn = sqlite3.connect(database_path)
        conn.row_factory = sqlite3.Row  # Configure to return rows as dictionaries
        #  logging.info("Connection very successful!")
    except Exception as e:
        logging.error(f"Failed to connect to the database: {e}")
    return conn

def get_app_url():
    """Get the application URL from system settings, fallback to request.url_root."""
    try:
        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT value FROM system_settings WHERE key = ?', ('app_url',))
        result = cursor.fetchone()
        conn.close()
        if result and result['value']:
            # Ensure URL ends with /
            url = result['value']
            return url if url.endswith('/') else url + '/'
    except Exception as e:
        app.logger.warning(f"Failed to get app_url from settings: {e}")
    
    # Fallback to request context if available
    try:
        return request.url_root
    except:
        return 'http://localhost:5001/'  # Last resort fallback

class Songs(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    author = db.Column(db.String(200), nullable=False)
    image = db.Column(db.String(200))
    popularity = db.Column(db.Integer, default=0)

class Requests(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    song_id = db.Column(db.Integer, db.ForeignKey('songs.id'), nullable=False)
    requester = db.Column(db.String(200), nullable=False)
    request_time = db.Column(db.DateTime, default=datetime.utcnow)

def execute_query(query, args=()):
    conn = create_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute(query, args)
            conn.commit()
            return cur.lastrowid
        except sqlite3.Error as e:
            logging.error(f"Error executing query: {e}")
        finally:
            conn.close()
    return None

def fetch_results(query, args=()):
    conn = create_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute(query, args)
            rows = cur.fetchall()
            return rows
        except sqlite3.Error as e:
            logging.error(f"Error fetching results: {e}")
        finally:
            conn.close()
    return []

def create_tables():
    sql_create_songs_table = """
    CREATE TABLE IF NOT EXISTS songs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        author TEXT NOT NULL,
        language TEXT NOT NULL,
        image TEXT NOT NULL,
        popularity INTEGER NOT NULL DEFAULT 0
    );
    """

    sql_create_requests_table = """
    CREATE TABLE IF NOT EXISTS requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        song_id INTEGER NOT NULL,
        requester TEXT NOT NULL,
        request_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(song_id) REFERENCES songs(id)
    );
    """

    sql_create_settings_table = """
    CREATE TABLE IF NOT EXISTS settings (
        setting_key TEXT PRIMARY KEY,
        setting_value TEXT NOT NULL
    );
    """

    execute_query(sql_create_songs_table)
    execute_query(sql_create_requests_table)
    execute_query(sql_create_settings_table)

    if not fetch_results("SELECT * FROM settings WHERE setting_key = 'max_requests_per_user'"):
        execute_query("INSERT INTO settings (setting_key, setting_value) VALUES (?, ?)", ('max_requests_per_user', '3'))

create_tables()

def get_setting(setting_key, tenant_id=None):
    """Get a setting value, optionally filtered by tenant_id."""
    # Map setting keys to tenant table columns
    tenant_column_map = {
        'max_requests_per_user': 'max_requests',
        'venue_name': 'venue_name'
    }
    
    if tenant_id and setting_key in tenant_column_map:
        # Get from tenants table
        column = tenant_column_map[setting_key]
        result = fetch_results(f"SELECT {column} FROM tenants WHERE id = ?", (tenant_id,))
        if result and result[0][column] is not None:
            return str(result[0][column])
    
    # Fallback to global settings table
    result = fetch_results("SELECT setting_value FROM settings WHERE setting_key = ? AND tenant_id IS NULL", (setting_key,))
    if result:
        return result[0]['setting_value']
    
    # Return default values if no setting found
    defaults = {
        'max_requests_per_user': '3',
        'venue_name': 'Music Venue'
    }
    return defaults.get(setting_key, None)

def count_user_requests(user_name, tenant_id=None, gig_id=None):
    """
    Count user requests. By default counts only pending requests.
    If gig_id is provided, counts only pending requests for that gig.
    """
    # Build query to count only pending requests
    if tenant_id and gig_id:
        # Count pending requests for specific gig
        result = fetch_results(
            "SELECT COUNT(*) AS request_count FROM requests WHERE requester = ? AND tenant_id = ? AND gig_id = ? AND status = ?",
            (user_name, tenant_id, gig_id, 'pending')
        )
    elif tenant_id:
        # Count pending requests for tenant (all gigs)
        result = fetch_results(
            "SELECT COUNT(*) AS request_count FROM requests WHERE requester = ? AND tenant_id = ? AND status = ?",
            (user_name, tenant_id, 'pending')
        )
    else:
        # Count all pending requests (no tenant filter)
        result = fetch_results(
            "SELECT COUNT(*) AS request_count FROM requests WHERE requester = ? AND status = ?",
            (user_name, 'pending')
        )
    
    if result:
        return result[0]['request_count']
    return 0

@app.route('/set_timestamp', methods=['POST'])
def set_timestamp():
    timestamp = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    session['last_visited'] = timestamp
    return jsonify({"status": "success"})









@app.route('/get_queue', methods=['GET'])
@limiter.exempt  # Exempt from rate limiting - read-only endpoint, called frequently for queue updates
def get_queue():
    tenant_id = session.get('tenant_id')
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT s.id as song_id, s.title, s.author, s.image, GROUP_CONCAT(r.requester) as requesters, MIN(r.request_time) as request_time
        FROM requests r
        JOIN songs s ON r.song_id = s.id
        WHERE r.tenant_id = ? AND r.status = ?
        GROUP BY r.song_id
        ORDER BY request_time ASC
    """, (tenant_id, 'pending'))
    queue = cursor.fetchall()
    conn.close()

    # Format the request_time as ISO 8601 string
    formatted_queue = []
    for row in queue:
        row_dict = dict(row)
        row_dict['request_time'] = datetime.strptime(row_dict['request_time'], '%Y-%m-%d %H:%M:%S').isoformat()
        formatted_queue.append(row_dict)

    return jsonify(formatted_queue)



@app.route('/get_user_requests', methods=['GET'])
@limiter.exempt  # Exempt from rate limiting - read-only endpoint, called frequently during normal use
def get_user_requests():
    app.logger.debug("Accessed /get_user_requests")
    user_name = session.get('user_name')
    tenant_id = session.get('tenant_id')
    
    if not user_name:
        app.logger.error("No user_name in session")
        return jsonify({'error': 'User not logged in'}), 403

    app.logger.debug(f"Username in session: {user_name}, tenant_id: {tenant_id}")

    try:
        conn = create_connection()
        cursor = conn.cursor()
        
        # Filter by tenant_id if available (only show pending requests)
        if tenant_id:
            query = """
                SELECT s.id as song_id, s.title, s.author, s.image, GROUP_CONCAT(r.requester) as requesters
                FROM requests r
                JOIN songs s ON r.song_id = s.id
                WHERE r.requester = ? AND r.tenant_id = ? AND r.status = ?
                GROUP BY r.song_id
                ORDER BY MIN(r.request_time) ASC
            """
            cursor.execute(query, (user_name, tenant_id, 'pending'))
        else:
            query = """
                SELECT s.id as song_id, s.title, s.author, s.image, GROUP_CONCAT(r.requester) as requesters
                FROM requests r
                JOIN songs s ON r.song_id = s.id
                WHERE r.requester = ? AND r.status = ?
                GROUP BY r.song_id
                ORDER BY MIN(r.request_time) ASC
            """
            cursor.execute(query, (user_name, 'pending'))
            
        user_requests = cursor.fetchall()
        app.logger.debug(f"Query returned {len(user_requests)} requests for tenant_id: {tenant_id}")
        conn.close()

        return jsonify([dict(row) for row in user_requests])
    except Exception as e:
        app.logger.error(f"Database error: {e}")
        return jsonify({'error': 'Database error'}), 500



@app.route('/get_user_requests_old', methods=['GET'])
def get_user_requests_old():
    user_name = session.get('user_name')
    conn = create_connection()
    cursor = conn.cursor()

    # Fetch the user's requests
    cursor.execute("""
        SELECT s.id as song_id, s.title, s.author, s.image, GROUP_CONCAT(r.requester) as requesters
        FROM requests r
        JOIN songs s ON r.song_id = s.id
        WHERE r.requester = ?
        GROUP BY r.song_id
        ORDER BY MIN(r.request_time) ASC
    """, (user_name,))
    user_requests = cursor.fetchall()

    conn.close()

    # Format the response
    formatted_user_requests = [dict(row) for row in user_requests]

    return jsonify(formatted_user_requests)


def get_venue_name(tenant_id=None):
    """Get venue name, optionally filtered by tenant_id."""
    return get_setting('venue_name', tenant_id)

@app.route('/update_venue', methods=['POST'])
def update_venue():
    data = request.get_json()
    new_venue_name = data.get('venue_name')
    tenant_id = session.get('tenant_id')
    
    conn = create_connection()
    cursor = conn.cursor()
    
    if tenant_id:
        # Update tenant-specific venue name
        cursor.execute("UPDATE tenants SET venue_name = ? WHERE id = ?", (new_venue_name, tenant_id))
    else:
        # Fallback to global settings (for legacy non-tenant admin)
        cursor.execute("""
            INSERT INTO settings (setting_key, setting_value) 
            VALUES ('venue_name', ?) 
            ON CONFLICT(setting_key) 
            DO UPDATE SET setting_value = excluded.setting_value
        """, (new_venue_name,))
    
    conn.commit()
    conn.close()
    return jsonify({
        'message': 'Venue updated successfully.',
        'venue_name': new_venue_name
    })

@app.route('/<tenant_slug>/update_paypal_link', methods=['POST'])
def tenant_update_paypal_link(tenant_slug):
    """Update PayPal.me link for the tenant."""
    if not session.get('is_tenant_admin') or session.get('tenant_slug') != tenant_slug:
        return jsonify({'success': False, 'message': _('Unauthorized')}), 403
    
    data = request.get_json()
    paypal_link = data.get('paypal_link', '').strip()
    
    # Validate and normalize PayPal.me link
    if paypal_link:
        # Remove http:// or https:// if present
        paypal_link = paypal_link.replace('https://', '').replace('http://', '')
        # Remove www. if present
        paypal_link = paypal_link.replace('www.', '')
        # Ensure it starts with paypal.me/
        if not paypal_link.startswith('paypal.me/'):
            if paypal_link.startswith('paypal.me'):
                paypal_link = 'paypal.me/' + paypal_link.replace('paypal.me', '').lstrip('/')
            else:
                paypal_link = 'paypal.me/' + paypal_link.lstrip('/')
    
    tenant_id = session.get('tenant_id')
    if not tenant_id:
        return jsonify({'success': False, 'message': _('Tenant ID not found')}), 400
    
    conn = create_connection()
    cursor = conn.cursor()
    try:
        # Check if updated_at column exists
        cursor.execute("PRAGMA table_info(tenants)")
        columns = [col[1] for col in cursor.fetchall()]
        has_updated_at = 'updated_at' in columns
        
        # Update PayPal link
        if has_updated_at:
            cursor.execute("""
                UPDATE tenants 
                SET paypal_link = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (paypal_link if paypal_link else None, tenant_id))
        else:
            cursor.execute("""
                UPDATE tenants 
                SET paypal_link = ?
                WHERE id = ?
            """, (paypal_link if paypal_link else None, tenant_id))
        conn.commit()
        
        return jsonify({
            'success': True, 
            'message': _('PayPal link updated successfully'),
            'paypal_link': paypal_link
        })
    except Exception as e:
        app.logger.error(f"Error updating PayPal link: {e}", exc_info=True)
        conn.rollback()
        return jsonify({'success': False, 'message': _('Error updating PayPal link')}), 500
    finally:
        conn.close()

@app.route('/get_venue_name', methods=['GET'])
def fetch_venue_name():
    tenant_id = session.get('tenant_id')
    venue_name = get_venue_name(tenant_id)
    return jsonify({'venue_name': venue_name})



@app.route('/update_venue_old', methods=['POST'])
def update_venue_old():
    venue_name = request.form.get('venue_name')
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("REPLACE INTO settings (setting_key, setting_value) VALUES (?, ?)", ('venue_name', venue_name))
    conn.commit()
    conn.close()

    return render_queue()

@app.route('/scan_qr')
def scan_qr():
    session.pop('last_visited', None)
    tenant = None
    if session.get('tenant_id'):
        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM tenants WHERE id = ?', (session.get('tenant_id'),))
        tenant = cursor.fetchone()
        conn.close()
    return render_template('scan_qr.html', tenant=tenant)

@app.route('/<tenant_slug>/scan_qr')
def tenant_scan_qr(tenant_slug):
    session.pop('last_visited', None)
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM tenants WHERE slug = ? AND active = 1', (tenant_slug,))
    tenant = cursor.fetchone()
    conn.close()
    
    if not tenant:
        flash('Tenant not found or inactive')
        return redirect(url_for('index'))
    
    # Store tenant info in session
    session['tenant_id'] = tenant['id']
    session['tenant_slug'] = tenant['slug']
    
    # If there's an active gig, store its ID in session to verify user presence
    # This ensures users must scan QR code for each new gig
    try:
        active_gig = get_active_gig(tenant['id'])
        if active_gig:
            session['gig_id'] = active_gig['id']
            session['gig_verified_at'] = datetime.now().isoformat()
        else:
            # No active gig - clear any old gig_id
            session.pop('gig_id', None)
            session.pop('gig_verified_at', None)
    except Exception:
        # If gigs table doesn't exist yet, skip (backward compatibility)
        pass
    
    return render_template('scan_qr.html', tenant=tenant)

@app.route('/search_mobile')
def search_mobile():
    session.pop('last_visited', None)
    tenant = None
    tenant_id = None
    if session.get('tenant_id'):
        tenant_id = session.get('tenant_id')
        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM tenants WHERE id = ?', (tenant_id,))
        tenant = cursor.fetchone()
        conn.close()
        
        # Check if there's an active gig (only if gigs table exists)
        # If no active gig, redirect to scan_qr page with message
        try:
            if tenant and not has_active_gig(tenant_id):
                tenant_slug = session.get('tenant_slug')
                if tenant_slug:
                    flash(_('No active gig. Please wait for the musician to start the gig.'), 'info')
                    return redirect(url_for('tenant_scan_qr', tenant_slug=tenant_slug))
                else:
                    flash(_('No active gig. Please wait for the musician to start the gig.'), 'info')
                    return redirect(url_for('scan_qr'))
        except Exception:
            # If gigs table doesn't exist yet, allow access (backward compatibility)
            pass
    return render_template('search-mobile.html', tenant=tenant)

def is_session_valid():
    """Check if the current session is still valid based on the last activity timestamp."""
    timestamp = session.get('last_visited')
    if not timestamp:
        return False
    last_request_time = datetime.strptime(timestamp, '%Y-%m-%dT%H:%M:%S')
    current_time = datetime.now()
    user_name = session.get('user_name')

    if current_time - last_request_time > timedelta(hours=MAX_TIME_TO_REQUEST):
        logging.info(f"User {user_name} timedout at {timestamp} current time {current_time} delta {current_time - last_request_time}")

        return False
    return True

@app.route('/check_session', methods=['GET'])
@limiter.exempt  # Exempt from rate limiting - read-only endpoint, called frequently for polling
def check_session():
    if not is_session_valid():
        return jsonify({'redirect': url_for('scan_qr')})
    return jsonify({'status': 'valid'})


@app.route('/api/user_requested_song_ids', methods=['GET'])
@limiter.exempt  # Exempt from rate limiting - read-only endpoint, called frequently for polling
def get_user_requested_song_ids():
    """Get list of song IDs currently requested by the user (for polling). Only returns pending requests."""
    user_name = session.get('user_name')
    tenant_id = session.get('tenant_id')
    
    if not user_name or not tenant_id:
        return jsonify({'requested_song_ids': []})
    
    try:
        conn = create_connection()
        cursor = conn.cursor()
        
        # Get active gig_id to filter requests by current gig only
        active_gig = get_active_gig(tenant_id)
        gig_id = active_gig['id'] if active_gig else None
        
        if gig_id:
            # Only return requests from the current active gig
            cursor.execute(
                'SELECT song_id FROM requests WHERE requester = ? AND tenant_id = ? AND gig_id = ? AND status = ?', 
                (user_name, tenant_id, gig_id, 'pending')
            )
        else:
            # Fallback: return all pending requests if no gig system (backward compatibility)
            cursor.execute(
                'SELECT song_id FROM requests WHERE requester = ? AND tenant_id = ? AND status = ?', 
                (user_name, tenant_id, 'pending')
            )
        
        requests = cursor.fetchall()
        conn.close()
        
        requested_song_ids = [req['song_id'] for req in requests]
        
        # Also get active gig announcement if available
        announcement = None
        gig_id_for_announcement = None
        if active_gig:
            announcement = active_gig.get('announcement', '')
            gig_id_for_announcement = active_gig.get('id')
        
        return jsonify({
            'requested_song_ids': requested_song_ids,
            'announcement': announcement if announcement else None,
            'gig_id': gig_id_for_announcement
        })
    except Exception as e:
        app.logger.error(f"Error fetching user requests: {e}")
        return jsonify({'requested_song_ids': []})

# PayPal API Helper Functions
def get_paypal_access_token(client_id, client_secret, mode='sandbox'):
    """Get PayPal OAuth access token."""
    base_url = 'https://api-m.sandbox.paypal.com' if mode == 'sandbox' else 'https://api-m.paypal.com'
    url = f"{base_url}/v1/oauth2/token"
    
    headers = {
        'Accept': 'application/json',
        'Accept-Language': 'en_US',
    }
    
    data = {
        'grant_type': 'client_credentials'
    }
    
    try:
        response = requests.post(
            url,
            headers=headers,
            data=data,
            auth=(client_id, client_secret),
            timeout=10
        )
        response.raise_for_status()
        token_data = response.json()
        return token_data.get('access_token')
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Error getting PayPal access token: {e}")
        return None

def create_paypal_order(access_token, amount, currency, mode='sandbox', description=None):
    """Create a PayPal order and return order ID."""
    base_url = 'https://api-m.sandbox.paypal.com' if mode == 'sandbox' else 'https://api-m.paypal.com'
    url = f"{base_url}/v2/checkout/orders"
    
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {access_token}',
        'PayPal-Request-Id': f'order-{int(time.time())}'
    }
    
    payload = {
        'intent': 'CAPTURE',
        'purchase_units': [{
            'amount': {
                'currency_code': currency,
                'value': f"{amount:.2f}"
            }
        }]
    }
    
    if description:
        payload['purchase_units'][0]['description'] = description
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        order_data = response.json()
        return order_data.get('id'), order_data
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Error creating PayPal order: {e}")
        if hasattr(e.response, 'text'):
            app.logger.error(f"PayPal API error response: {e.response.text}")
        return None, None

def capture_paypal_order(access_token, order_id, mode='sandbox'):
    """Capture a PayPal order and return capture details."""
    base_url = 'https://api-m.sandbox.paypal.com' if mode == 'sandbox' else 'https://api-m.paypal.com'
    url = f"{base_url}/v2/checkout/orders/{order_id}/capture"
    
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {access_token}'
    }
    
    try:
        response = requests.post(url, headers=headers, json={}, timeout=10)
        response.raise_for_status()
        capture_data = response.json()
        return capture_data
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Error capturing PayPal order: {e}")
        if hasattr(e.response, 'text'):
            app.logger.error(f"PayPal API error response: {e.response.text}")
        return None

@app.route('/request_song/<int:song_id>', methods=['POST'])
@limiter.limit("10 per minute")
def request_song(song_id):
    try:
        from utils.audit_logger import log_user_action
    except ImportError:
        log_user_action = None

    if not is_session_valid():
        return jsonify({'redirect': url_for('scan_qr')})

    # Get tenant_id from session
    tenant_id = session.get('tenant_id')
    
    # Check if there's an active gig (only if gigs table exists)
    if tenant_id:
        try:
            active_gig = get_active_gig(tenant_id)
            if not active_gig:
                return jsonify({
                    'error': _('No active gig'),
                    'message': _('The musician has not started a gig yet. Please wait for the gig to begin.')
                }), 403
            
            # Verify user has scanned QR code for the current active gig
            session_gig_id = session.get('gig_id')
            if session_gig_id != active_gig['id']:
                # User hasn't scanned QR code for this gig - they need to rescan
                tenant_slug = session.get('tenant_slug', '')
                return jsonify({
                    'error': _('Gig Changed'),
                    'message': _('A new musical event has started. Please scan the QR code to participate.'),
                    'redirect': url_for('tenant_scan_qr', tenant_slug=tenant_slug) if tenant_slug else url_for('scan_qr')
                }), 403
        except Exception:
            # If gigs table doesn't exist yet, allow requests (backward compatibility)
            pass

    try:
        data = request.get_json()
        app.logger.info(f"📥 Request song data received: {data}")
        user_name = data.get('user')
        tip_amount = data.get('tip_amount')  # Optional tip amount in euros (will be converted to cents)
        app.logger.info(f"📥 Parsed: user_name={user_name}, tip_amount={tip_amount} (type: {type(tip_amount)}), tip_amount in data: {'tip_amount' in data if data else False}")
        if not user_name:
            return jsonify({'error': _('User Required')}), 400
        
        max_requests = int(get_setting('max_requests_per_user', tenant_id))  # Ensure max_requests is an integer with tenant isolation
        
        # Get active gig for counting requests
        active_gig_for_count = get_active_gig(tenant_id)
        gig_id_for_count = active_gig_for_count['id'] if active_gig_for_count else None
        
        # Count only pending requests for the current active gig
        user_requests = count_user_requests(user_name, tenant_id, gig_id_for_count)
        app.logger.info(f"User {user_name} has {user_requests} pending requests (max: {max_requests}, gig_id: {gig_id_for_count})")

        if user_requests >= max_requests:
            # Log failed request - max requests reached
            if log_user_action:
                log_user_action(
                    action='song_request_failed',
                entity_type='request',
                song_id=song_id,
                failure_reason='max_requests_reached',
                    user_current_requests_count=user_requests,
                    max_requests_allowed=max_requests
                )
            return jsonify({'error': _('Maximum Request Reached')}), 400

        conn = create_connection()
        cursor = conn.cursor()
        
        # Fetch song info for logging
        cursor.execute('SELECT title, author, requests FROM songs WHERE id = ? AND tenant_id = ?', (song_id, tenant_id))
        song = cursor.fetchone()
        if not song:
            conn.close()
            # Log failed request - song not found
            if log_user_action:
                log_user_action(
                    action='song_request_failed',
                entity_type='request',
                    song_id=song_id,
                    failure_reason='song_not_found'
                )
            return jsonify({'error': 'Song not found'}), 404

        # Check if the user has already requested the song in the current active gig
        # Get active gig_id if available
        active_gig = get_active_gig(tenant_id)
        gig_id = active_gig['id'] if active_gig else None
        
        if gig_id:
            # Check only within the current gig
            cursor.execute('SELECT COUNT(*) as count FROM requests WHERE song_id = ? AND requester = ? AND tenant_id = ? AND gig_id = ? AND status = ?', 
                         (song_id, user_name, tenant_id, gig_id, 'pending'))
        else:
            # Fallback: check all pending requests if no gig system (backward compatibility)
            cursor.execute('SELECT COUNT(*) as count FROM requests WHERE song_id = ? AND requester = ? AND tenant_id = ? AND status = ?', 
                         (song_id, user_name, tenant_id, 'pending'))
        
        user_requested_song = cursor.fetchone()

        if user_requested_song['count'] > 0:
            conn.close()
            # Log failed request - already requested
            if log_user_action:
                log_user_action(
                    action='song_request_failed',
                entity_type='request',
                song_id=song_id,
                song_title=song['title'],
                    song_author=song['author'],
                    failure_reason='already_requested'
                )
            return jsonify({'error': _('Song Already Requested')}), 400

        # Get current queue size (pending requests) for position calculation
        cursor.execute('SELECT COUNT(*) as count FROM requests WHERE tenant_id = ? AND status = ?', (tenant_id, 'pending'))
        pending_count = cursor.fetchone()['count']
        queue_position = pending_count + 1  # Will be this position after insertion

        # Increment the request count
        cursor.execute('UPDATE songs SET requests = requests + 1 WHERE id = ? AND tenant_id = ?', (song_id, tenant_id))

        # Get session_id for tracking
        user_session_id = session.get('user_session_id', 'unknown')
        
        # Get active gig_id if available
        active_gig = get_active_gig(tenant_id)
        gig_id = active_gig['id'] if active_gig else None
        
        # Check if tips are enabled for this gig
        tip_enabled = True  # Default to enabled for backward compatibility
        if active_gig:
            tip_enabled = active_gig.get('tip_enabled', 1) == 1
        
        # Validate tip amount if provided
        tip_amount_cents = 0
        app.logger.info(f"🔍 Validating tip: tip_amount={tip_amount} (type: {type(tip_amount)}), tip_enabled={tip_enabled}, active_gig={active_gig.get('id') if active_gig else None}")
        app.logger.info(f"🔍 tip_amount is not None: {tip_amount is not None}, tip_amount > 0: {tip_amount > 0 if tip_amount is not None else False}")
        if tip_amount is not None and tip_amount > 0:
            app.logger.info(f"✅ Tip amount provided: {tip_amount}, proceeding with validation")
            if not tip_enabled:
                app.logger.warning(f"❌ Tip requested but not enabled for gig {active_gig.get('id') if active_gig else 'N/A'}")
                return jsonify({'error': _('Tips are not enabled for this event')}), 400
            # Convert euros to cents
            try:
                tip_amount_cents = int(float(tip_amount) * 100)
                app.logger.info(f"✅ Converted tip_amount {tip_amount} EUR to {tip_amount_cents} cents")
            except (ValueError, TypeError) as e:
                app.logger.error(f"❌ Invalid tip_amount format: {tip_amount}, error: {e}")
                return jsonify({'error': _('Invalid tip amount format')}), 400
            if tip_amount_cents < 100:  # Minimum 1 euro
                app.logger.warning(f"❌ Tip amount too small: {tip_amount_cents} cents")
                return jsonify({'error': _('Minimum tip amount is 1 EUR')}), 400
        else:
            app.logger.info(f"ℹ️ No tip amount provided or tip_amount is 0: tip_amount={tip_amount}")
        
        # Add the song to the queue with tenant_id, session_id, gig_id, and default status
        # Use tip_amount in euros (as stored in requests table) vs tip_amount_cents (for TipIntent)
        tip_amount_for_db = tip_amount if tip_amount else 0.0
        try:
            cursor.execute(
                'INSERT INTO requests (song_id, requester, tenant_id, session_id, gig_id, status, tip_amount) VALUES (?, ?, ?, ?, ?, ?, ?)', 
                (song_id, user_name, tenant_id, user_session_id, gig_id, 'pending', tip_amount_for_db)
            )
        except sqlite3.OperationalError as e:
            app.logger.error(f"Error inserting request with gig_id: {e}")
            # If gig_id column doesn't exist yet, insert without it (backward compatibility)
            try:
                cursor.execute(
                    'INSERT INTO requests (song_id, requester, tenant_id, session_id, status, tip_amount) VALUES (?, ?, ?, ?, ?, ?)', 
                    (song_id, user_name, tenant_id, user_session_id, 'pending', tip_amount_for_db)
                )
            except sqlite3.OperationalError as e2:
                app.logger.error(f"Error inserting request without gig_id: {e2}")
                conn.close()
                return jsonify({'error': _('Database error: unable to insert request')}), 500
        except Exception as e:
            app.logger.error(f"Unexpected error inserting request: {e}", exc_info=True)
            conn.close()
            return jsonify({'error': _('Database error: unable to insert request')}), 500
        request_id = cursor.lastrowid

        # Create TipIntent if tip amount is provided
        tip_intent_id = None
        tip_intent_data = None
        paypal_order_id = None
        app.logger.info(f"🔍 Checking if TipIntent should be created: tip_amount_cents={tip_amount_cents}, tip_amount_cents > 0: {tip_amount_cents > 0}")
        if tip_amount_cents > 0:
            try:
                app.logger.info(f"✅ Creating TipIntent: request_id={request_id}, tip_amount_cents={tip_amount_cents}")
                # Get musician_id (tenant_id serves as musician_id in this context)
                musician_id = tenant_id
                
                # Get PayPal credentials from environment
                paypal_client_id = os.environ.get('PAYPAL_CLIENT_ID')
                paypal_client_secret = os.environ.get('PAYPAL_CLIENT_SECRET')
                paypal_mode = os.environ.get('PAYPAL_MODE', 'sandbox')
                
                if not paypal_client_id or not paypal_client_secret:
                    app.logger.warning("PayPal credentials not configured - creating TipIntent without order")
                    # Still create TipIntent but without order
                    cursor.execute("""
                        INSERT INTO tip_intents (
                            musician_id, tenant_id, user_session_id, request_id,
                            amount, currency, provider, status
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        musician_id, tenant_id, user_session_id, request_id,
                        tip_amount_cents, 'EUR', 'paypal', 'pending'
                    ))
                    tip_intent_id = cursor.lastrowid
                    conn.commit()
                    app.logger.info(f"TipIntent created without PayPal order (credentials missing): {tip_intent_id}")
                    
                    # Fetch the created tip_intent
                    cursor.execute("""
                        SELECT id, amount, currency, provider, status, provider_payment_id, created_at
                        FROM tip_intents WHERE id = ?
                    """, (tip_intent_id,))
                    tip_intent = cursor.fetchone()
                    
                    app.logger.info(f"🔍 Fetching TipIntent {tip_intent_id}, result: {tip_intent is not None}")
                    if tip_intent:
                        # sqlite3.Row doesn't have .get(), use direct access with try/except
                        provider_payment_id = tip_intent['provider_payment_id'] if 'provider_payment_id' in tip_intent.keys() else None
                        tip_intent_data = {
                            'id': tip_intent['id'],
                            'amount': tip_intent['amount'],
                            'amount_euros': tip_intent['amount'] / 100.0,
                            'currency': tip_intent['currency'],
                            'provider': tip_intent['provider'],
                            'status': tip_intent['status'],
                            'paypal_order_id': provider_payment_id
                        }
                        app.logger.info(f"✅ TipIntent data prepared (no PayPal): {tip_intent_data}")
                    else:
                        app.logger.error(f"❌ TipIntent {tip_intent_id} created but not found when fetching! Trying direct query...")
                        # Try direct query to verify
                        cursor.execute("SELECT COUNT(*) FROM tip_intents WHERE id = ?", (tip_intent_id,))
                        count = cursor.fetchone()[0]
                        app.logger.error(f"❌ Direct query count for tip_intent_id {tip_intent_id}: {count}")
                else:
                    # Create PayPal order
                    access_token = get_paypal_access_token(paypal_client_id, paypal_client_secret, paypal_mode)
                    if not access_token:
                        app.logger.error("Failed to get PayPal access token")
                        raise Exception("Failed to get PayPal access token")
                    
                    amount_euros = tip_amount_cents / 100.0
                    tenant_name = session.get('tenant_name', 'the musician')
                    description = f"Tip for {tenant_name}"
                    
                    paypal_order_id, order_data = create_paypal_order(
                        access_token, 
                        amount_euros, 
                        'EUR', 
                        paypal_mode,
                        description
                    )
                    
                    if not paypal_order_id:
                        app.logger.error("Failed to create PayPal order")
                        raise Exception("Failed to create PayPal order")
                    
                    app.logger.info(f"PayPal order created: {paypal_order_id}")
                    
                    # Create TipIntent with PayPal order ID
                    cursor.execute("""
                        INSERT INTO tip_intents (
                            musician_id, tenant_id, user_session_id, request_id,
                            amount, currency, provider, provider_payment_id, status
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        musician_id, tenant_id, user_session_id, request_id,
                        tip_amount_cents, 'EUR', 'paypal', paypal_order_id, 'pending'
                    ))
                    tip_intent_id = cursor.lastrowid
                    conn.commit()  # Commit before fetching
                    app.logger.info(f"TipIntent created with id: {tip_intent_id}, PayPal order: {paypal_order_id}")
                    
                    # Fetch the created tip_intent
                    cursor.execute("""
                        SELECT id, amount, currency, provider, status, provider_payment_id, created_at
                        FROM tip_intents WHERE id = ?
                    """, (tip_intent_id,))
                    tip_intent = cursor.fetchone()
                    
                    app.logger.info(f"🔍 Fetching TipIntent {tip_intent_id} (with PayPal), result: {tip_intent is not None}")
                    if tip_intent:
                        # sqlite3.Row doesn't have .get(), use direct access
                        provider_payment_id = tip_intent['provider_payment_id'] if 'provider_payment_id' in tip_intent.keys() else None
                        tip_intent_data = {
                            'id': tip_intent['id'],
                            'amount': tip_intent['amount'],
                            'amount_euros': tip_intent['amount'] / 100.0,
                            'currency': tip_intent['currency'],
                            'provider': tip_intent['provider'],
                            'status': tip_intent['status'],
                            'paypal_order_id': provider_payment_id or paypal_order_id
                        }
                        app.logger.info(f"✅ TipIntent data prepared (with PayPal): {tip_intent_data}, paypal_order_id: {tip_intent_data.get('paypal_order_id')}")
                    else:
                        app.logger.error(f"❌ TipIntent {tip_intent_id} created but not found when fetching! Trying direct query...")
                        # Try direct query to verify
                        cursor.execute("SELECT COUNT(*) FROM tip_intents WHERE id = ?", (tip_intent_id,))
                        count = cursor.fetchone()[0]
                        app.logger.error(f"❌ Direct query count for tip_intent_id {tip_intent_id}: {count}")
            except sqlite3.OperationalError as e:
                # If tip_intents table doesn't exist yet, log but don't fail the request
                app.logger.error(f"❌ TipIntent creation failed (table may not exist): {e}", exc_info=True)
                app.logger.error(f"❌ Full error details: {str(e)}")
                tip_intent_id = None
                tip_intent_data = None
            except Exception as e:
                app.logger.error(f"❌ Error creating TipIntent: {e}", exc_info=True)
                app.logger.error(f"❌ Exception type: {type(e).__name__}, message: {str(e)}")
                import traceback
                app.logger.error(f"❌ Traceback: {traceback.format_exc()}")
                # Don't fail the request if TipIntent creation fails, but log it
                tip_intent_id = None
                tip_intent_data = None
        
        # Only commit if TipIntent was not created (to avoid double commit)
        # TipIntent creation already commits in both branches
        if tip_intent_id is None:
            conn.commit()
        
        app.logger.info(f"🔍 Final check BEFORE closing connection:")
        app.logger.info(f"   - tip_intent_data exists: {tip_intent_data is not None}")
        app.logger.info(f"   - tip_intent_id: {tip_intent_id}")
        app.logger.info(f"   - tip_amount_cents: {tip_amount_cents}")
        if tip_intent_data:
            app.logger.info(f"   - tip_intent_data keys: {list(tip_intent_data.keys())}")
        conn.close()

        # Log successful song request (async - non-blocking)
        log_data = {
            'song_id': song_id,
            'song_title': song['title'],
            'song_author': song['author'],
            'request_position_in_queue': queue_position,
            'user_current_requests_count': user_requests,
            'max_requests_allowed': max_requests,
            'total_song_requests': song['requests'] + 1  # After increment
        }
        
        # Add gig_id if available
        active_gig = get_active_gig(tenant_id)
        if active_gig:
            log_data['gig_id'] = active_gig['id']
            log_data['gig_name'] = active_gig['name']
        
        if log_user_action:
            log_user_action(
                action='song_requested',
            entity_type='request',
                entity_id=request_id,
                **log_data
            )

        # Return success message with tip_intent data if created
        response_data = {
            'success': True, 
            'message': _('Song request successful'),
            'request_id': request_id
        }
        
        # Debug: Check tip_intent_data before adding to response
        app.logger.info(f"🔍 DEBUG: About to check tip_intent_data:")
        app.logger.info(f"   - tip_intent_data is None: {tip_intent_data is None}")
        app.logger.info(f"   - tip_intent_data value: {tip_intent_data}")
        app.logger.info(f"   - tip_intent_id: {tip_intent_id}")
        app.logger.info(f"   - tip_amount_cents: {tip_amount_cents}")
        
        # Fallback: If we have tip_intent_id but no data, try to fetch it directly
        if tip_intent_id and not tip_intent_data:
            app.logger.warning(f"⚠️ Fallback: tip_intent_id exists ({tip_intent_id}) but tip_intent_data is None. Trying to fetch directly...")
            try:
                fallback_conn = create_connection()
                if fallback_conn:
                    fallback_cursor = fallback_conn.cursor()
                    fallback_cursor.execute("""
                        SELECT id, amount, currency, provider, status, provider_payment_id, created_at
                        FROM tip_intents WHERE id = ?
                    """, (tip_intent_id,))
                    fallback_tip_intent = fallback_cursor.fetchone()
                    if fallback_tip_intent:
                        provider_payment_id = fallback_tip_intent['provider_payment_id'] if 'provider_payment_id' in fallback_tip_intent.keys() else None
                        tip_intent_data = {
                            'id': fallback_tip_intent['id'],
                            'amount': fallback_tip_intent['amount'],
                            'amount_euros': fallback_tip_intent['amount'] / 100.0,
                            'currency': fallback_tip_intent['currency'],
                            'provider': fallback_tip_intent['provider'],
                            'status': fallback_tip_intent['status'],
                            'paypal_order_id': provider_payment_id
                        }
                        app.logger.info(f"✅ Fallback fetch successful: {tip_intent_data}")
                    fallback_conn.close()
            except Exception as e:
                app.logger.error(f"❌ Fallback fetch failed: {e}")
        
        if tip_intent_data:
            response_data['tip_intent'] = tip_intent_data
            # Also include PayPal client ID for frontend SDK
            paypal_client_id = os.environ.get('PAYPAL_CLIENT_ID')
            paypal_mode = os.environ.get('PAYPAL_MODE', 'sandbox')
            if paypal_client_id:
                response_data['paypal_client_id'] = paypal_client_id
                response_data['paypal_mode'] = paypal_mode
            app.logger.info(f"✅ Returning response with tip_intent: {tip_intent_data}")
            app.logger.info(f"✅ Response data now has tip_intent: {'tip_intent' in response_data}")
        else:
            app.logger.warning(f"⚠️ No tip_intent_data to return! tip_amount_cents was: {tip_amount_cents}, tip_intent_id: {tip_intent_id}")
            # If we have tip_intent_id but no data, try to fetch it directly
            if tip_intent_id:
                app.logger.warning(f"⚠️ We have tip_intent_id {tip_intent_id} but tip_intent_data is None. This is a bug!")
        
        app.logger.info(f"📤 Final response_data keys: {list(response_data.keys())}, has tip_intent: {'tip_intent' in response_data}")
        if 'tip_intent' in response_data:
            app.logger.info(f"📤 tip_intent in response: {response_data['tip_intent']}")
        else:
            app.logger.warning(f"⚠️ tip_intent NOT in response! tip_amount_cents was: {tip_amount_cents}")
        return jsonify(response_data), 200

    except Exception as e:
        # Log error
        if log_user_action:
            log_user_action(
                action='song_request_failed',
            entity_type='request',
                    song_id=song_id,
                    failure_reason='error',
                    error_message=str(e)
                )
        app.logger.error(f"Error incrementing request: {e}")
        return jsonify({'error': _('Song Request Error')}), 500

@app.route('/api/create_paypal_order', methods=['POST'])
@limiter.limit("20 per minute")
def create_paypal_order():
    """Create a PayPal order for a tip intent."""
    if not is_session_valid():
        return jsonify({'error': 'Session invalid'}), 401
    
    try:
        data = request.get_json()
        tip_intent_id = data.get('tip_intent_id')
        if not tip_intent_id:
            return jsonify({'error': 'tip_intent_id is required'}), 400
        
        tenant_id = session.get('tenant_id')
        if not tenant_id:
            return jsonify({'error': 'Tenant ID not found'}), 400
        
        conn = create_connection()
        cursor = conn.cursor()
        
        # Fetch tip_intent
        cursor.execute("""
            SELECT id, amount, currency, status, tenant_id
            FROM tip_intents
            WHERE id = ? AND tenant_id = ?
        """, (tip_intent_id, tenant_id))
        tip_intent = cursor.fetchone()
        
        if not tip_intent:
            conn.close()
            return jsonify({'error': 'Tip intent not found'}), 404
        
        if tip_intent['status'] != 'pending':
            conn.close()
            return jsonify({'error': 'Tip intent is not pending'}), 400
        
        # Get PayPal credentials from global environment variables only
        # Platform-level configuration - single PayPal Business account
        paypal_client_id = os.environ.get('PAYPAL_CLIENT_ID')
        paypal_client_secret = os.environ.get('PAYPAL_CLIENT_SECRET')
        paypal_mode = os.environ.get('PAYPAL_MODE', 'sandbox')
        
        if not paypal_client_id or not paypal_client_secret:
            conn.close()
            return jsonify({'error': 'PayPal not configured'}), 500
        
        # If order already exists, return it
        if tip_intent.get('provider_payment_id'):
            conn.close()
            amount = tip_intent['amount'] / 100.0
            return jsonify({
                'success': True,
                'order_id': tip_intent['provider_payment_id'],
                'amount': amount,
                'currency': tip_intent['currency'],
                'paypal_client_id': paypal_client_id,
                'paypal_mode': paypal_mode
            }), 200
        
        # Create new PayPal order if it doesn't exist
        amount = tip_intent['amount'] / 100.0
        currency = tip_intent['currency']
        
        access_token = get_paypal_access_token(paypal_client_id, paypal_client_secret, paypal_mode)
        if not access_token:
            conn.close()
            return jsonify({'error': 'Failed to get PayPal access token'}), 500
        
        # Get tenant name for description
        cursor.execute("SELECT name FROM tenants WHERE id = ?", (tenant_id,))
        tenant = cursor.fetchone()
        tenant_name = tenant['name'] if tenant else 'the musician'
        description = f"Tip for {tenant_name}"
        
        paypal_order_id, order_data = create_paypal_order(
            access_token, 
            amount, 
            currency, 
            paypal_mode,
            description
        )
        
        if not paypal_order_id:
            conn.close()
            return jsonify({'error': 'Failed to create PayPal order'}), 500
        
        # Update tip_intent with provider_payment_id
        cursor.execute("""
            UPDATE tip_intents
            SET provider_payment_id = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (paypal_order_id, tip_intent_id))
        
        conn.commit()
        conn.close()
        
        # Return order details for frontend PayPal SDK
        return jsonify({
            'success': True,
            'order_id': paypal_order_id,
            'amount': amount,
            'currency': currency,
            'paypal_client_id': paypal_client_id,
            'paypal_mode': paypal_mode
        }), 200
        
    except Exception as e:
        app.logger.error(f"Error creating PayPal order: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/confirm_paypal_payment', methods=['POST'])
@app.route('/api/tips/paypal/capture', methods=['POST'])
@limiter.limit("20 per minute")
def confirm_paypal_payment():
    """Confirm/capture a PayPal payment for a tip intent."""
    if not is_session_valid():
        return jsonify({'error': 'Session invalid'}), 401
    
    try:
        data = request.get_json()
        tip_intent_id = data.get('tip_intent_id')
        order_id = data.get('order_id')
        
        if not tip_intent_id or not order_id:
            return jsonify({'error': 'tip_intent_id and order_id are required'}), 400
        
        tenant_id = session.get('tenant_id')
        if not tenant_id:
            return jsonify({'error': 'Tenant ID not found'}), 400
        
        conn = create_connection()
        cursor = conn.cursor()
        
        # Fetch tip_intent
        cursor.execute("""
            SELECT id, provider_payment_id, status, tenant_id
            FROM tip_intents
            WHERE id = ? AND tenant_id = ?
        """, (tip_intent_id, tenant_id))
        tip_intent = cursor.fetchone()
        
        if not tip_intent:
            conn.close()
            return jsonify({'error': 'Tip intent not found'}), 404
        
        if tip_intent['status'] != 'pending':
            conn.close()
            return jsonify({'error': 'Tip intent is not pending'}), 400
        
        if tip_intent['provider_payment_id'] != order_id:
            conn.close()
            return jsonify({'error': 'Order ID mismatch'}), 400
        
        # Get PayPal credentials
        paypal_client_id = os.environ.get('PAYPAL_CLIENT_ID')
        paypal_client_secret = os.environ.get('PAYPAL_CLIENT_SECRET')
        paypal_mode = os.environ.get('PAYPAL_MODE', 'sandbox')
        
        if not paypal_client_id or not paypal_client_secret:
            conn.close()
            return jsonify({'error': 'PayPal not configured'}), 500
        
        # Capture the PayPal order
        access_token = get_paypal_access_token(paypal_client_id, paypal_client_secret, paypal_mode)
        if not access_token:
            conn.close()
            return jsonify({'error': 'Failed to get PayPal access token'}), 500
        
        capture_data = capture_paypal_order(access_token, order_id, paypal_mode)
        
        if not capture_data:
            # Update status to failed
            cursor.execute("""
                UPDATE tip_intents
                SET status = 'failed', updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (tip_intent_id,))
            conn.commit()
            conn.close()
            return jsonify({'error': 'Failed to capture PayPal payment'}), 500
        
        # Check if capture was successful
        capture_status = capture_data.get('status', '').upper()
        if capture_status == 'COMPLETED':
            # Update tip_intent status to completed
            cursor.execute("""
                UPDATE tip_intents
                SET status = 'completed', updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (tip_intent_id,))
            conn.commit()
            conn.close()
            
            return jsonify({
                'success': True,
                'message': 'Payment confirmed successfully',
                'capture_id': capture_data.get('id')
            }), 200
        else:
            # Update status to failed
            cursor.execute("""
                UPDATE tip_intents
                SET status = 'failed', updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (tip_intent_id,))
            conn.commit()
            conn.close()
            return jsonify({'error': f'Payment capture failed with status: {capture_status}'}), 400
        
    except Exception as e:
        app.logger.error(f"Error confirming PayPal payment: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/create_tip', methods=['POST'])
@limiter.limit("10 per minute")
def create_tip():
    """Create a standalone tip (not linked to a song request) for supporting the musician."""
    if not is_session_valid():
        return jsonify({'error': 'Session invalid'}), 401
    
    try:
        data = request.get_json()
        tip_amount = data.get('tip_amount')
        
        if not tip_amount or tip_amount <= 0:
            return jsonify({'error': 'Valid tip amount is required'}), 400
        
        tenant_id = session.get('tenant_id')
        if not tenant_id:
            return jsonify({'error': 'Tenant ID not found'}), 400
        
        # Check if tips are enabled for active gig
        active_gig = get_active_gig(tenant_id)
        tip_enabled = True
        if active_gig:
            tip_enabled = active_gig.get('tip_enabled', 1) == 1
        
        if not tip_enabled:
            return jsonify({'error': _('Tips are not enabled for this event')}), 400
        
        # Convert euros to cents
        tip_amount_cents = int(float(tip_amount) * 100)
        if tip_amount_cents < 100:  # Minimum 1 euro
            return jsonify({'error': _('Minimum tip amount is 1 EUR')}), 400
        
        user_session_id = session.get('user_session_id', 'unknown')
        musician_id = tenant_id
        
        conn = create_connection()
        cursor = conn.cursor()
        
        # Get PayPal credentials
        paypal_client_id = os.environ.get('PAYPAL_CLIENT_ID')
        paypal_client_secret = os.environ.get('PAYPAL_CLIENT_SECRET')
        paypal_mode = os.environ.get('PAYPAL_MODE', 'sandbox')
        
        paypal_order_id = None
        if paypal_client_id and paypal_client_secret:
            # Create PayPal order
            access_token = get_paypal_access_token(paypal_client_id, paypal_client_secret, paypal_mode)
            if access_token:
                amount_euros = tip_amount_cents / 100.0
                # Get tenant name for description
                cursor.execute("SELECT name FROM tenants WHERE id = ?", (tenant_id,))
                tenant = cursor.fetchone()
                tenant_name = tenant['name'] if tenant else 'the musician'
                description = f"Tip for {tenant_name}"
                
                paypal_order_id, order_data = create_paypal_order(
                    access_token, 
                    amount_euros, 
                    'EUR', 
                    paypal_mode,
                    description
                )
                
                if paypal_order_id:
                    app.logger.info(f"PayPal order created for standalone tip: {paypal_order_id}")
                else:
                    app.logger.error("Failed to create PayPal order for standalone tip")
            else:
                app.logger.error("Failed to get PayPal access token for standalone tip")
        else:
            app.logger.warning("PayPal credentials not configured - creating tip intent without order")
        
        # Create TipIntent without request_id
        cursor.execute("""
            INSERT INTO tip_intents (
                musician_id, tenant_id, user_session_id, request_id,
                amount, currency, provider, provider_payment_id, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            musician_id, tenant_id, user_session_id, None,
            tip_amount_cents, 'EUR', 'paypal', paypal_order_id, 'pending'
        ))
        tip_intent_id = cursor.lastrowid
        
        # Fetch the created tip_intent
        cursor.execute("""
            SELECT id, amount, currency, provider, status, provider_payment_id, created_at
            FROM tip_intents WHERE id = ?
        """, (tip_intent_id,))
        tip_intent = cursor.fetchone()
        
        conn.commit()
        conn.close()
        
        if tip_intent:
            tip_intent_data = {
                'id': tip_intent['id'],
                'amount': tip_intent['amount'],
                'amount_euros': tip_intent['amount'] / 100.0,
                'currency': tip_intent['currency'],
                'provider': tip_intent['provider'],
                'status': tip_intent['status'],
                'paypal_order_id': tip_intent.get('provider_payment_id')
            }
            
            response_data = {
                'success': True,
                'tip_intent': tip_intent_data
            }
            
            # Include PayPal client ID for frontend SDK
            if paypal_client_id:
                response_data['paypal_client_id'] = paypal_client_id
                response_data['paypal_mode'] = paypal_mode
            
            return jsonify(response_data), 200
        else:
            return jsonify({'error': 'Failed to create tip intent'}), 500
        
    except Exception as e:
        app.logger.error(f"Error creating tip: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/mark_request_fulfilled/<int:request_id>', methods=['POST'])
def mark_request_fulfilled(request_id):
    """Mark a song request as fulfilled (played) by the artist."""
    try:
        from utils.audit_logger import log_tenant_admin_action
    except ImportError:
        log_tenant_admin_action = None
    from datetime import datetime, timezone
    
    try:
        # Verify tenant admin is logged in
        if not session.get('is_tenant_admin'):
            return jsonify({'error': 'Unauthorized'}), 403
        
        tenant_id = session.get('tenant_id')
        
        conn = create_connection()
        cursor = conn.cursor()
        
        # Get request and song info before updating
        cursor.execute('''
            SELECT r.*, s.title, s.author, s.id as song_id, r.request_time
            FROM requests r
            JOIN songs s ON r.song_id = s.id
            WHERE r.id = ? AND r.tenant_id = ?
        ''', (request_id, tenant_id))
        
        request_data = cursor.fetchone()
        if not request_data:
            conn.close()
            return jsonify({'error': 'Request not found'}), 404
        
        # Calculate time in queue
        try:
            request_time = datetime.fromisoformat(request_data['request_time'].replace('Z', '+00:00'))
            if request_time.tzinfo is None:
                request_time = request_time.replace(tzinfo=timezone.utc)
            time_in_queue_seconds = int((datetime.now(timezone.utc) - request_time).total_seconds())
        except:
            time_in_queue_seconds = None
        
        # Get queue position before marking as fulfilled
        cursor.execute('''
            SELECT COUNT(*) as position FROM requests
            WHERE tenant_id = ? AND status = 'pending' 
            AND request_time <= ?
        ''', (tenant_id, request_data['request_time']))
        queue_position = cursor.fetchone()['position']
        
        # Update status to 'fulfilled' and set played_at timestamp
        cursor.execute(
            'UPDATE requests SET status = ?, played_at = ? WHERE id = ? AND tenant_id = ?',
            ('fulfilled', datetime.now(timezone.utc).isoformat(), request_id, tenant_id)
        )
        
        conn.commit()
        conn.close()
        
        # Log request fulfilled (async - non-blocking)
        if log_tenant_admin_action:
            log_tenant_admin_action(
                action='request_marked_fulfilled',
            entity_type='request',
            entity_id=request_id,
            song_id=request_data['song_id'],
            song_title=request_data['title'],
            song_author=request_data['author'],
            requester=request_data['requester'],
                queue_position=queue_position,
                time_in_queue_seconds=time_in_queue_seconds
            )
        
        return jsonify({'success': True, 'message': 'Request marked as fulfilled'}), 200
        
    except Exception as e:
        app.logger.error(f"Error marking request as fulfilled: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/create_db', methods=['POST'])
def create_db():
    try:
        os.system('python3 create_db.py')
        return jsonify({'message': 'Database created successfully'}), 200
    except Exception as e:
        return jsonify({'message': 'Exception while creating database', 'details': str(e)}), 500



@app.route('/delete_all_songs', methods=['POST'])
def delete_all_songs():
    try:
        # Get tenant_id from session for data isolation
        tenant_id = session.get('tenant_id')
        
        conn = create_connection()
        cursor = conn.cursor()
        
        # Filter by tenant_id if available
        if tenant_id:
            cursor.execute("DELETE FROM songs WHERE tenant_id = ?", (tenant_id,))
        else:
            cursor.execute("DELETE FROM songs")
        
        conn.commit()
        conn.close()
        return jsonify({'message': 'All songs deleted successfully'}), 200
    except Exception as e:
        app.logger.error(f"Error deleting all songs: {e}")
        return jsonify({'error': 'Failed to delete all songs'}), 500

@app.route('/delete_all_requests', methods=['POST'])
def delete_all_requests():
    tenant_id = session.get('tenant_id')
    conn = create_connection()
    cursor = conn.cursor()
    
    try:
        # Filter by tenant_id if available
        if tenant_id:
            cursor.execute('DELETE FROM requests WHERE tenant_id = ?', (tenant_id,))
            deleted_count = cursor.rowcount
        else:
            cursor.execute('DELETE FROM requests')
            deleted_count = cursor.rowcount
        
        conn.commit()
        return jsonify({
            'success': True,
            'message': f'Deleted {deleted_count} request(s)',
            'deleted_count': deleted_count
        })
    except Exception as e:
        conn.rollback()
        app.logger.error(f"Error deleting all requests: {e}")
        return jsonify({
            'success': False,
            'message': f'Error deleting requests: {str(e)}'
        }), 500
    finally:
        conn.close()


@app.route('/delete_request/<int:song_id>', methods=['POST'])
def delete_request(song_id):
    """Mark all pending requests for a song as fulfilled (played) OR remove a specific user's request."""
    try:
        tenant_id = session.get('tenant_id')
        conn = create_connection()
        cursor = conn.cursor()
        
        # Check if this is a user-specific request removal (from end user UI)
        data = request.get_json(silent=True) or {}
        user_name = data.get('user')
        
        if user_name:
            # End user is removing their own request - mark as cancelled instead of deleting
            # This preserves the request history for analytics
            # Note: The column name in requests table is 'requester', not 'user_name'
            if tenant_id:
                cursor.execute(
                    "UPDATE requests SET status = ? WHERE song_id = ? AND tenant_id = ? AND requester = ? AND status = ?",
                    ('cancelled', song_id, tenant_id, user_name, 'pending')
                )
            else:
                cursor.execute(
                    "UPDATE requests SET status = ? WHERE song_id = ? AND requester = ? AND status = ?",
                    ('cancelled', song_id, user_name, 'pending')
                )
            
            conn.commit()
            conn.close()
            return jsonify({"message": "Song removed from queue successfully"})
        else:
            # Tenant admin is marking song as played - mark all pending requests as fulfilled
            from datetime import datetime
            played_at = datetime.now().isoformat()
            
            # Mark all pending requests for this song as fulfilled
            if tenant_id:
                cursor.execute(
                    "UPDATE requests SET status = ?, played_at = ? WHERE song_id = ? AND tenant_id = ? AND status = ?",
                    ('fulfilled', played_at, song_id, tenant_id, 'pending')
                )
            else:
                cursor.execute(
                    "UPDATE requests SET status = ?, played_at = ? WHERE song_id = ? AND status = ?",
                    ('fulfilled', played_at, song_id, 'pending')
                )
            
            conn.commit()
            conn.close()
            return jsonify({"message": "Song marked as played successfully"})
    except Exception as e:
        app.logger.error(f"Error in delete_request: {e}")
        conn.close()
        return jsonify({"message": "Error processing request"}), 500


@app.route('/update_max_requests', methods=['POST'])
def update_max_requests():
    data = request.get_json()
    max_requests = data.get('max_requests')
    tenant_id = session.get('tenant_id')
    
    conn = create_connection()
    cursor = conn.cursor()
    
    if tenant_id:
        # Update tenant-specific max requests
        cursor.execute("UPDATE tenants SET max_requests = ? WHERE id = ?", (max_requests, tenant_id))
    else:
        # Fallback to global settings (for legacy non-tenant admin)
        cursor.execute("""
            INSERT INTO settings (setting_key, setting_value) 
            VALUES ('max_requests_per_user', ?) 
            ON CONFLICT(setting_key) 
            DO UPDATE SET setting_value = excluded.setting_value
        """, (max_requests,))
    
    conn.commit()
    conn.close()
    return jsonify({
        'message': 'Max requests per user updated successfully.',
        'max_requests': max_requests
    })


@app.route('/get_max_requests', methods=['GET'])
def fetch_max_requests():
    tenant_id = session.get('tenant_id')
    max_requests = get_setting('max_requests_per_user', tenant_id)
    return jsonify({'max_requests': max_requests})



@app.route('/api/queued_songs', methods=['GET'])
@limiter.exempt  # Exempt from rate limiting - read-only endpoint, called frequently
def get_queued_songs():
    try:
        requests = (db.session.query(Requests)
                    .join(Songs, Requests.song_id == Songs.id)
                    .order_by(Requests.request_time)
                    .all())

        result = []
        seen_songs = set()

        for req in requests:
            if req.song_id not in seen_songs:
                seen_songs.add(req.song_id)
                song = db.session.query(Songs).get(req.song_id)
                requesters = [r.requester for r in requests if r.song_id == req.song_id]
                result.append({
                    'id': song.id,
                    'title': song.title,
                    'author': song.author,
                    'image': song.image,
                    'requesters': requesters
                })

        return jsonify(result)
    except Exception as e:
        app.logger.error(f"Error fetching queued songs: {e}")
        return jsonify({"error": "An error occurred while fetching queued songs"}), 500




@app.route('/change_language/<lang_code>', methods=['GET', 'POST'])
def change_language(lang_code):
    if lang_code in app.config['LANGUAGES'].keys():
        session['language'] = lang_code
        session.modified = True
        app.logger.debug(f"Language changed to {lang_code}")
    else:
        app.logger.error(f"Attempted to set unsupported language: {lang_code}")

    user = request.args.get('user', '')
    if user:
        return redirect(request.referrer or url_for('index', user=user))
    else:
        return redirect(request.referrer or url_for('index'))

@app.route('/<tenant_slug>/change_language/<lang_code>', methods=['GET', 'POST'])
def tenant_change_language(tenant_slug, lang_code):
    """Tenant-specific language change route."""
    if lang_code in app.config['LANGUAGES'].keys():
        session['language'] = lang_code
        session.modified = True
        app.logger.debug(f"Language changed to {lang_code} for tenant {tenant_slug}")
    else:
        app.logger.error(f"Attempted to set unsupported language: {lang_code}")

    # Redirect back to the referrer page or tenant admin
    return redirect(request.referrer or url_for('tenant_admin', tenant_slug=tenant_slug))

@app.route('/change_language_old/<lang_code>', methods=['GET', 'POST'])
def change_language_old(lang_code):
    if lang_code in app.config['LANGUAGES'].keys():
        session['language'] = lang_code
        session.modified = True
        app.logger.debug(f"Language changed to {lang_code}")
    else:
        app.logger.error(f"Attempted to set unsupported language: {lang_code}")

    user = request.args.get('user', '')
    return redirect(request.referrer or url_for('index', user=user))





def simple_sanitize_filename(filename):
    """Sanitize the filename by removing unsafe characters."""
    return re.sub(r'[^a-zA-Z0-9_.-]', '_', filename)


@app.route('/upload_author_image/<int:id>', methods=['POST'])
def upload_author_image(id):
    if 'image' not in request.files:
        return jsonify({'message': 'No image part'}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({'message': 'No selected file'}), 400

    if file:
        # Get tenant_id from session for data isolation
        tenant_id = session.get('tenant_id')
        if not tenant_id:
            return jsonify({'message': 'Unauthorized'}), 403
        
        # Get tenant info to save image in tenant directory
        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM tenants WHERE id = ?', (tenant_id,))
        tenant = cursor.fetchone()
        
        if not tenant:
            conn.close()
            return jsonify({'message': 'Tenant not found'}), 404
        
        # Sanitize and save filename
        filename = secure_filename(file.filename)
        timestamp = str(int(time.time()))
        filename_with_timestamp = f"{timestamp}_{filename}"
        
        # Save to tenant's author_images directory
        from utils.tenant_utils import get_tenant_dir
        author_images_dir = get_tenant_dir(app, tenant['slug'], 'author_images')
        
        file_path = os.path.join(author_images_dir, filename_with_timestamp)
        file.save(file_path)
        
        # Update database with just the filename (getAuthorImageUrl will construct the full path)
        cursor.execute('UPDATE songs SET image = ? WHERE id = ? AND tenant_id = ?', 
                      (filename_with_timestamp, id, tenant_id))
        conn.commit()
        conn.close()
        
        return jsonify({
            'message': 'Image uploaded successfully', 
            'image': filename_with_timestamp
        }), 200

    return jsonify({'message': 'Error uploading image'}), 500


@app.route('/upload_author_image_old/<int:id>', methods=['POST'])
def upload_author_image_old(id):
    if 'image' not in request.files:
        return jsonify({'message': 'No image part'}), 400
    file = request.files['image']
    if file.filename == '':
        return jsonify({'message': 'No selected file'}), 400
    
    # Save the file to the desired location
    filename = simple_sanitize_filename(file.filename)
    file_path = os.path.join('/home/vittorioviarengo/songs/static/author_images', filename)
    file.save(file_path)
    
    # Update the database with the new image path
    conn = create_connection()
    conn.execute('UPDATE songs SET image = ? WHERE id = ?', (filename, id))
    conn.commit()
    conn.close()
    
    return jsonify({'message': 'Image uploaded successfully'}), 200

@app.route('/update_song_new/<int:id>', methods=['POST'])
def update_song_new(id):
    data = request.get_json()
    title = data.get('title')
    author = data.get('author')
    language = data.get('language')
    popularity = data.get('popularity')

    conn = create_connection()
    conn.execute('''
        UPDATE songs
        SET title = ?, author = ?, language = ?, popularity = ?
        WHERE id = ?
    ''', (title, author, language, popularity, id))
    conn.commit()
    conn.close()
    
    return jsonify({'message': 'Song updated successfully'}), 200

@app.route('/delete_song/<int:id>', methods=['DELETE'])
def delete_song(id):
    try:
        from utils.audit_logger import log_tenant_admin_action
    except ImportError:
        log_tenant_admin_action = None
    
    # Get tenant_id from session for data isolation
    tenant_id = session.get('tenant_id')
    
    conn = create_connection()
    cursor = conn.cursor()
    
    try:
        # Get song info before deletion for logging
        if tenant_id:
            cursor.execute('SELECT title, author FROM songs WHERE id = ? AND tenant_id = ?', (id, tenant_id))
        else:
            cursor.execute('SELECT title, author FROM songs WHERE id = ?', (id,))
        
        song_data = cursor.fetchone()
        song_title = song_data['title'] if song_data else None
        song_author = song_data['author'] if song_data else None
        
        # First, delete any associated requests for this song
        if tenant_id:
            cursor.execute('DELETE FROM requests WHERE song_id = ? AND tenant_id = ?', (id, tenant_id))
        else:
            cursor.execute('DELETE FROM requests WHERE song_id = ?', (id,))
        
        requests_deleted = cursor.rowcount
        
        # Then delete the song itself
        if tenant_id:
            cursor.execute('DELETE FROM songs WHERE id = ? AND tenant_id = ?', (id, tenant_id))
        else:
            cursor.execute('DELETE FROM songs WHERE id = ?', (id,))
        
        conn.commit()
        conn.close()
        
        message = f'Song deleted successfully'
        if requests_deleted > 0:
            message += f' (also removed {requests_deleted} associated request(s) from queue)'
        
        app.logger.info(f"Deleted song {id} and {requests_deleted} associated requests for tenant {tenant_id}")
        
        # Log song deletion (async - non-blocking)
        if song_data and log_tenant_admin_action:  # Only log if song was found and logger available
            log_tenant_admin_action(
                action='song_deleted',
                entity_type='song',
                entity_id=id,
                song_title=song_title,
                song_author=song_author,
                total_requests_removed=requests_deleted
            )
        
        return jsonify({'message': message}), 200
        
    except Exception as e:
        if conn:
            conn.rollback()
            conn.close()
        app.logger.error(f"Error deleting song {id}: {e}")
        return jsonify({'error': 'Failed to delete song'}), 500
    finally:
        conn.close()




@app.route('/add_song', methods=['POST'])
def add_song():
    title = request.form['title']
    author = request.form['author']
    language = request.form['language']
    popularity = request.form.get('popularity', 0)
    image = request.form.get('image')
    genre = request.form.get('genre', '')
    playlist = request.form.get('playlist', '')
    
    # Get tenant_id from session
    tenant_id = session.get('tenant_id')
    if not tenant_id:
        return jsonify({'error': 'No tenant associated with this session'}), 403

    conn = create_connection()
    conn.execute('''
        INSERT INTO songs (title, author, language, popularity, image, tenant_id, genre, playlist)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (title, author, language, popularity, image, tenant_id, genre, playlist))
    conn.commit()
    conn.close()
    
    return jsonify({'message': 'Song added successfully'}), 200


@app.route('/add_song_old', methods=['POST'])
def add_song_old():
    title = request.form['title']
    author = request.form['author']
    language = request.form['language']
    popularity = request.form.get('popularity', 0)
    image = request.files.get('image')

    image_dir = app.config['UPLOAD_FOLDER']
    if image and not os.path.exists(image_dir):
        os.makedirs(image_dir)

    if image:
        filename = secure_filename(image.filename)
        image.save(os.path.join(image_dir, filename))

    conn = create_connection()
    conn.execute('''
        INSERT INTO songs (title, author, language, popularity, image)
        VALUES (?, ?, ?, ?, ?)
    ''', (title, author, language, popularity, filename))
    conn.commit()
    conn.close()
    
    return jsonify({'message': 'Song added successfully'}), 200


@app.route('/increment_popularity/<int:id>', methods=['POST'])
def increment_popularity(id):
    conn = create_connection()
    conn.execute('UPDATE songs SET popularity = popularity + 1 WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    
    return jsonify({'message': 'Popularity incremented successfully'}), 200


@app.route('/upload', methods=['POST'])
def upload_file():
    """Legacy upload route - redirects to tenant-specific upload."""
    if session.get('tenant_slug'):
        return redirect(url_for('tenant_upload_csv', tenant_slug=session['tenant_slug']))
    
    flash('Please log in to upload files', 'error')
    return redirect(url_for('index'))

@app.route('/<tenant_slug>/upload', methods=['POST'])
def tenant_upload_csv(tenant_slug):
    """Upload CSV file and populate tenant's song database."""
    # Check if tenant admin is logged in
    if not session.get('is_tenant_admin') or session.get('tenant_slug') != tenant_slug:
        flash('Unauthorized access', 'error')
        return redirect(url_for('tenant_login', tenant_slug=tenant_slug))
    
    # Get tenant info
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM tenants WHERE slug = ? AND active = 1', (tenant_slug,))
    tenant = cursor.fetchone()
    
    if not tenant:
        flash('Tenant not found or inactive', 'error')
        conn.close()
        return redirect(url_for('index'))
    
    tenant_id = tenant['id']
    
    # Check if file is in request (support both 'file' and 'csv_file')
    file = request.files.get('file') or request.files.get('csv_file')
    if not file or file.filename == '':
        # Check if this is an AJAX request (from wizard)
        if request.headers.get('Accept') == 'application/json' or request.is_json or request.args.get('format') == 'json':
            conn.close()
            return jsonify({'success': False, 'message': 'No file uploaded'})
        flash('No file uploaded', 'error')
        conn.close()
        return redirect(url_for('tenant_admin', tenant_slug=tenant_slug))
    
    # Validate file extension
    if not file.filename.endswith('.csv'):
        if request.headers.get('Accept') == 'application/json' or request.is_json or request.args.get('format') == 'json':
            conn.close()
            return jsonify({'success': False, 'message': 'Only CSV files are allowed'})
        flash('Only CSV files are allowed', 'error')
        conn.close()
        return redirect(url_for('tenant_admin', tenant_slug=tenant_slug))
    
    try:
        import csv
        import io
        
        # Read CSV file
        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
        csv_reader = csv.reader(stream)
        
        songs_added = 0
        songs_skipped = 0
        errors = []
        
        # Check if first row is a header and determine CSV format
        first_row = next(csv_reader, None)
        is_header = False
        rows_to_process = []
        csv_format = 'new'  # Default: Title, Author, Language, Genre, Playlist
        
        if first_row:
            # Check if it looks like a header row (contains common header keywords)
            first_cell = first_row[0].strip().lower()
            is_header = first_cell in ['title', 'song', 'name', 'titolo', 'canzone']
            
            if is_header:
                # Detect CSV format by checking column names
                header_lower = [cell.strip().lower() for cell in first_row]
                
                # Detect specific format based on columns
                if len(header_lower) == 5 and 'image' in header_lower:
                    # Downloaded CSV format: Title, Artist, Language, Genre, Image
                    csv_format = 'downloaded'
                    app.logger.info("Detected DOWNLOADED CSV format: Title,Artist,Language,Genre,Image")
                elif 'image' in header_lower or 'immagine' in header_lower:
                    # Old format with full columns
                    csv_format = 'old'  # Title, Author, Language, Image, Popularity, Genre, Playlist
                    app.logger.info("Detected OLD CSV format with Image column")
                else:
                    # New template format
                    csv_format = 'new'  # Title, Author, Language, Genre, Playlist
                    app.logger.info("Detected NEW CSV format without Image column")
            else:
                # Not a header, process it as the first song
                rows_to_process = [first_row]
                # Try to detect format by column count
                if len(first_row) >= 6:
                    csv_format = 'old'  # Probably has Image column
                else:
                    csv_format = 'new'
        
        # Add remaining rows
        rows_to_process.extend(csv_reader)
        
        for row_num, row in enumerate(rows_to_process, start=2 if is_header else 1):
            try:
                # Skip empty rows
                if not row or len(row) == 0:
                    continue
                
                # Support multiple CSV formats
                # DOWNLOADED: title,artist,language,genre,image (5 columns)
                # OLD: title,author,language,image,popularity,genre,playlist (7 columns)
                # NEW: title,author,language,genre,playlist (5 columns without image)
                if len(row) < 3:
                    errors.append(f"Row {row_num}: Not enough columns (need at least 3: title, author, language)")
                    songs_skipped += 1
                    continue
                
                title = row[0].strip()
                author = row[1].strip()
                language = row[2].strip().lower()  # Normalize language to lowercase
                
                if csv_format == 'downloaded':
                    # DOWNLOADED format: title,artist,language,genre,image
                    genre = row[3].strip() if len(row) > 3 else ''
                    image = row[4].strip() if len(row) > 4 else ''
                    playlist = ''
                    popularity = 0
                elif csv_format == 'old':
                    # OLD format: title,author,language,image,popularity,genre,playlist
                    image = row[3].strip() if len(row) > 3 else ''
                    popularity = int(row[4]) if len(row) > 4 and row[4].strip() and row[4].strip().isdigit() else 0
                    genre = row[5].strip() if len(row) > 5 else ''
                    playlist = row[6].strip() if len(row) > 6 else ''
                else:
                    # NEW format: title,author,language,genre,playlist
                    genre = row[3].strip() if len(row) > 3 else ''
                    playlist = row[4].strip() if len(row) > 4 else ''
                    image = ''  # Will be fetched from Spotify later
                    popularity = 0
                
                # Validate required fields
                if not title or not author or not language:
                    errors.append(f"Row {row_num}: Missing required fields (title, author, or language)")
                    songs_skipped += 1
                    continue
                
                # Insert song into database with tenant_id
                cursor.execute('''
                    INSERT INTO songs (title, author, language, image, popularity, tenant_id, genre, playlist)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (title, author, language, image, popularity, tenant_id, genre, playlist))
                
                songs_added += 1
                
            except Exception as e:
                errors.append(f"Row {row_num}: {str(e)}")
                songs_skipped += 1
                continue
        
        conn.commit()
        conn.close()
        
        # Build success message
        is_ajax = request.headers.get('Accept') == 'application/json' or request.is_json or request.args.get('format') == 'json'
        
        if songs_added > 0 and songs_skipped == 0:
            # All songs added successfully
            message = f"✅ CSV upload complete! Successfully added {songs_added} song(s) to your library."
            if is_ajax:
                return jsonify({'success': True, 'message': message, 'songs_added': songs_added})
            flash(message, 'success')
        elif songs_added > 0 and songs_skipped > 0:
            # Partial success
            message = f"CSV upload complete! Added {songs_added} song(s), skipped {songs_skipped} row(s)."
        if errors:
            error_preview = '; '.join(errors[:3])  # Show first 3 errors
            if len(errors) > 3:
                message += f"<br><br><strong>Sample errors:</strong> {error_preview}... and {len(errors) - 3} more."
            else:
                message += f"<br><br><strong>Errors:</strong> {error_preview}"
            if is_ajax:
                return jsonify({'success': True, 'message': message, 'songs_added': songs_added, 'songs_skipped': songs_skipped, 'errors': errors})
            flash(message, 'warning')
        else:
            # No songs added
            message = f"❌ CSV upload failed. No songs were added."
            if errors:
                error_preview = '; '.join(errors[:5])
                if len(errors) > 5:
                    message += f"<br><br><strong>Errors:</strong> {error_preview}... and {len(errors) - 5} more."
                else:
                    message += f"<br><br><strong>Errors:</strong> {error_preview}"
            if is_ajax:
                return jsonify({'success': False, 'message': message, 'errors': errors})
            flash(message, 'error')
        
    except Exception as e:
        conn.close()
        is_ajax = request.headers.get('Accept') == 'application/json' or request.is_json or request.args.get('format') == 'json'
        if is_ajax:
            return jsonify({'success': False, 'message': f'Error processing CSV file: {str(e)}'})
        flash(f'Error processing CSV file: {str(e)}', 'error')
    
    return redirect(url_for('tenant_admin', tenant_slug=tenant_slug))

@app.route('/<tenant_slug>/download_csv', methods=['GET'])
def tenant_download_csv(tenant_slug):
    """Download CSV file with all tenant's songs."""
    # Check if tenant admin is logged in
    if not session.get('is_tenant_admin') or session.get('tenant_slug') != tenant_slug:
        flash('Unauthorized access', 'error')
        return redirect(url_for('tenant_login', tenant_slug=tenant_slug))
    
    # Get tenant info
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM tenants WHERE slug = ? AND active = 1', (tenant_slug,))
    tenant = cursor.fetchone()
    
    if not tenant:
        flash('Tenant not found or inactive', 'error')
        conn.close()
        return redirect(url_for('index'))
    
    tenant_id = tenant['id']
    tenant_name = tenant['name']
    
    try:
        import csv
        import io
        from flask import make_response
        
        # Get all songs for this tenant
        cursor.execute('''
            SELECT title, author, language, image, popularity, genre, playlist
            FROM songs 
            WHERE tenant_id = ?
            ORDER BY title ASC
        ''', (tenant_id,))
        
        songs = cursor.fetchall()
        conn.close()
        
        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header row
        writer.writerow(['title', 'author', 'language', 'image', 'popularity', 'genre', 'playlist'])
        
        # Write data rows
        for song in songs:
            writer.writerow([
                song['title'],
                song['author'],
                song['language'],
                song['image'] or '',
                song['popularity'] or 0,
                song['genre'] or '',
                song['playlist'] or ''
            ])
        
        # Prepare response
        output.seek(0)
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv; charset=utf-8'
        response.headers['Content-Disposition'] = f'attachment; filename={tenant_slug}_songs.csv'
        
        app.logger.info(f"Tenant {tenant_slug} downloaded CSV with {len(songs)} songs")
        
        return response
        
    except Exception as e:
        app.logger.error(f"Error generating CSV for tenant {tenant_slug}: {e}")
        if conn:
            conn.close()
        flash(f'Error generating CSV file: {str(e)}', 'error')
    return redirect(url_for('tenant_admin', tenant_slug=tenant_slug))

@app.route('/populate_db', methods=['POST'])
def populate_db():
    pythonfile = os.path.join(os.path.dirname(__file__), 'load_db.py')
    os.chdir('/home/vittorioviarengo/songs')
    os.system('python' + ' ' + pythonfile)
    logging.info('Populating songs')
    return redirect('/admin')

# Translation management is now done manually
# Removed translate_ui route - translations are handled via .po files
# To add new translations:
# 1. Edit translations/[lang]/LC_MESSAGES/messages.po
# 2. Run: pybabel compile -d translations
# 3. Reload the application

@app.route('/help')
def help_page():
    """Non-tenant help page (for backwards compatibility)."""
    return render_template('help.html', tenant=None)

@app.route('/logout_user', methods=['GET', 'POST'])
def logout_user():
    """Logout end user - clear name and return to home."""
    # Clear user name from session
    session.pop('user_name', None)
    session.pop('last_visited', None)
    session.pop('user_session_id', None)
    
    # Redirect to home page
    return redirect(url_for('index'))

@app.route('/search', methods=['GET', 'POST'])
def search():
    user_name = request.form.get('user_name', request.args.get('user_name', session.get('user_name', '')))
    language = request.form.get('lang', request.args.get('lang', session.get('language', 'en')))
    search_query = request.args.get('s', '')  # Assuming there's a query parameter 's' for search queries

    # Set session variables
    session['user_name'] = user_name
    session['language'] = language
    
    app.logger.debug(f'Loading Search.html for user: {user_name}')
    app.logger.debug(f'Language: {language}')
    app.logger.debug(f'Search query: {search_query}')
    
    # Get tenant info
    tenant = None
    if session.get('tenant_id'):
        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM tenants WHERE id = ?', (session.get('tenant_id'),))
        tenant = cursor.fetchone()
        conn.close()
    
    # Check if the username is empty
    if user_name == '':
        app.logger.debug('Rendering Search.html without request ability')
        songs = fetch_songs('all', search_query, language, tenant_id=session.get('tenant_id'))
        return render_template('search.html', user_name=user_name, language=language, songs=songs, can_request_songs=False, tenant=tenant)

    # If username is not empty, check if the session is valid
    if not is_session_valid():
        # Reset username and redirect if session is not valid
        app.logger.debug(f'redirecting to scan_qr for user: {user_name}')
        session['user_name'] = ''
        return redirect(url_for('scan_qr'))

    # If session is valid and username is not empty, fetch and render the search page with song data
    songs = fetch_songs('all', search_query, language, tenant_id=session.get('tenant_id'))
    return render_template('search.html', user_name=user_name, language=language, songs=songs, can_request_songs=True, tenant=tenant)


# SECURITY: Disabled old debug endpoints (Phase 1, Task 2)
# These were duplicate/debug versions of /search and should not be exposed in production
# Commented out 2024-11-19 - can be removed completely after verification

# @app.route('/search_old', methods=['GET', 'POST'])
# def search_old():
#     # OLD/DEBUG: Superseded by /search
#     pass

# @app.route('/search_works', methods=['GET', 'POST'])
# def search_works():
#     # OLD/DEBUG: Superseded by /search
#     pass

@app.route('/get_all_songs', methods=['GET'])
@limiter.exempt  # Exempt from rate limiting - read-only endpoint, called on every page load/scroll
def get_all_songs():
    # SECURITY: Require tenant session for data isolation
    # Without this, the endpoint would return ALL songs from ALL tenants
    tenant_id = session.get('tenant_id')
    if not tenant_id:
        app.logger.warning("Unauthorized access attempt to /get_all_songs without tenant_id in session")
        return jsonify({'error': 'Unauthorized - No tenant session'}), 403
    
    sort_by = request.args.get('sort_by', 'title')  # Default sort by title
    sort_order = request.args.get('sort_order', 'asc')  # Default sort order ascending
    page = int(request.args.get('page', 1))  # Default to page 1
    per_page = int(request.args.get('per_page', 10))  # Default to 10 songs per page
    search_query = request.args.get('search', '')  # Default to empty search query

    # Validate sort_by and sort_order
    valid_columns = ['title', 'author', 'language', 'popularity']
    if sort_by not in valid_columns:
        sort_by = 'title'
    if sort_order not in ['asc', 'desc']:
        sort_order = 'asc'

    offset = (page - 1) * per_page

    conn = create_connection()
    cursor = conn.cursor()
    
    # SECURITY: Always filter by tenant_id (already verified above)
    # This ensures data isolation between tenants
    query = f'''
        SELECT * FROM songs
        WHERE (title LIKE ? OR author LIKE ? OR language LIKE ?) AND tenant_id = ?
        ORDER BY {sort_by} {sort_order}
        LIMIT {per_page} OFFSET {offset}
    '''
    cursor.execute(query, (f'%{search_query}%', f'%{search_query}%', f'%{search_query}%', tenant_id))
    
    songs = cursor.fetchall()
    conn.close()

    songs_list = [dict(song) for song in songs]
    return jsonify(songs_list)

@app.route('/update_song/<int:song_id>', methods=['POST'])
def update_song(song_id):
    # SECURITY: Require tenant session to prevent cross-tenant data modification
    tenant_id = session.get('tenant_id')
    if not tenant_id:
        app.logger.warning(f"Unauthorized update attempt for song {song_id} without tenant_id in session")
        return jsonify({'error': 'Unauthorized - No tenant session'}), 403
    
    try:
        data = request.get_json()
        app.logger.debug(f"Received data: {data}")

        title = data.get('title')
        author = data.get('author')
        language = data.get('language')
        popularity = data.get('popularity')
        image = data.get('image')
        genre = data.get('genre', '')
        playlist = data.get('playlist', '')

        app.logger.info(f"Updating song {song_id}: title={title}, author={author}, image={image}")

        if not title or not author or not language or popularity is None:
            app.logger.error('Invalid data received')
            return jsonify({'message': 'Invalid data'}), 400
        
        conn = create_connection()
        cursor = conn.cursor()
        
        # SECURITY: Always filter by tenant_id to prevent cross-tenant modification
        cursor.execute("""
            UPDATE songs
            SET title = ?, author = ?, language = ?, popularity = ?, image = ?, genre = ?, playlist = ?
            WHERE id = ? AND tenant_id = ?
        """, (title, author, language, popularity, image, genre, playlist, song_id, tenant_id))
        
        conn.commit()
        conn.close()

        return jsonify({'message': 'Song updated successfully'}), 200
    except Exception as e:
        app.logger.error(f"Error updating song: {e}")
        return jsonify({'message': 'Error updating song'}), 500

@app.route('/zero_popularity', methods=['POST'])
def zero_popularity():
    try:
        # Get tenant_id from session for data isolation
        tenant_id = session.get('tenant_id')
        
        conn = create_connection()
        cursor = conn.cursor()
        
        # Filter by tenant_id if available
        if tenant_id:
            cursor.execute("UPDATE songs SET popularity = 0 WHERE tenant_id = ?", (tenant_id,))
        else:
            cursor.execute("UPDATE songs SET popularity = 0")
        
        conn.commit()
        conn.close()

        return jsonify({'message': 'Popularity of all songs has been reset to zero'}), 200
    except Exception as e:
        app.logger.error(f"Error resetting popularity: {e}")
        return jsonify({'message': 'Error resetting popularity'}), 500


@app.route('/search_songs')
@limiter.exempt  # Exempt from rate limiting - read-only endpoint, called on every scroll/page load
def search_songs():
    query = request.args.get('s', '').strip().lower()
    language = request.args.get('language', 'All').lower()
    letter = request.args.get('letter', 'All').lower()
    sortBy = request.args.get('sortBy', 'title')  # Default sorting by title
    sortOrder = request.args.get('sortOrder', 'asc')  # Default sort order ascending
    try:
        page = int(request.args.get('page', 1))  # Get the page number from the request
    except ValueError:
        page = 1  # Default to page 1 if the page parameter is invalid

    songs_per_page = 20  # Define the number of songs per page

    # Get tenant_id from session for data isolation
    tenant_id = session.get('tenant_id')
    print(f'DEBUG /search_songs: tenant_id={tenant_id}, query={query}, language={language}, page={page}')
    app.logger.debug(f'Received search parameters - Query: {query}, Language: {language}, Letter: {letter}, SortBy: {sortBy}, SortOrder: {sortOrder}, Page: {page}, tenant_id: {tenant_id}')

    songs = fetch_songs(letter, query, language, sortBy, sortOrder, page, songs_per_page, tenant_id=tenant_id)
    print(f'DEBUG /search_songs: Found {len(songs)} songs for tenant_id={tenant_id}')
    app.logger.debug(f'Sorting by: {sortBy} {sortOrder}, found {len(songs)} songs for tenant_id: {tenant_id}')
    return jsonify({'songs': songs})

@app.route('/search_songs_old2')
def search_songs_old2():
    query = request.args.get('s', '').strip().lower()
    language = request.args.get('language', 'All').lower()
    letter = request.args.get('letter', 'All').lower()
    sortBy = request.args.get('sortBy', 'title')  # Default sorting by title
    try:
        page = int(request.args.get('page', 1))  # Get the page number from the request
    except ValueError:
        page = 1  # Default to page 1 if the page parameter is invalid

    songs_per_page = 20  # Define the number of songs per page

    app.logger.debug(f'Received search parameters - Query: {query}, Language: {language}, Letter: {letter}, SortBy: {sortBy}, Page: {page}')

    songs = fetch_songs(letter, query, language, sortBy, page, songs_per_page)
    app.logger.debug(f'Sorting by: {sortBy}')
    return jsonify({'songs': songs})

@app.route('/search_songs_old')
def search_songs_old():
    query = request.args.get('s', '').strip().lower()
    language = request.args.get('language', 'All').lower()
    letter = request.args.get('letter', 'All').lower()
    sortBy = request.args.get('sortBy', 'title')  # Default sorting by title
    page = int(request.args.get('page', 1))  # Get the page number from the request
    songs_per_page = 10  # Define the number of songs per page

    app.logger.debug(f'Received search parameters - Query: {query}, Language: {language}, Letter: {letter}, SortBy: {sortBy}, Page: {page}')

    songs = fetch_songs(letter, query, language, sortBy, page, songs_per_page)
    app.logger.debug(f'Sorting by: {sortBy}')
    return jsonify({'songs': songs})


def fetch_songs(start_letter, query='', language='all', sortBy='title', sortOrder='asc', page=1, songs_per_page=20, tenant_id=None, user_name=None):
    conn = create_connection()
    cursor = conn.cursor()
    conditions = []
    params = []
    
    # CRITICAL: Filter by tenant_id for data isolation
    if tenant_id:
        conditions.append("songs.tenant_id = ?")
        params.append(tenant_id)
    
    # Exclude songs already requested by this user (still in queue)
    if user_name and tenant_id:
        conditions.append("songs.id NOT IN (SELECT song_id FROM requests WHERE requester = ? AND tenant_id = ?)")
        params.extend([user_name, tenant_id])
    
    if query:
        conditions.append("(LOWER(songs.title) LIKE ? OR LOWER(songs.author) LIKE ?)")
        params.extend([f'%{query}%', f'%{query}%'])
    if language != 'all':
        conditions.append("LOWER(songs.language) = ?")
        params.append(language)
    if start_letter != 'all':
        conditions.append("LOWER(songs.title) LIKE ?")
        params.append(f'{start_letter.lower()}%')

    where_clause = ' AND '.join(conditions) if conditions else '1=1'

    # Safely adding sorting criteria
    order_by_column = 'popularity' if sortBy == 'popularity' else 'author' if sortBy == 'author' else 'title'
    order_by_direction = 'DESC' if sortOrder == 'desc' else 'ASC'
    sql_query = f"SELECT songs.* FROM songs WHERE {where_clause} ORDER BY songs.{order_by_column} {order_by_direction} LIMIT ? OFFSET ?"

    # Calculate the offset for pagination
    offset = (page - 1) * songs_per_page
    params.extend([songs_per_page, offset])

    cursor.execute(sql_query, params)
    songs = cursor.fetchall()
    conn.close()
    return [dict(song) for song in songs]

def fetch_songs_old2(start_letter, query='', language='all', sortBy='title', page=1, songs_per_page=10):
    conn = create_connection()
    cursor = conn.cursor()
    conditions = []
    params = []
    if query:
        conditions.append("(LOWER(title) LIKE ? OR LOWER(author) LIKE ?)")
        params.extend([f'%{query}%', f'%{query}%'])
    if language != 'all':
        conditions.append("LOWER(language) = ?")
        params.append(language)
    if start_letter != 'all':
        conditions.append("LOWER(title) LIKE ?")
        params.append(f'{start_letter.lower()}%')

    where_clause = ' AND '.join(conditions) if conditions else '1=1'

    # Safely adding sorting criteria
    order_by_column = 'author' if sortBy == 'author' else 'title'
    sql_query = f"SELECT * FROM songs WHERE {where_clause} ORDER BY {order_by_column} LIMIT ? OFFSET ?"

    # Calculate the offset for pagination
    offset = (page - 1) * songs_per_page
    params.extend([songs_per_page, offset])

    cursor.execute(sql_query, params)
    songs = cursor.fetchall()
    conn.close()
    return [dict(song) for song in songs]

def fetch_songs_old(start_letter, query='', language='all', sortBy='title', page=1, songs_per_page=10):
    conn = create_connection()
    cursor = conn.cursor()
    conditions = []
    params = []
    if query:
        conditions.append("(LOWER(title) LIKE ? OR LOWER(author) LIKE ?)")
        params.extend([f'%{query}%', f'%{query}%'])
    if language != 'all':
        conditions.append("LOWER(language) = ?")
        params.append(language)
    if start_letter != 'all':
        conditions.append("LOWER(title) LIKE ?")
        params.append(f'{start_letter.lower()}%')

    where_clause = ' AND '.join(conditions) if conditions else '1=1'

    # Safely adding sorting criteria
    order_by_column = 'author' if sortBy == 'author' else 'title'
    sql_query = f"SELECT * FROM songs WHERE {where_clause} ORDER BY {order_by_column} LIMIT ? OFFSET ?"

    # Calculate the offset for pagination
    offset = (page - 1) * songs_per_page
    params.extend([songs_per_page, offset])

    cursor.execute(sql_query, params)
    songs = cursor.fetchall()
    conn.close()
    return [dict(song) for song in songs]



def ensure_gigs_table():
    """Ensure the gigs table exists. Called at app startup."""
    conn = create_connection()
    if not conn:
        app.logger.error("Failed to create database connection for gigs table check")
        return
    
    cursor = conn.cursor()
    try:
        # Check if table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='gigs'
        """)
        table_exists = cursor.fetchone()
        
        # Add announcement column if table exists but column doesn't
        if table_exists:
            try:
                cursor.execute("ALTER TABLE gigs ADD COLUMN announcement TEXT NULL")
                app.logger.info("Added announcement column to existing gigs table")
            except sqlite3.OperationalError as e:
                if "duplicate column name" in str(e).lower():
                    app.logger.info("Column announcement already exists in gigs table")
                else:
                    raise
        
        if table_exists:
            conn.commit()
            conn.close()
            return
        
        # Create gigs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS gigs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER NOT NULL,
                name TEXT,
                start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                end_time TIMESTAMP NULL,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                tip_enabled INTEGER DEFAULT 1,
                FOREIGN KEY(tenant_id) REFERENCES tenants(id),
                CHECK(is_active IN (0, 1))
            )
        """)
        
        # Create indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_gigs_tenant_active 
            ON gigs(tenant_id, is_active)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_gigs_start_time 
            ON gigs(start_time)
        """)
        
        # Add gig_id column to requests table if it doesn't exist
        try:
            cursor.execute("ALTER TABLE requests ADD COLUMN gig_id INTEGER NULL")
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_requests_gig_id 
                ON requests(gig_id)
            """)
            app.logger.info("Added gig_id column to requests table")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                app.logger.info("Column gig_id already exists in requests table")
            else:
                raise
        
        # Add announcement column to gigs table if it doesn't exist
        try:
            cursor.execute("ALTER TABLE gigs ADD COLUMN announcement TEXT NULL")
            app.logger.info("Added announcement column to gigs table")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                app.logger.info("Column announcement already exists in gigs table")
            else:
                raise
        
        # Add tip_enabled column to gigs table if it doesn't exist
        try:
            cursor.execute("ALTER TABLE gigs ADD COLUMN tip_enabled INTEGER DEFAULT 1")
            app.logger.info("Added tip_enabled column to gigs table")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                app.logger.info("Column tip_enabled already exists in gigs table")
            else:
                raise
        
        conn.commit()
        app.logger.info("Successfully created 'gigs' table and indexes")
    except sqlite3.Error as e:
        app.logger.error(f"Error creating gigs table: {e}")
        conn.rollback()
    finally:
        conn.close()

def ensure_tip_intents_table():
    """Ensure the tip_intents table exists. Called at app startup."""
    conn = create_connection()
    if not conn:
        app.logger.error("Failed to create database connection for tip_intents table check")
        return
    
    cursor = conn.cursor()
    try:
        # Check if table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='tip_intents'
        """)
        table_exists = cursor.fetchone()
        
        if table_exists:
            conn.commit()
            conn.close()
            return
        
        # Create tip_intents table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tip_intents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                musician_id INTEGER NOT NULL,
                tenant_id INTEGER NOT NULL,
                user_session_id TEXT NOT NULL,
                request_id INTEGER NULL,
                amount INTEGER NOT NULL,
                currency TEXT DEFAULT 'EUR',
                provider TEXT DEFAULT 'paypal',
                provider_payment_id TEXT NULL,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(tenant_id) REFERENCES tenants(id),
                FOREIGN KEY(request_id) REFERENCES requests(id),
                CHECK(status IN ('pending', 'completed', 'failed', 'cancelled'))
            )
        """)
        
        # Create indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tip_intents_tenant_id 
            ON tip_intents(tenant_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tip_intents_status 
            ON tip_intents(status)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tip_intents_request_id 
            ON tip_intents(request_id)
        """)
        
        conn.commit()
        app.logger.info("Successfully created 'tip_intents' table and indexes")
    except sqlite3.Error as e:
        app.logger.error(f"Error creating tip_intents table: {e}")
        conn.rollback()
    finally:
        conn.close()

# Ensure gigs table exists at startup
# This is called when the module is imported, which happens on PythonAnywhere
_gigs_table_ensured = False
_tip_intents_table_ensured = False

def ensure_gigs_table_once():
    """Ensure gigs table exists, but only once per app instance."""
    global _gigs_table_ensured
    if _gigs_table_ensured:
        return
    
    try:
        with app.app_context():
            ensure_gigs_table()
            _gigs_table_ensured = True
    except Exception as e:
        app.logger.error(f"Error ensuring gigs table at startup: {e}")

def ensure_tip_intents_table_once():
    """Ensure tip_intents table exists, but only once per app instance."""
    global _tip_intents_table_ensured
    if _tip_intents_table_ensured:
        return
    
    try:
        with app.app_context():
            ensure_tip_intents_table()
            _tip_intents_table_ensured = True
    except Exception as e:
        app.logger.error(f"Error ensuring tip_intents table at startup: {e}")

# Call immediately when module loads
ensure_gigs_table_once()
ensure_tip_intents_table_once()

# Also ensure on first request (fallback for PythonAnywhere)
@app.before_request
def ensure_tables_before_request():
    """Ensure tables exist before each request (only runs once due to flag)."""
    ensure_gigs_table_once()
    ensure_tip_intents_table_once()

if __name__ == '__main__':
    #app.run(debug=True)
    app.run(host='0.0.0.0', port=5001, debug=True)


    

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

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = b'3L+nc\xcd\x02e/\x88\xbf\x9e\xfc\xb5\xa2'

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


# Vittorio's Spotify credentials
client_id = "4dd130b8c960408798e64c30f04d67ad"
client_secret = "96c2357eea1e400e9921799f45581370"


babel = Babel(app)

# Context processor to make app_name available to all templates
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

ADMIN_PASSWORD = 'cottonclub'
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
    venue_name = get_venue_name(tenant_id)
    max_requests = get_setting('max_requests_per_user', tenant_id)
    return render_template('queue.html', is_admin=is_admin, current_datetime=current_datetime, venue_name=venue_name, max_requests=max_requests)


#--------------------------------------------- Utility functions to inspect the database table ---------------------------------------------


@app.route('/fetch_table')
def fetch_table():
    table_name = request.args.get('name')
    conn = create_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(f'SELECT * FROM {table_name}')
        rows = cursor.fetchall()
        data = [dict(row) for row in rows]
        return jsonify(data)
    except sqlite3.Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


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
        
        # Call the Python script to generate the PDF with tenant_id using the same Python interpreter
        result = subprocess.run(
            [sys.executable, script_path, str(tenant_id)], 
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
    try:
        # Set timeout for Spotify API calls
        sp = Spotify(
            auth_manager=SpotifyClientCredentials(
                client_id=client_id, 
                client_secret=client_secret
            ),
            requests_timeout=10,  # 10 second timeout
            retries=2
        )
        results = sp.search(q=author_name, type="artist", limit=1)
        items = results.get("artists", {}).get("items", [])
    except Exception as e:
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
        
        # Try to infer language from artist's top track or origin
        # Get artist's top tracks to check their markets
        language = None
        try:
            artist_id = artist_data.get("id")
            if artist_id:
                app.logger.info(f"Fetching top tracks for artist ID: {artist_id}")
                top_tracks = sp.artist_top_tracks(artist_id)
                tracks = top_tracks.get("tracks", [])
                app.logger.info(f"Found {len(tracks)} top tracks")
                
                # Check available markets to infer language
                if tracks:
                    markets = tracks[0].get("available_markets", [])
                    app.logger.info(f"First track available in {len(markets)} markets")
                    # Map common markets to languages
                    market_to_lang = {
                        'IT': 'it', 'CH': 'it',  # Italy, Switzerland (Italian)
                        'ES': 'es', 'MX': 'es', 'AR': 'es', 'CO': 'es', 'CL': 'es',  # Spanish countries
                        'DE': 'de', 'AT': 'de',  # Germany, Austria
                        'FR': 'fr', 'BE': 'fr', 'CA': 'fr',  # French countries
                        'US': 'en', 'GB': 'en', 'AU': 'en', 'CA': 'en', 'IE': 'en'  # English countries
                    }
                    
                    # Check genre for language hints
                    genre_lower = genre.lower() if genre else ''
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
                    # If no genre hint, check markets
                    elif not language:
                        for market in ['IT', 'ES', 'DE', 'FR', 'US']:
                            if market in markets:
                                language = market_to_lang.get(market, 'en')
                                app.logger.info(f"Language detected from market {market}: {language}")
                                break
                    
                    # If still no language detected, default to English
                    if not language:
                        language = 'en'
                        app.logger.info(f"No language detected, defaulting to: {language}")
                else:
                    app.logger.warning("No tracks found, defaulting to English")
                    language = 'en'
            else:
                app.logger.warning("No artist ID found, defaulting to English")
                language = 'en'
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

def download_image(url, filename, tenant_slug=None):
    """Download image from URL and save to tenant-specific or shared directory."""
    from utils.tenant_utils import get_tenant_dir
    
    try:
        # Add timeout and disable SSL verification if needed (for compatibility)
        response = requests.get(url, stream=True, timeout=10, verify=True)
        if response.status_code == 200:
            safe_filename = secure_filename(filename)
            
            # Use tenant-specific directory if tenant_slug is provided
            if tenant_slug:
                image_dir = get_tenant_dir(app, tenant_slug, 'author_images')
            else:
                image_dir = app.config['UPLOAD_FOLDER']
            
            filepath = os.path.join(image_dir, safe_filename)
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)
            return safe_filename
    except requests.exceptions.SSLError as e:
        app.logger.error(f"SSL Error downloading image from {url}: {e}")
        # Try again without SSL verification as fallback
        try:
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            response = requests.get(url, stream=True, timeout=10, verify=False)
            if response.status_code == 200:
                safe_filename = secure_filename(filename)
                if tenant_slug:
                    image_dir = get_tenant_dir(app, tenant_slug, 'author_images')
                else:
                    image_dir = app.config['UPLOAD_FOLDER']
                filepath = os.path.join(image_dir, safe_filename)
                with open(filepath, 'wb') as f:
                    for chunk in response.iter_content(1024):
                        f.write(chunk)
                return safe_filename
        except Exception as fallback_error:
            app.logger.error(f"Fallback download also failed: {fallback_error}")
            return None
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Error downloading image from {url}: {e}")
        return None
    except Exception as e:
        app.logger.error(f"Unexpected error downloading image: {e}")
        return None
    
    return None

@app.route('/fetch_spotify_image', methods=['POST'])
def fetch_spotify_image():
    """Fetch image from Spotify (legacy route)."""
    author = request.form.get('author')
    if not author:
        return jsonify({'message': 'Author name is required'}), 400

    # Get tenant_slug from session if available
    tenant_slug = session.get('tenant_slug')
    
    try:
        app.logger.info(f"Fetching Spotify data for: {author}")
        artist_data = get_spotify_image(author)
        
        if artist_data is None:
            app.logger.warning(f"No Spotify data returned for: {author}")
            return jsonify({'message': 'Spotify API timeout or error. Please check your internet connection and try again.'}), 408
            
        if artist_data and artist_data.get('image_url'):
            # Normalize filename: lowercase, replace spaces with underscores
            normalized_author = author.lower().replace(' ', '_')
            filename = f"{normalized_author}.jpg"
            saved_filename = download_image(artist_data['image_url'], filename, tenant_slug)
            if saved_filename:
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
            else:
                return jsonify({'message': 'Failed to download image due to SSL/connection error. Image URL found but download failed.'}), 500
        return jsonify({'message': 'Artist not found on Spotify. Check the spelling or try a different name.'}), 404
    except Exception as e:
        app.logger.error(f"Error in fetch_spotify_image: {e}")
        return jsonify({'message': f'Error fetching from Spotify: {str(e)}'}), 500

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
        
        # Get all songs for this tenant that need data
        cursor.execute('''
            SELECT id, title, author, image, genre, language 
            FROM songs 
            WHERE tenant_id = ?
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
                    image_path = os.path.join('static', 'tenants', tenant_slug, 'author_images', song['image'])
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
                        # Normalize filename: lowercase, replace spaces with underscores
                        normalized_artist = artist_name.lower().replace(' ', '_')
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
                    if needs_language and artist_data.get('language'):
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
    """Count how many songs need data from Spotify."""
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
    
    # Count all songs (we'll check if they need data in the message)
    cursor.execute('SELECT COUNT(*) as total FROM songs WHERE tenant_id = ?', (tenant_id,))
    result = cursor.fetchone()
    total_songs = result['total'] if result else 0
    
    conn.close()
    
    return jsonify({
        'success': True,
        'total_songs': total_songs
    })

@app.route('/<tenant_slug>/bulk_fetch_spotify', methods=['POST'])
def tenant_bulk_fetch_spotify(tenant_slug):
    """Fetch images, genres, and languages from Spotify synchronously."""
    import time
    
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
    
    # Get max batch size from request (default 500)
    request_data = request.json if request.json else {}
    batch_size = min(int(request_data.get('batch_size', 500)), 1000)
    
    try:
        # First, count total songs that might need data
        cursor.execute('SELECT COUNT(*) as total FROM songs WHERE tenant_id = ?', (tenant_id,))
        total_result = cursor.fetchone()
        total_in_db = total_result['total'] if total_result else 0
        
        # Get all songs for this tenant that need data
        cursor.execute('''
            SELECT id, title, author, image, genre, language 
            FROM songs 
            WHERE tenant_id = ?
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
                if not needs_image and song['image']:
                    import os
                    image_path = os.path.join('static', 'tenants', tenant_slug, 'author_images', song['image'])
                    if not os.path.exists(image_path):
                        needs_image = True
                
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
                    # Fetch from Spotify
                    artist_data = get_spotify_image(artist_name)
                    processed_artists[artist_name] = artist_data
                    time.sleep(0.1)  # Small delay to avoid rate limiting
                
                if artist_data:
                    updates = []
                    params = []
                    
                    # Update image if needed
                    if needs_image and artist_data.get('image_url'):
                        normalized_artist = artist_name.lower().replace(' ', '_')
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
                    if needs_language and artist_data.get('language'):
                        updates.append('language = ?')
                        params.append(artist_data['language'])
                        stats['languages_added'] += 1
                    
                    # Perform update if we have changes
                    if updates:
                        params.append(song['id'])
                        query = f"UPDATE songs SET {', '.join(updates)} WHERE id = ?"
                        cursor.execute(query, tuple(params))
                        conn.commit()
                else:
                    stats['errors'] += 1
                    
            except Exception as e:
                app.logger.error(f"Error processing song {song['id']}: {e}")
                stats['errors'] += 1
                continue
        
        conn.close()
        
        # Build message with info about remaining songs
        message = f"Processed {stats['total']} songs: {stats['images_fetched']} images, {stats['genres_added']} genres, {stats['languages_added']} languages"
        
        # Check if there are more songs to process
        remaining = total_in_db - stats['total']
        has_more = remaining > 0
        
        app.logger.info(f"Bulk fetch completed for {tenant_slug}: {message}")
        
        return jsonify({
            'success': True,
            'message': message,
            'stats': stats,
            'total_in_db': total_in_db,
            'has_more': has_more,
            'remaining': remaining
        })
        
    except Exception as e:
        conn.close()
        app.logger.error(f"Error in bulk fetch for {tenant_slug}: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

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
    api_token = '5e76f4491650da91c0152a43a6ba5d8d9d765d66'
    username = 'vittorioviarengo'
    domain_name = 'vittorioviarengo.pythonanywhere.com'
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
    async_reload()
    return jsonify({"message": "Reload initiated. Please wait for the application to restart."})


#--------------------------------------------- Main Functions  ---------------------------------------------
@app.route("/")
def index():
    """Default index - redirect to super admin or show error"""
    return render_template('error.html', 
                         title='Invalid Access',
                         message='Please use a valid tenant URL (e.g., /your-artist-name/) or access the super admin panel.',
                         contact_email='admin@example.com')

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
        email = request.form.get('email')
        password = request.form.get('password')
        
        print(f"DEBUG tenant_login POST: email={email}, tenant_email={tenant['email']}")
        
        if email == tenant['email'] and check_password_hash(tenant['password'], password):
            session['is_tenant_admin'] = True
            session['tenant_id'] = tenant['id']
            session['tenant_slug'] = tenant_slug
            # Set default language to tenant's preferred language
            try:
                session['language'] = tenant['preferred_language'] if tenant['preferred_language'] else 'en'
            except (KeyError, IndexError):
                session['language'] = 'en'
            
            # Update last login time
            cursor.execute('UPDATE tenants SET last_login_at = CURRENT_TIMESTAMP WHERE id = ?', (tenant['id'],))
            conn.commit()
            
            # Check if wizard needs to be completed
            wizard_completed = tenant['wizard_completed'] if tenant['wizard_completed'] else 0
            has_essential_data = tenant['slug'] and tenant['name']
            
            conn.close()
            
            # Redirect to wizard if not completed or missing essential data
            if not wizard_completed or not has_essential_data:
                return redirect(url_for('wizard', tenant_slug=tenant_slug))
            
            return redirect(url_for('tenant_admin', tenant_slug=tenant_slug))
        else:
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
                    flash('Password reset email sent! Check your inbox.')
                except Exception as e:
                    print(f"Error sending reset email: {e}")
                    flash('Email system not configured. Please contact support.')
            else:
                flash(f'Password reset link (email not configured): /{tenant_slug}/reset-password/{reset_token}')
        else:
            # Don't reveal if email exists or not (security best practice)
            flash('If that email is registered, a password reset link has been sent.')
        
        conn.close()
        return redirect(url_for('tenant_login', tenant_slug=tenant_slug))
    
    conn.close()
    return render_template('forgot_password.html', tenant=tenant)

@app.route('/<tenant_slug>/reset-password/<token>', methods=['GET', 'POST'])
def tenant_reset_password(tenant_slug, token):
    """Tenant reset password page - set new password with token."""
    from utils.password_utils import is_token_valid
    from werkzeug.security import generate_password_hash
    
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
    
    return render_template('queue.html', is_admin=is_admin, current_datetime=current_datetime, venue_name=venue_name, max_requests=max_requests, tenant=tenant)

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
    
    return render_template('help.html', tenant=tenant)

@app.route('/<tenant_slug>/search', methods=['GET', 'POST'])
def tenant_search(tenant_slug):
    """Tenant-specific search page."""
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
        return render_template('search.html', user_name=user_name, language=language, songs=songs, can_request_songs=False, tenant=tenant)
    
    # If username is not empty, check if the session is valid
    if not is_session_valid():
        # Reset username and redirect if session is not valid
        app.logger.debug(f'redirecting to scan_qr for user: {user_name}')
        session['user_name'] = ''
        return redirect(url_for('scan_qr'))
    
    # If session is valid and username is not empty, fetch and render the search page with song data
    # Pass user_name to exclude songs already requested by this user
    songs = fetch_songs('all', search_query, language, tenant_id=tenant['id'], user_name=user_name)
    return render_template('search.html', user_name=user_name, language=language, songs=songs, can_request_songs=True, tenant=tenant)


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

def count_user_requests(user_name, tenant_id=None):
    # Filter by tenant_id if available
    if tenant_id:
        result = fetch_results("SELECT COUNT(*) AS request_count FROM requests WHERE requester = ? AND tenant_id = ?", (user_name, tenant_id))
    else:
        result = fetch_results("SELECT COUNT(*) AS request_count FROM requests WHERE requester = ?", (user_name,))
    
    if result:
        return result[0]['request_count']
    return 0

@app.route('/set_timestamp', methods=['POST'])
def set_timestamp():
    timestamp = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    session['last_visited'] = timestamp
    return jsonify({"status": "success"})









@app.route('/get_queue', methods=['GET'])
def get_queue():
    tenant_id = session.get('tenant_id')
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT s.id as song_id, s.title, s.author, s.image, GROUP_CONCAT(r.requester) as requesters, MIN(r.request_time) as request_time
        FROM requests r
        JOIN songs s ON r.song_id = s.id
        WHERE r.tenant_id = ?
        GROUP BY r.song_id
        ORDER BY request_time ASC
    """, (tenant_id,))
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
        
        # Filter by tenant_id if available
        if tenant_id:
            query = """
                SELECT s.id as song_id, s.title, s.author, s.image, GROUP_CONCAT(r.requester) as requesters
                FROM requests r
                JOIN songs s ON r.song_id = s.id
                WHERE r.requester = ? AND r.tenant_id = ?
                GROUP BY r.song_id
                ORDER BY MIN(r.request_time) ASC
            """
            cursor.execute(query, (user_name, tenant_id))
        else:
            query = """
                SELECT s.id as song_id, s.title, s.author, s.image, GROUP_CONCAT(r.requester) as requesters
                FROM requests r
                JOIN songs s ON r.song_id = s.id
                WHERE r.requester = ?
                GROUP BY r.song_id
                ORDER BY MIN(r.request_time) ASC
            """
            cursor.execute(query, (user_name,))
            
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
    
    return render_template('scan_qr.html', tenant=tenant)

@app.route('/search_mobile')
def search_mobile():
    session.pop('last_visited', None)
    tenant = None
    if session.get('tenant_id'):
        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM tenants WHERE id = ?', (session.get('tenant_id'),))
        tenant = cursor.fetchone()
        conn.close()
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
def check_session():
    if not is_session_valid():
        return jsonify({'redirect': url_for('scan_qr')})
    return jsonify({'status': 'valid'})


@app.route('/api/user_requested_song_ids', methods=['GET'])
def get_user_requested_song_ids():
    """Get list of song IDs currently requested by the user (for polling)."""
    user_name = session.get('user_name')
    tenant_id = session.get('tenant_id')
    
    if not user_name or not tenant_id:
        return jsonify({'requested_song_ids': []})
    
    try:
        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT song_id FROM requests WHERE requester = ? AND tenant_id = ?', (user_name, tenant_id))
        requests = cursor.fetchall()
        conn.close()
        
        requested_song_ids = [req['song_id'] for req in requests]
        return jsonify({'requested_song_ids': requested_song_ids})
    except Exception as e:
        app.logger.error(f"Error fetching user requests: {e}")
        return jsonify({'requested_song_ids': []})

@app.route('/request_song/<int:song_id>', methods=['POST'])
def request_song(song_id):


    if not is_session_valid():
        return jsonify({'redirect': url_for('scan_qr')})


    try:
        data = request.get_json()
        user_name = data.get('user')
        if not user_name:
            return jsonify({'error': _('User Required')}), 400

        # Get tenant_id from session
        tenant_id = session.get('tenant_id')
        
        max_requests = int(get_setting('max_requests_per_user', tenant_id))  # Ensure max_requests is an integer with tenant isolation
        user_requests = count_user_requests(user_name, tenant_id)

        if user_requests >= max_requests:
            return jsonify({'error': _('Maximum Request Reached')}), 400

        conn = create_connection()
        cursor = conn.cursor()
        
        # Fetch the current number of requests for the song (with tenant isolation)
        cursor.execute('SELECT requests FROM songs WHERE id = ? AND tenant_id = ?', (song_id, tenant_id))
        song = cursor.fetchone()
        if not song:
            return jsonify({'error': 'Song not found'}), 404

        # Check if the user has already requested the song
        cursor.execute('SELECT COUNT(*) as count FROM requests WHERE song_id = ? AND requester = ? AND tenant_id = ?', (song_id, user_name, tenant_id))
        user_requested_song = cursor.fetchone()

        if user_requested_song['count'] > 0:
            return jsonify({'error': _('Song Already Requested')}), 400

        # Increment the request count
        cursor.execute('UPDATE songs SET requests = requests + 1 WHERE id = ? AND tenant_id = ?', (song_id, tenant_id))

        # Add the song to the queue with tenant_id
        cursor.execute('INSERT INTO requests (song_id, requester, tenant_id) VALUES (?, ?, ?)', (song_id, user_name, tenant_id))

        conn.commit()
        conn.close()

        # Return success message
        return jsonify({'success': True, 'message': _('Song request successful')}), 200

    except Exception as e:
        app.logger.error(f"Error incrementing request: {e}")
        return jsonify({'error': _('Song Request Error')}), 500

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
    
    # Filter by tenant_id if available
    if tenant_id:
        cursor.execute('DELETE FROM requests WHERE tenant_id = ?', (tenant_id,))
    else:
        cursor.execute('DELETE FROM requests')
    
    conn.commit()
    conn.close()
    return render_queue()


@app.route('/delete_request/<int:song_id>', methods=['POST'])
def delete_request(song_id):
    try:
        tenant_id = session.get('tenant_id')
        conn = create_connection()
        cursor = conn.cursor()
        
        # Filter by tenant_id if available
        if tenant_id:
            cursor.execute("DELETE FROM requests WHERE song_id = ? AND tenant_id = ?", (song_id, tenant_id))
        else:
            cursor.execute("DELETE FROM requests WHERE song_id = ?", (song_id,))
        
        conn.commit()
        conn.close()
        return jsonify({"message": "Song removed from queue successfully"})
    except Exception as e:
        print(f"Error removing song from queue: {e}")
        return jsonify({"message": "Error removing song from queue"}), 500


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
    # Get tenant_id from session for data isolation
    tenant_id = session.get('tenant_id')
    
    conn = create_connection()
    cursor = conn.cursor()
    
    try:
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
        
        message = f'Song deleted successfully'
        if requests_deleted > 0:
            message += f' (also removed {requests_deleted} associated request(s) from queue)'
        
        app.logger.info(f"Deleted song {id} and {requests_deleted} associated requests for tenant {tenant_id}")
        
        return jsonify({'message': message}), 200
        
    except Exception as e:
        conn.rollback()
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


@app.route('/search_old', methods=['GET', 'POST'])
def search_old():
    user_name = request.form.get('user_name', request.args.get('user_name', session.get('user_name', '')))
    language = request.form.get('lang', request.args.get('lang', session.get('language', 'en')))
    search_query = request.args.get('s', '')  # Assuming there's a query parameter 's' for search queries

    # Set session variables
    session['user_name'] = user_name
    session['language'] = language
    
    app.logger.debug(f'Loading Search.html for user: {user_name}')
    app.logger.debug(f'Language: {language}')
    app.logger.debug(f'Search query: {search_query}')
    
    # Check if the username is empty
    if user_name == '':
        app.logger.debug('Rendering Search.html')
        return render_template('search.html')

    # If username is not empty, check if the session is valid
    if not is_session_valid():
        # Reset username and redirect if session is not valid
        app.logger.debug(f'redirecting to scan_qr for user: {user_name}')
        

        session['user_name'] = ''
        return redirect(url_for('scan_qr'))

    # If session is valid and username is not empty, fetch and render the search page with song data
    # Assuming 'all' is a valid argument for start_letter to fetch all songs
    songs = fetch_songs('all', search_query, language)
    return render_template('search.html', user_name=user_name, language=language, songs=songs)

@app.route('/search_works', methods=['GET', 'POST'])
def search_works():
    if not is_session_valid():
        return redirect('scan_qr')

    user_name = request.form.get('user_name', request.args.get('user_name', session.get('user_name', '')))
    language = request.form.get('lang', request.args.get('lang', session.get('language', 'en')))

    if (user_name == '') :
        can_request_songs = False

    session['user_name'] = user_name
    session['language'] = language


    if request.method == 'POST':
        return redirect(url_for('search', user_name=user_name, lang=language))

    # Handle the case where 's' might be None
    search_query = request.args.get('s', '')
    if search_query:
        search_query = search_query.strip().lower()

    songs = fetch_songs(request.args.get('letter', 'all'), search_query, language)
    return render_template('search.html', user_name=user_name, language=language, can_request_songs=can_request_songs, songs=songs)

@app.route('/get_all_songs', methods=['GET'])
def get_all_songs():
    sort_by = request.args.get('sort_by', 'title')  # Default sort by title
    sort_order = request.args.get('sort_order', 'asc')  # Default sort order ascending
    page = int(request.args.get('page', 1))  # Default to page 1
    per_page = int(request.args.get('per_page', 10))  # Default to 10 songs per page
    search_query = request.args.get('search', '')  # Default to empty search query

    # Get tenant_id from session for data isolation
    tenant_id = session.get('tenant_id')

    # Validate sort_by and sort_order
    valid_columns = ['title', 'author', 'language', 'popularity']
    if sort_by not in valid_columns:
        sort_by = 'title'
    if sort_order not in ['asc', 'desc']:
        sort_order = 'asc'

    offset = (page - 1) * per_page

    conn = create_connection()
    cursor = conn.cursor()
    
    # Filter by tenant_id if available
    if tenant_id:
        query = f'''
            SELECT * FROM songs
            WHERE (title LIKE ? OR author LIKE ? OR language LIKE ?) AND tenant_id = ?
            ORDER BY {sort_by} {sort_order}
            LIMIT {per_page} OFFSET {offset}
        '''
        cursor.execute(query, (f'%{search_query}%', f'%{search_query}%', f'%{search_query}%', tenant_id))
    else:
        query = f'''
            SELECT * FROM songs
            WHERE title LIKE ? OR author LIKE ? OR language LIKE ?
            ORDER BY {sort_by} {sort_order}
            LIMIT {per_page} OFFSET {offset}
        '''
        cursor.execute(query, (f'%{search_query}%', f'%{search_query}%', f'%{search_query}%'))
    
    songs = cursor.fetchall()
    conn.close()

    songs_list = [dict(song) for song in songs]
    return jsonify(songs_list)

@app.route('/update_song/<int:song_id>', methods=['POST'])
def update_song(song_id):
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

        # Get tenant_id from session for data isolation
        tenant_id = session.get('tenant_id')
        
        conn = create_connection()
        cursor = conn.cursor()
        
        # Filter by tenant_id if available
        if tenant_id:
            cursor.execute("""
                UPDATE songs
                SET title = ?, author = ?, language = ?, popularity = ?, image = ?, genre = ?, playlist = ?
                WHERE id = ? AND tenant_id = ?
            """, (title, author, language, popularity, image, genre, playlist, song_id, tenant_id))
        else:
            cursor.execute("""
                UPDATE songs
                SET title = ?, author = ?, language = ?, popularity = ?, image = ?, genre = ?, playlist = ?
                WHERE id = ?
            """, (title, author, language, popularity, image, genre, playlist, song_id))
        
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



if __name__ == '__main__':
    #app.run(debug=True)
    app.run(host='0.0.0.0', port=5001, debug=True)


    

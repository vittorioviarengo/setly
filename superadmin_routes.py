from functools import wraps
import time
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash, generate_password_hash
from flask import current_app as app
from utils.tenant_utils import get_tenant_dir
import sqlite3
import os
from flask_mail import Mail, Message

superadmin = Blueprint('superadmin', __name__)

def create_connection():
    """Create a database connection to the SQLite database."""
    database_path = os.path.join(os.path.dirname(__file__), 'songs.db')
    conn = None
    try:
        conn = sqlite3.connect(database_path)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        print(f"Error connecting to database: {e}")
    return conn

def superadmin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_superadmin'):
            return redirect(url_for('superadmin.login'))
        return f(*args, **kwargs)
    return decorated_function

def send_invitation_email(tenant_email, tenant_name, tenant_slug, setup_url, language='en'):
    """Send invitation email to new tenant with password setup link in their preferred language."""
    from utils.email_templates import get_invitation_email
    
    # Check if email is configured
    if not app.config.get('MAIL_USERNAME') or not app.config.get('MAIL_PASSWORD'):
        error_msg = "Email not configured. Set MAIL_USERNAME and MAIL_PASSWORD environment variables to enable email invitations."
        print(error_msg)
        return error_msg
    
    try:
        # Initialize mail if not already done
        mail = Mail(app)
        
        # Get multilingual email content
        subject, html_body, text_body = get_invitation_email(language, tenant_name, tenant_email, setup_url)
        
        msg = Message(
            subject=subject,
            sender=app.config.get('MAIL_DEFAULT_SENDER', 'noreply@setly.app'),
            recipients=[tenant_email]
        )
        
        msg.html = html_body
        msg.body = text_body
        
        mail.send(msg)
        print(f"✅ Invitation email sent successfully to {tenant_email}")
        return True
    except Exception as e:
        error_msg = f"Error sending invitation email: {str(e)}"
        print(error_msg)
        import traceback
        traceback.print_exc()
        return error_msg

@superadmin.route('/superadmin/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM super_admins WHERE email = ?', (username,))
        admin = cursor.fetchone()
        conn.close()

        if admin and check_password_hash(admin['password_hash'], password):
            # Make session permanent so it persists across browser tabs/closing
            session.permanent = True
            
            session['is_superadmin'] = True
            session['superadmin_id'] = admin['id']
            return redirect(url_for('superadmin.dashboard'))
        
        flash('Invalid username or password')
    return render_template('superadmin/login.html')

@superadmin.route('/superadmin/dashboard')
@superadmin_required
def dashboard():
    conn = create_connection()
    cursor = conn.cursor()
    
    # Get basic stats
    cursor.execute('SELECT COUNT(*) as tenant_count FROM tenants')
    tenant_count = cursor.fetchone()['tenant_count']
    
    cursor.execute('SELECT COUNT(*) as song_count FROM songs')
    song_count = cursor.fetchone()['song_count']
    
    # Total requests all-time (all statuses)
    cursor.execute('SELECT COUNT(*) as request_count FROM requests')
    total_request_count = cursor.fetchone()['request_count']
    
    # Currently open requests (pending status only, excluding fulfilled/cancelled)
    # Check if status column exists
    try:
        cursor.execute("SELECT COUNT(*) as open_count FROM requests WHERE status = 'pending'")
        open_request_count = cursor.fetchone()['open_count']
        # If no pending requests but status column exists, check for NULL (old requests before migration)
        if open_request_count == 0:
            cursor.execute("SELECT COUNT(*) as null_count FROM requests WHERE status IS NULL")
            null_count = cursor.fetchone()['null_count']
            if null_count > 0:
                # Old requests without status - consider them as pending for now
                open_request_count = null_count
    except sqlite3.OperationalError:
        # If status column doesn't exist yet, all requests are considered open
        open_request_count = total_request_count
    
    # Get recent tenants with song and request counts
    cursor.execute('''
        SELECT 
            t.*,
            COALESCE(COUNT(DISTINCT s.id), 0) as song_count,
            COALESCE(COUNT(DISTINCT r.id), 0) as request_count
        FROM tenants t
        LEFT JOIN songs s ON s.tenant_id = t.id
        LEFT JOIN requests r ON r.tenant_id = t.id
        GROUP BY t.id
        ORDER BY t.created_at DESC 
        LIMIT 5
    ''')
    recent_tenants = cursor.fetchall()
    
    conn.close()
    
    return render_template('superadmin/dashboard.html',
                         tenant_count=tenant_count,
                         song_count=song_count,
                         total_request_count=total_request_count,
                         open_request_count=open_request_count,
                         recent_tenants=recent_tenants)

@superadmin.route('/superadmin/tenants')
@superadmin_required
def tenants():
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM tenants ORDER BY created_at DESC')
    tenants = cursor.fetchall()
    conn.close()
    return render_template('superadmin/tenants.html', tenants=tenants)

@superadmin.route('/superadmin/invitations')
@superadmin_required
def invitations():
    """View all pending and completed invitations"""
    print("DEBUG: Invitations route called")
    conn = create_connection()
    cursor = conn.cursor()
    
    # Get all invitations with tenant info
    cursor.execute('''
        SELECT 
            invitations.*,
            tenants.name as invited_by_name,
            tenants.slug as invited_by_slug
        FROM invitations
        LEFT JOIN tenants ON invitations.invited_by = tenants.id
        ORDER BY invitations.sent_at DESC
    ''')
    all_invitations = cursor.fetchall()
    
    print(f"DEBUG: Found {len(all_invitations)} invitations")
    for inv in all_invitations:
        print(f"DEBUG: Invitation: {dict(inv)}")
    
    conn.close()
    return render_template('superadmin/invitations.html', invitations=all_invitations)

@superadmin.route('/superadmin/invitation/<int:id>/resend', methods=['POST'])
@superadmin_required
def resend_invitation(id):
    """Resend an invitation"""
    conn = create_connection()
    cursor = conn.cursor()
    
    # Get invitation details
    cursor.execute('''
        SELECT invitations.*, tenants.name, tenants.slug, tenants.referral_code
        FROM invitations
        LEFT JOIN tenants ON invitations.invited_by = tenants.id
        WHERE invitations.id = ?
    ''', (id,))
    invitation = cursor.fetchone()
    
    if not invitation:
        conn.close()
        flash('Invitation not found', 'error')
        return redirect(url_for('superadmin.invitations'))
    
    # Update sent_at timestamp
    cursor.execute('''
        UPDATE invitations
        SET sent_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (id,))
    conn.commit()
    conn.close()
    
    # TODO: Actually resend the email here
    flash(f'Invitation resent to {invitation["email"]}', 'success')
    return redirect(url_for('superadmin.invitations'))

@superadmin.route('/superadmin/invitation/<int:id>/cancel', methods=['POST'])
@superadmin_required
def cancel_invitation(id):
    """Cancel a pending invitation"""
    conn = create_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE invitations
        SET status = 'cancelled', cancelled_at = CURRENT_TIMESTAMP
        WHERE id = ? AND status = 'pending'
    ''', (id,))
    conn.commit()
    conn.close()
    
    flash('Invitation cancelled', 'success')
    return redirect(url_for('superadmin.invitations'))

@superadmin.route('/superadmin/tenant/new', methods=['GET', 'POST'])
@superadmin_required
def new_tenant():
    if request.method == 'POST':
        print("Received POST request to create new tenant")
        print("Form data:", request.form)
        from utils.password_utils import generate_reset_token, get_token_expiry
        
        name = request.form.get('name')
        slug = request.form.get('slug')
        email = request.form.get('email')
        website_url = request.form.get('website_url')
        events_link = request.form.get('events_link')
        preferred_language = request.form.get('preferred_language', 'en')
        active = bool(request.form.get('active'))
        paypal_enabled = bool(request.form.get('paypal_enabled'))
        paypal_link = request.form.get('paypal_link')
        venmo_enabled = bool(request.form.get('venmo_enabled'))
        venmo_link = request.form.get('venmo_link')

        # Validate required fields (password is no longer required, will be set via email)
        if not all([name, slug, email]):
            flash('Please fill in all required fields')
            # Pass form data back to preserve user input
            form_data = {
                'name': name,
                'slug': slug,
                'email': email,
                'website_url': website_url,
                'events_link': events_link,
                'preferred_language': preferred_language,
                'paypal_enabled': paypal_enabled,
                'paypal_link': paypal_link,
                'venmo_enabled': venmo_enabled,
                'venmo_link': venmo_link,
                'active': active
            }
            return render_template('superadmin/tenant_form.html', form_data=form_data)

        # Handle logo upload
        logo_image = None
        if 'logo' in request.files:
            file = request.files['logo']
            if file.filename:
                # Validate file type
                allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
                ext = os.path.splitext(file.filename)[1].lower().lstrip('.')
                if ext not in allowed_extensions:
                    flash('Invalid file type. Allowed types: PNG, JPG, JPEG, GIF, WEBP')
                    return render_template('superadmin/tenant_form.html')
                
                # Get tenant's logos directory
                logos_dir = get_tenant_dir(app, slug, 'logos')
                
                # Generate unique filename with timestamp
                filename = f"logo_{int(time.time())}.{ext}"
                filename = secure_filename(filename)
                
                # Save the file in tenant's logos directory
                file_path = os.path.join(logos_dir, filename)
                file.save(file_path)
                # Store relative path from static directory
                logo_image = os.path.join('tenants', slug, 'logos', filename)

        # Handle banner upload
        banner_image = None
        if 'banner' in request.files:
            file = request.files['banner']
            if file.filename:
                # Validate file type
                allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
                ext = os.path.splitext(file.filename)[1].lower().lstrip('.')
                if ext not in allowed_extensions:
                    flash('Invalid file type. Allowed types: PNG, JPG, JPEG, GIF, WEBP')
                    return render_template('superadmin/tenant_form.html')
                
                # Get tenant's images directory
                images_dir = get_tenant_dir(app, slug, 'images')
                
                # Generate unique filename with timestamp
                filename = f"banner_{int(time.time())}.{ext}"
                filename = secure_filename(filename)
                
                # Save the file in tenant's images directory
                file_path = os.path.join(images_dir, filename)
                file.save(file_path)
                # Store relative path from static directory
                banner_image = os.path.join('tenants', slug, 'images', filename)

        conn = create_connection()
        try:
            # Check if slug is unique
            cursor = conn.cursor()
            cursor.execute('SELECT id FROM tenants WHERE slug = ?', (slug,))
            if cursor.fetchone():
                flash('This URL slug is already in use')
                # Pass form data back to preserve user input
                form_data = {
                    'name': name,
                    'slug': slug,
                    'email': email,
                    'website_url': website_url,
                    'events_link': events_link,
                    'preferred_language': preferred_language,
                    'paypal_enabled': paypal_enabled,
                    'paypal_link': paypal_link,
                    'venmo_enabled': venmo_enabled,
                    'venmo_link': venmo_link,
                    'active': active
                }
                return render_template('superadmin/tenant_form.html', form_data=form_data)
            
            # Check if email is unique
            cursor.execute('SELECT id FROM tenants WHERE email = ?', (email,))
            if cursor.fetchone():
                flash('This email address is already in use')
                # Pass form data back to preserve user input
                form_data = {
                    'name': name,
                    'slug': slug,
                    'email': email,
                    'website_url': website_url,
                    'events_link': events_link,
                    'preferred_language': preferred_language,
                    'paypal_enabled': paypal_enabled,
                    'paypal_link': paypal_link,
                    'venmo_enabled': venmo_enabled,
                    'venmo_link': venmo_link,
                    'active': active
                }
                return render_template('superadmin/tenant_form.html', form_data=form_data)

            # Create new tenant
            print("Creating new tenant with values:", {
                'name': name,
                'slug': slug,
                'email': email,
                'active': active,
                'paypal_enabled': paypal_enabled,
                'paypal_link': paypal_link,
                'venmo_enabled': venmo_enabled,
                'venmo_link': venmo_link,
                'logo_image': logo_image
            })
            try:
                # Generate setup token for password creation
                reset_token = generate_reset_token()
                token_expiry = get_token_expiry(hours=24)  # 24 hour expiry for initial setup
                
                # Generate unique referral code
                import secrets
                referral_code = secrets.token_urlsafe(8)
                while True:
                    cursor.execute('SELECT id FROM tenants WHERE referral_code = ?', (referral_code,))
                    if cursor.fetchone() is None:
                        break
                    referral_code = secrets.token_urlsafe(8)
                
                # Create tenant with no password initially (will be set via email link)
                cursor.execute('''
                    INSERT INTO tenants (
                        name, slug, email, password, website_url, events_link, preferred_language, logo_image, banner_image, active,
                        paypal_enabled, paypal_link, venmo_enabled, venmo_link,
                        reset_token, reset_token_expiry, password_set, referral_code
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (name, slug, email, '', website_url, events_link, preferred_language, logo_image, banner_image,
                      active, paypal_enabled, paypal_link, venmo_enabled, venmo_link,
                      reset_token, token_expiry, 0, referral_code))
                conn.commit()
                print("Successfully created tenant in database")
                
                # Send invitation email if requested
                send_invitation = request.form.get('send_invitation')
                if send_invitation:
                    setup_url = request.url_root + slug + '/reset-password/' + reset_token
                    if send_invitation_email(email, name, slug, setup_url, preferred_language):
                        flash(f'Tenant created successfully and invitation sent to {email}')
                    else:
                        flash(f'Tenant created successfully. Email not sent - configure email settings in env.example to enable invitations. Setup link: /{slug}/reset-password/{reset_token}')
                else:
                    flash(f'Tenant created successfully. Setup link: /{slug}/reset-password/{reset_token}')
                
                return redirect(url_for('superadmin.tenants'))
            except sqlite3.Error as e:
                print("Database error:", str(e))
                flash(f'Database error: {str(e)}')
                return render_template('superadmin/tenant_form.html')
        except Exception as e:
            flash(f'Error creating tenant: {str(e)}')
            return render_template('superadmin/tenant_form.html')
        finally:
            conn.close()

    return render_template('superadmin/tenant_form.html')

@superadmin.route('/superadmin/tenant/<int:id>/edit', methods=['GET', 'POST'])
@superadmin_required
def edit_tenant(id):
    conn = create_connection()
    cursor = conn.cursor()
    
    if request.method == 'POST':
        name = request.form.get('name')
        slug = request.form.get('slug')
        email = request.form.get('email')
        website_url = request.form.get('website_url')
        events_link = request.form.get('events_link')
        preferred_language = request.form.get('preferred_language', 'en')
        active = bool(request.form.get('active'))
        paypal_enabled = bool(request.form.get('paypal_enabled'))
        paypal_link = request.form.get('paypal_link')
        venmo_enabled = bool(request.form.get('venmo_enabled'))
        venmo_link = request.form.get('venmo_link')

        # Validate required fields
        if not all([name, slug, email]):
            flash('Please fill in all required fields')
            cursor.execute('SELECT * FROM tenants WHERE id = ?', (id,))
            tenant = cursor.fetchone()
            conn.close()
            return render_template('superadmin/tenant_form.html', tenant=tenant)

        # Handle logo upload
        logo_image = None
        if 'logo' in request.files:
            file = request.files['logo']
            if file.filename:
                # Validate file type
                allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
                ext = os.path.splitext(file.filename)[1].lower().lstrip('.')
                if ext not in allowed_extensions:
                    flash('Invalid file type. Allowed types: PNG, JPG, JPEG, GIF, WEBP')
                    cursor.execute('SELECT * FROM tenants WHERE id = ?', (id,))
                    tenant = cursor.fetchone()
                    return render_template('superadmin/tenant_form.html', tenant=tenant)
                
                # Get tenant's logos directory
                logos_dir = get_tenant_dir(app, slug, 'logos')
                
                # Delete old logo if it exists
                cursor.execute('SELECT logo_image FROM tenants WHERE id = ?', (id,))
                old_logo = cursor.fetchone()['logo_image']
                if old_logo:
                    # Convert relative path to absolute path
                    old_logo_path = os.path.join(app.config['TENANTS_BASE_DIR'], '..', old_logo)
                    try:
                        if os.path.exists(old_logo_path):
                            os.remove(old_logo_path)
                    except Exception as e:
                        print(f"Error deleting old logo: {e}")
                
                # Generate unique filename with timestamp
                filename = f"logo_{int(time.time())}.{ext}"
                filename = secure_filename(filename)
                
                # Save the file in tenant's logos directory
                file_path = os.path.join(logos_dir, filename)
                file.save(file_path)
                # Store relative path from static directory
                logo_image = os.path.join('tenants', slug, 'logos', filename)

        # Handle banner upload
        banner_image = None
        if 'banner' in request.files:
            file = request.files['banner']
            if file.filename:
                # Validate file type
                allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
                ext = os.path.splitext(file.filename)[1].lower().lstrip('.')
                if ext not in allowed_extensions:
                    flash('Invalid file type. Allowed types: PNG, JPG, JPEG, GIF, WEBP')
                    cursor.execute('SELECT * FROM tenants WHERE id = ?', (id,))
                    tenant = cursor.fetchone()
                    return render_template('superadmin/tenant_form.html', tenant=tenant)
                
                # Get tenant's images directory
                images_dir = get_tenant_dir(app, slug, 'images')
                
                # Delete old banner if it exists
                cursor.execute('SELECT banner_image FROM tenants WHERE id = ?', (id,))
                old_banner = cursor.fetchone()['banner_image']
                if old_banner:
                    # Convert relative path to absolute path
                    old_banner_path = os.path.join(app.config['TENANTS_BASE_DIR'], '..', old_banner)
                    try:
                        if os.path.exists(old_banner_path):
                            os.remove(old_banner_path)
                    except Exception as e:
                        print(f"Error deleting old banner: {e}")
                
                # Generate unique filename with timestamp
                filename = f"banner_{int(time.time())}.{ext}"
                filename = secure_filename(filename)
                
                # Save the file in tenant's images directory
                file_path = os.path.join(images_dir, filename)
                file.save(file_path)
                # Store relative path from static directory
                banner_image = os.path.join('tenants', slug, 'images', filename)

        try:
            # Check if slug is unique (excluding current tenant)
            cursor.execute('SELECT id FROM tenants WHERE slug = ? AND id != ?', (slug, id))
            if cursor.fetchone():
                flash('This URL slug is already in use')
                cursor.execute('SELECT * FROM tenants WHERE id = ?', (id,))
                tenant = cursor.fetchone()
                conn.close()
                return render_template('superadmin/tenant_form.html', tenant=tenant)
            
            # Check if email is unique (excluding current tenant)
            cursor.execute('SELECT id FROM tenants WHERE email = ? AND id != ?', (email, id))
            if cursor.fetchone():
                flash('This email address is already in use')
                cursor.execute('SELECT * FROM tenants WHERE id = ?', (id,))
                tenant = cursor.fetchone()
                conn.close()
                return render_template('superadmin/tenant_form.html', tenant=tenant)

            # Update tenant
            update_fields = [
                'name = ?',
                'slug = ?',
                'email = ?',
                'website_url = ?',
                'events_link = ?',
                'preferred_language = ?',
                'active = ?',
                'paypal_enabled = ?',
                'paypal_link = ?',
                'venmo_enabled = ?',
                'venmo_link = ?'
            ]
            params = [name, slug, email, website_url, events_link, preferred_language, active, paypal_enabled, paypal_link, venmo_enabled, venmo_link]

            # Only update password if provided
            if request.form.get('password'):
                update_fields.append('password = ?')
                params.append(generate_password_hash(request.form.get('password'), method='pbkdf2:sha256'))

            # Only update logo if provided
            if logo_image:
                update_fields.append('logo_image = ?')
                params.append(logo_image)

            # Only update banner if provided
            if banner_image:
                update_fields.append('banner_image = ?')
                params.append(banner_image)

            # Add tenant ID to params
            params.append(id)

            cursor.execute(f'''
                UPDATE tenants 
                SET {', '.join(update_fields)}
                WHERE id = ?
            ''', params)
            conn.commit()
            flash('Tenant updated successfully')
            return redirect(url_for('superadmin.tenants'))
        except Exception as e:
            flash(f'Error updating tenant: {str(e)}')
            cursor.execute('SELECT * FROM tenants WHERE id = ?', (id,))
            tenant = cursor.fetchone()
            return render_template('superadmin/tenant_form.html', tenant=tenant)
        finally:
            conn.close()

    # GET request - show edit form
    cursor.execute('SELECT * FROM tenants WHERE id = ?', (id,))
    tenant = cursor.fetchone()
    if not tenant:
        conn.close()
        flash('Tenant not found')
        return redirect(url_for('superadmin.tenants'))
    
    conn.close()
    return render_template('superadmin/tenant_form.html', tenant=tenant)

@superadmin.route('/superadmin/tenant/<int:id>/toggle', methods=['POST'])
@superadmin_required
def toggle_tenant(id):
    conn = create_connection()
    cursor = conn.cursor()
    try:
        # Get current status
        cursor.execute('SELECT active FROM tenants WHERE id = ?', (id,))
        tenant = cursor.fetchone()
        if not tenant:
            conn.close()
            return jsonify({'success': False, 'message': 'Tenant not found'})
        
        # Toggle status
        new_status = not tenant['active']
        cursor.execute('UPDATE tenants SET active = ? WHERE id = ?', (new_status, id))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    finally:
        conn.close()

@superadmin.route('/superadmin/tenant/<int:id>/delete', methods=['POST'])
@superadmin_required
def delete_tenant(id):
    """Permanently delete a tenant and ALL associated data (CASCADE DELETE)."""
    import shutil
    from utils.tenant_utils import get_tenant_dir
    
    app.logger.info(f"Delete tenant request received for ID: {id}")
    
    conn = create_connection()
    cursor = conn.cursor()
    
    # Statistics for deletion
    stats = {
        'songs_deleted': 0,
        'requests_deleted': 0,
        'images_deleted': 0,
        'directories_deleted': 0
    }
    
    try:
        # Verify confirmation from request
        data = request.json or {}
        app.logger.info(f"Request data: {data}")
        
        if not data.get('confirmed'):
            app.logger.warning("Deletion not confirmed in request")
            return jsonify({'success': False, 'message': 'Deletion not confirmed'}), 400
        
        # Check if tenant exists
        cursor.execute('SELECT * FROM tenants WHERE id = ?', (id,))
        tenant = cursor.fetchone()
        if not tenant:
            conn.close()
            return jsonify({'success': False, 'message': 'Tenant not found'}), 404
        
        tenant_slug = tenant['slug']
        tenant_name = tenant['name']
        
        # Verify tenant name matches (additional safety check)
        if data.get('tenant_name') != tenant_name:
            conn.close()
            return jsonify({'success': False, 'message': 'Tenant name verification failed'}), 400
        
        app.logger.info(f"Starting CASCADE DELETE for tenant: {tenant_name} (ID: {id}, slug: {tenant_slug})")
        
        # STEP 1: Delete all song requests/queue items for this tenant
        cursor.execute('SELECT COUNT(*) as count FROM requests WHERE tenant_id = ?', (id,))
        stats['requests_deleted'] = cursor.fetchone()['count']
        cursor.execute('DELETE FROM requests WHERE tenant_id = ?', (id,))
        app.logger.info(f"Deleted {stats['requests_deleted']} requests/queue items")
        
        # STEP 2: Delete all songs for this tenant
        cursor.execute('SELECT COUNT(*) as count FROM songs WHERE tenant_id = ?', (id,))
        stats['songs_deleted'] = cursor.fetchone()['count']
        cursor.execute('DELETE FROM songs WHERE tenant_id = ?', (id,))
        app.logger.info(f"Deleted {stats['songs_deleted']} songs")
        
        # STEP 3: Delete tenant-specific file directories
        tenant_base_dir = os.path.join(app.static_folder, 'tenants', tenant_slug)
        app.logger.info(f"Checking for tenant directory: {tenant_base_dir}")
        
        if os.path.exists(tenant_base_dir):
            try:
                # Count images before deletion
                author_images_dir = os.path.join(tenant_base_dir, 'author_images')
                if os.path.exists(author_images_dir):
                    try:
                        stats['images_deleted'] = len([f for f in os.listdir(author_images_dir) 
                                                       if os.path.isfile(os.path.join(author_images_dir, f))])
                    except Exception as e:
                        app.logger.warning(f"Could not count images: {e}")
                        stats['images_deleted'] = 0
                
                # Delete entire tenant directory
                shutil.rmtree(tenant_base_dir)
                stats['directories_deleted'] += 1
                app.logger.info(f"Deleted tenant directory: {tenant_base_dir}")
            except Exception as e:
                app.logger.error(f"Error deleting tenant directory: {e}")
                # Don't fail the entire deletion if directory removal fails
        else:
            app.logger.info(f"No tenant directory found at: {tenant_base_dir}")
        
        # STEP 4: Delete tenant's logo (if it's stored outside tenant directory)
        try:
            if tenant['logo_image'] and not tenant['logo_image'].startswith('tenants/'):
                # Legacy logos stored in shared folder
                logo_path = os.path.join(app.static_folder, tenant['logo_image'])
                if os.path.exists(logo_path):
                    os.remove(logo_path)
                    app.logger.info(f"Deleted tenant logo: {logo_path}")
                else:
                    app.logger.info(f"Logo file not found: {logo_path}")
            # Note: New logos stored in tenants/slug/logos/ are already deleted in STEP 3
        except Exception as e:
            app.logger.error(f"Error deleting logo file: {e}")
            # Don't fail the entire deletion if logo removal fails
        
        # STEP 5: Delete tenant's banner image (if it's stored outside tenant directory)
        try:
            if tenant.get('banner_image') and not tenant.get('banner_image').startswith('tenants/'):
                # Legacy banners stored in shared folder
                banner_path = os.path.join(app.static_folder, tenant['banner_image'])
                if os.path.exists(banner_path):
                    os.remove(banner_path)
                    app.logger.info(f"Deleted tenant banner: {banner_path}")
                else:
                    app.logger.info(f"Banner file not found: {banner_path}")
            # Note: New banners stored in tenants/slug/images/ are already deleted in STEP 3
        except Exception as e:
            app.logger.error(f"Error deleting banner file: {e}")
            # Don't fail the entire deletion if banner removal fails
        
        # STEP 6: Finally, delete the tenant record itself
        cursor.execute('DELETE FROM tenants WHERE id = ?', (id,))
        conn.commit()
        
        app.logger.info(f"✓ CASCADE DELETE completed for tenant: {tenant_name}")
        app.logger.info(f"  Songs deleted: {stats['songs_deleted']}")
        app.logger.info(f"  Requests deleted: {stats['requests_deleted']}")
        app.logger.info(f"  Images deleted: {stats['images_deleted']}")
        app.logger.info(f"  Directories deleted: {stats['directories_deleted']}")
        
        return jsonify({
            'success': True,
            'message': f'Tenant "{tenant_name}" and all associated data deleted successfully',
            'stats': stats
        })
        
    except Exception as e:
        conn.rollback()
        import traceback
        error_traceback = traceback.format_exc()
        app.logger.error(f"Error in CASCADE DELETE for tenant {id}: {e}")
        app.logger.error(f"Full traceback: {error_traceback}")
        return jsonify({
            'success': False, 
            'message': f'Error deleting tenant: {str(e)}',
            'error_type': type(e).__name__
        }), 500
    finally:
        conn.close()

@superadmin.route('/superadmin/tenant/<int:id>/get_setup_link', methods=['POST'])
@superadmin_required
def get_setup_link(id):
    """Generate a new setup token and return the setup link (no email sent)."""
    from utils.password_utils import generate_reset_token, get_token_expiry
    
    conn = create_connection()
    cursor = conn.cursor()
    try:
        # Get tenant details
        cursor.execute('SELECT * FROM tenants WHERE id = ?', (id,))
        tenant = cursor.fetchone()
        if not tenant:
            return jsonify({'success': False, 'message': 'Tenant not found'})
        
        # Generate new setup token
        reset_token = generate_reset_token()
        token_expiry = get_token_expiry(hours=24)
        
        # Update tenant with new token
        cursor.execute('''
            UPDATE tenants 
            SET reset_token = ?, reset_token_expiry = ?
            WHERE id = ?
        ''', (reset_token, token_expiry, id))
        conn.commit()
        
        # Build setup URL
        setup_url = request.url_root + tenant['slug'] + '/reset-password/' + reset_token
        
        return jsonify({
            'success': True, 
            'setup_url': setup_url,
            'tenant_slug': tenant['slug'],
            'tenant_email': tenant['email']
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    finally:
        conn.close()

@superadmin.route('/superadmin/tenant/<int:id>/invite', methods=['POST'])
@superadmin_required
def invite_tenant(id):
    """Send invitation email to existing tenant (generate new setup token)."""
    from utils.password_utils import generate_reset_token, get_token_expiry
    
    conn = create_connection()
    cursor = conn.cursor()
    try:
        # Get tenant details
        cursor.execute('SELECT * FROM tenants WHERE id = ?', (id,))
        tenant = cursor.fetchone()
        if not tenant:
            return jsonify({'success': False, 'message': 'Tenant not found'})
        
        # Generate new setup token
        reset_token = generate_reset_token()
        token_expiry = get_token_expiry(hours=24)
        
        # Update tenant with new token
        cursor.execute('''
            UPDATE tenants 
            SET reset_token = ?, reset_token_expiry = ?
            WHERE id = ?
        ''', (reset_token, token_expiry, id))
        conn.commit()
        
        # Send invitation email with setup link (use tenant's preferred language)
        try:
            tenant_language = tenant['preferred_language'] if tenant['preferred_language'] else 'en'
        except (KeyError, IndexError):
            tenant_language = 'en'
        setup_url = request.url_root + tenant['slug'] + '/reset-password/' + reset_token
        result = send_invitation_email(tenant['email'], tenant['name'], tenant['slug'], setup_url, tenant_language)
        if result is True:
            return jsonify({'success': True, 'email': tenant['email']})
        else:
            # result is the error message if not True
            error_msg = result if isinstance(result, str) else 'Failed to send invitation email'
            return jsonify({'success': False, 'message': error_msg})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    finally:
        conn.close()

@superadmin.route('/superadmin/tenant/<int:tenant_id>/upload_csv', methods=['POST'])
@superadmin_required
def upload_tenant_csv(tenant_id):
    """Superadmin upload CSV for a tenant (for artists who need help)."""
    import csv
    import io
    
    conn = create_connection()
    cursor = conn.cursor()
    
    # Get tenant info
    cursor.execute('SELECT * FROM tenants WHERE id = ?', (tenant_id,))
    tenant = cursor.fetchone()
    
    if not tenant:
        flash('Tenant not found')
        conn.close()
        return redirect(url_for('superadmin.tenants'))
    
    # Check if file is in request
    if 'file' not in request.files:
        flash('No file uploaded')
        conn.close()
        return redirect(url_for('superadmin.edit_tenant', id=tenant_id))
    
    file = request.files['file']
    if file.filename == '':
        flash('No file selected')
        conn.close()
        return redirect(url_for('superadmin.edit_tenant', id=tenant_id))
    
    # Validate file extension
    if not file.filename.endswith('.csv'):
        flash('Only CSV files are allowed')
        conn.close()
        return redirect(url_for('superadmin.edit_tenant', id=tenant_id))
    
    try:
        # Read CSV file
        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
        csv_reader = csv.reader(stream)
        
        songs_added = 0
        songs_skipped = 0
        errors = []
        
        for row_num, row in enumerate(csv_reader, start=1):
            try:
                # Skip empty rows
                if not row or len(row) == 0:
                    continue
                
                # Expected format: title,author,language,image,requests,popularity,genre,playlist
                if len(row) < 4:
                    errors.append(f"Row {row_num}: Not enough columns")
                    songs_skipped += 1
                    continue
                
                title = row[0].strip()
                author = row[1].strip()
                language = row[2].strip()
                image = row[3].strip()
                requests = int(row[4]) if len(row) > 4 and row[4].strip() else 0
                popularity = int(row[5]) if len(row) > 5 and row[5].strip() else 0
                genre = row[6].strip() if len(row) > 6 else ''
                playlist = row[7].strip() if len(row) > 7 else ''
                
                # Validate required fields
                if not title or not author or not language:
                    errors.append(f"Row {row_num}: Missing required fields")
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
        message = f"✅ CSV upload complete for {tenant['name']}! Added {songs_added} song(s)."
        if songs_skipped > 0:
            message += f" Skipped {songs_skipped} row(s)."
        if errors and len(errors) <= 5:
            message += f" Errors: {'; '.join(errors)}"
        
        flash(message)
        
    except Exception as e:
        conn.close()
        flash(f'Error processing CSV file: {str(e)}')
    
    return redirect(url_for('superadmin.edit_tenant', id=tenant_id))

@superadmin.route('/superadmin/tenant/<int:tenant_id>/delete_all_songs', methods=['POST'])
@superadmin_required
def delete_tenant_all_songs(tenant_id):
    """Superadmin delete all songs for a tenant."""
    conn = create_connection()
    cursor = conn.cursor()
    
    # Get tenant info
    cursor.execute('SELECT * FROM tenants WHERE id = ?', (tenant_id,))
    tenant = cursor.fetchone()
    
    if not tenant:
        conn.close()
        return jsonify({'success': False, 'message': 'Tenant not found'}), 404
    
    try:
        # Get count of songs before deletion
        cursor.execute('SELECT COUNT(*) as count FROM songs WHERE tenant_id = ?', (tenant_id,))
        count = cursor.fetchone()['count']
        
        # Delete all songs for this tenant
        cursor.execute('DELETE FROM songs WHERE tenant_id = ?', (tenant_id,))
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f"Successfully deleted {count} song(s) for {tenant['name']}"
        })
        
    except Exception as e:
        conn.close()
        return jsonify({
            'success': False,
            'message': f'Error deleting songs: {str(e)}'
        }), 500

@superadmin.route('/superadmin/settings')
@superadmin_required
def settings():
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM system_settings')
    settings = cursor.fetchall()
    conn.close()
    return render_template('superadmin/settings.html', settings=settings)

@superadmin.route('/superadmin/settings/update', methods=['POST'])
@superadmin_required
def update_setting():
    from flask import jsonify, request
    from datetime import datetime
    
    try:
        data = request.get_json()
        key = data.get('key')
        value = data.get('value')
        
        if not key or value is None:
            return jsonify({'success': False, 'message': 'Key and value are required'}), 400
        
        conn = create_connection()
        cursor = conn.cursor()
        
        # Update the setting
        cursor.execute('''
            UPDATE system_settings 
            SET value = ?, updated_at = CURRENT_TIMESTAMP 
            WHERE key = ?
        ''', (value, key))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Setting updated successfully'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@superadmin.route('/superadmin/settings/upload-icon', methods=['POST'])
@superadmin_required
def upload_icon():
    """Upload favicon or app icon."""
    from flask import jsonify, request
    
    try:
        icon_type = request.form.get('icon_type')  # 'favicon' or 'app_icon'
        
        if icon_type not in ['favicon', 'app_icon']:
            return jsonify({'success': False, 'message': 'Invalid icon type'}), 400
        
        if 'file' not in request.files:
            return jsonify({'success': False, 'message': 'No file provided'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'success': False, 'message': 'No file selected'}), 400
        
        # Validate file extension
        allowed_extensions = {'.ico', '.png', '.jpg', '.jpeg', '.svg'}
        file_ext = os.path.splitext(file.filename)[1].lower()
        
        if file_ext not in allowed_extensions:
            return jsonify({'success': False, 'message': 'Invalid file type. Allowed: ico, png, jpg, svg'}), 400
        
        # Generate filename
        filename = secure_filename(file.filename)
        timestamp = str(int(time.time()))
        
        if icon_type == 'favicon':
            # For favicon, keep the .ico extension or use .png
            if file_ext == '.ico':
                final_filename = 'favicon.ico'
            else:
                final_filename = f'favicon_{timestamp}{file_ext}'
        else:
            final_filename = f'app-icon_{timestamp}{file_ext}'
        
        # Save to static/icons
        icons_dir = os.path.join(os.path.dirname(__file__), 'static', 'icons')
        os.makedirs(icons_dir, exist_ok=True)
        
        file_path = os.path.join(icons_dir, final_filename)
        file.save(file_path)
        
        # Update database
        relative_path = f'icons/{final_filename}'
        
        conn = create_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE system_settings 
            SET value = ?, updated_at = CURRENT_TIMESTAMP 
            WHERE key = ?
        ''', (relative_path, icon_type))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True, 
            'message': f'{icon_type} uploaded successfully',
            'filename': relative_path
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@superadmin.route('/superadmin/logs')
@superadmin_required
def logs():
    """Enhanced audit logs viewer with filtering, pagination, and search."""
    conn = create_connection()
    cursor = conn.cursor()
    
    # Get filter parameters
    action_filter = request.args.get('action', '')
    tenant_id_filter = request.args.get('tenant_id', '')
    user_type_filter = request.args.get('user_type', '')
    entity_type_filter = request.args.get('entity_type', '')
    search_query = request.args.get('search', '')
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 50))
    
    # Build WHERE clause
    where_clauses = []
    params = []
    
    if action_filter:
        where_clauses.append("action LIKE ?")
        params.append(f"%{action_filter}%")
    
    if tenant_id_filter:
        try:
            where_clauses.append("tenant_id = ?")
            params.append(int(tenant_id_filter))
        except (ValueError, TypeError):
            pass  # Skip invalid tenant_id
    
    if user_type_filter:
        where_clauses.append("user_type = ?")
        params.append(user_type_filter)
    
    if entity_type_filter:
        where_clauses.append("entity_type = ?")
        params.append(entity_type_filter)
    
    if search_query:
        where_clauses.append("(details LIKE ? OR action LIKE ? OR user_name LIKE ?)")
        params.extend([f"%{search_query}%", f"%{search_query}%", f"%{search_query}%"])
    
    where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""
    
    # Get total count for pagination
    count_query = f"SELECT COUNT(*) as total FROM audit_logs {where_sql}"
    cursor.execute(count_query, tuple(params))
    total_logs = cursor.fetchone()['total']
    total_pages = (total_logs + per_page - 1) // per_page
    
    # Get logs with pagination
    offset = (page - 1) * per_page
    query = f'''
        SELECT 
            al.*,
            t.name as tenant_name,
            t.slug as tenant_slug
        FROM audit_logs al
        LEFT JOIN tenants t ON al.tenant_id = t.id
        {where_sql}
        ORDER BY al.created_at DESC 
        LIMIT ? OFFSET ?
    '''
    params.extend([per_page, offset])
    cursor.execute(query, tuple(params))
    logs = cursor.fetchall()
    
    # Get unique values for filter dropdowns
    cursor.execute("SELECT DISTINCT action FROM audit_logs ORDER BY action")
    available_actions = [row['action'] for row in cursor.fetchall()]
    
    cursor.execute("SELECT DISTINCT user_type FROM audit_logs WHERE user_type IS NOT NULL ORDER BY user_type")
    available_user_types = [row['user_type'] for row in cursor.fetchall()]
    
    cursor.execute("SELECT DISTINCT entity_type FROM audit_logs ORDER BY entity_type")
    available_entity_types = [row['entity_type'] for row in cursor.fetchall()]
    
    # Get tenant list for filter
    cursor.execute("SELECT DISTINCT al.tenant_id, t.name, t.slug FROM audit_logs al LEFT JOIN tenants t ON al.tenant_id = t.id WHERE al.tenant_id IS NOT NULL ORDER BY t.name")
    available_tenants = cursor.fetchall()
    
    # Get statistics
    cursor.execute("SELECT COUNT(*) as total FROM audit_logs")
    stats_total = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as total FROM audit_logs WHERE created_at >= datetime('now', '-24 hours')")
    stats_today = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as total FROM audit_logs WHERE created_at >= datetime('now', '-7 days')")
    stats_week = cursor.fetchone()['total']
    
    # Top actions
    cursor.execute("""
        SELECT action, COUNT(*) as count 
        FROM audit_logs 
        WHERE created_at >= datetime('now', '-7 days')
        GROUP BY action 
        ORDER BY count DESC 
        LIMIT 10
    """)
    top_actions = cursor.fetchall()
    
    conn.close()
    
    return render_template('superadmin/logs.html', 
                         logs=logs,
                         page=page,
                         per_page=per_page,
                         total_logs=total_logs,
                         total_pages=total_pages,
                         action_filter=action_filter,
                         tenant_id_filter=tenant_id_filter,
                         user_type_filter=user_type_filter,
                         entity_type_filter=entity_type_filter,
                         search_query=search_query,
                         available_actions=available_actions,
                         available_user_types=available_user_types,
                         available_entity_types=available_entity_types,
                         available_tenants=available_tenants,
                         stats_total=stats_total,
                         stats_today=stats_today,
                         stats_week=stats_week,
                         top_actions=top_actions)

# Translation management is now done manually via .po files
# To add new translations:
# 1. Edit translations/[lang]/LC_MESSAGES/messages.po
# 2. Run: pybabel compile -d translations
# 3. Reload the application

@superadmin.route('/superadmin/backup_database')
@superadmin_required
def backup_database():
    """Download a backup of the database."""
    from flask import send_file
    from datetime import datetime
    import shutil
    
    try:
        # Path to the database
        db_path = os.path.join(os.path.dirname(__file__), 'songs.db')
        
        if not os.path.exists(db_path):
            flash('Database file not found.', 'error')
            return redirect(url_for('superadmin.dashboard'))
        
        # Create backups directory if it doesn't exist
        backup_dir = os.path.join(os.path.dirname(__file__), 'backups')
        os.makedirs(backup_dir, exist_ok=True)
        
        # Create timestamped backup filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f'songs_backup_{timestamp}.db'
        backup_path = os.path.join(backup_dir, backup_filename)
        
        # Copy database to backup location
        shutil.copy2(db_path, backup_path)
        
        # Send the backup file for download
        return send_file(
            backup_path,
            as_attachment=True,
            download_name=backup_filename,
            mimetype='application/x-sqlite3'
        )
    except Exception as e:
        flash(f'Error creating database backup: {str(e)}', 'error')
        return redirect(url_for('superadmin.dashboard'))

@superadmin.route('/superadmin/restore_database', methods=['POST'])
@superadmin_required
def restore_database():
    """Restore database from uploaded backup file."""
    from flask import request
    from werkzeug.utils import secure_filename
    import shutil
    from datetime import datetime
    
    try:
        # Check if file was uploaded
        if 'backup_file' not in request.files:
            flash('No file uploaded.', 'error')
            return redirect(url_for('superadmin.dashboard'))
        
        file = request.files['backup_file']
        
        if file.filename == '':
            flash('No file selected.', 'error')
            return redirect(url_for('superadmin.dashboard'))
        
        # Validate file extension
        if not file.filename.endswith('.db'):
            flash('Invalid file type. Please upload a .db file.', 'error')
            return redirect(url_for('superadmin.dashboard'))
        
        # Create a backup of the current database before restoring
        db_path = os.path.join(os.path.dirname(__file__), 'songs.db')
        backup_dir = os.path.join(os.path.dirname(__file__), 'backups')
        os.makedirs(backup_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        pre_restore_backup = os.path.join(backup_dir, f'pre_restore_{timestamp}.db')
        
        if os.path.exists(db_path):
            shutil.copy2(db_path, pre_restore_backup)
        
        # Save uploaded file as the new database
        file.save(db_path)
        
        flash('Database restored successfully! A backup of the previous database was saved.', 'success')
        return redirect(url_for('superadmin.dashboard'))
        
    except Exception as e:
        flash(f'Error restoring database: {str(e)}', 'error')
        return redirect(url_for('superadmin.dashboard'))

@superadmin.route('/superadmin/create_db', methods=['POST'])
@superadmin_required
def create_db():
    """Create a new empty database (WARNING: Deletes all data)."""
    try:
        result = os.system('python3 create_db.py')
        if result == 0:
            flash('Database created successfully! All previous data has been deleted.', 'success')
        else:
            flash('Failed to create database. Check logs for details.', 'error')
    except Exception as e:
        flash(f'Error creating database: {str(e)}', 'error')
    
    return redirect(url_for('superadmin.dashboard'))

@superadmin.route('/superadmin/delete_all_songs_global', methods=['POST'])
@superadmin_required
def delete_all_songs_global():
    """Delete all songs from all tenants (WARNING: Cannot be undone)."""
    try:
        conn = create_connection()
        cursor = conn.cursor()
        
        # Delete all songs from all tenants
        cursor.execute('DELETE FROM songs')
        deleted_count = cursor.rowcount
        
        conn.commit()
        conn.close()
        
        flash(f'Successfully deleted {deleted_count} songs from all tenants.', 'success')
    except Exception as e:
        flash(f'Error deleting songs: {str(e)}', 'error')
    
    return redirect(url_for('superadmin.dashboard'))

@superadmin.route('/superadmin/tenant/<int:id>/impersonate')
@superadmin_required
def impersonate_tenant(id):
    """Impersonate a tenant - login as them without password."""
    conn = create_connection()
    cursor = conn.cursor()
    
    try:
        # Get tenant details
        cursor.execute('SELECT * FROM tenants WHERE id = ? AND active = 1', (id,))
        tenant = cursor.fetchone()
        
        if not tenant:
            flash('Tenant not found or inactive', 'error')
            return redirect(url_for('superadmin.tenants'))
        
        # Store original superadmin session info before impersonating
        session['original_superadmin_id'] = session.get('superadmin_id')
        session['is_impersonating'] = True
        session['impersonated_tenant_name'] = tenant['name']
        
        # Set tenant session as if they logged in normally
        session['is_tenant_admin'] = True
        session['tenant_id'] = tenant['id']
        session['tenant_slug'] = tenant['slug']
        session['language'] = tenant['preferred_language'] if tenant['preferred_language'] else 'en'
        
        # Remove superadmin flag during impersonation
        session.pop('is_superadmin', None)
        
        flash(f'Now impersonating {tenant["name"]}', 'info')
        return redirect(url_for('tenant_admin', tenant_slug=tenant['slug']))
        
    except Exception as e:
        flash(f'Error impersonating tenant: {str(e)}', 'error')
        return redirect(url_for('superadmin.tenants'))
    finally:
        conn.close()

@superadmin.route('/superadmin/exit_impersonation')
def exit_impersonation():
    """Exit impersonation mode and return to superadmin."""
    if not session.get('is_impersonating'):
        return redirect(url_for('superadmin.dashboard'))
    
    # Get the original superadmin ID
    superadmin_id = session.get('original_superadmin_id')
    impersonated_name = session.get('impersonated_tenant_name', 'tenant')
    
    # Clear tenant session
    session.pop('is_tenant_admin', None)
    session.pop('tenant_id', None)
    session.pop('tenant_slug', None)
    session.pop('is_impersonating', None)
    session.pop('impersonated_tenant_name', None)
    session.pop('original_superadmin_id', None)
    
    # Restore superadmin session
    session['is_superadmin'] = True
    session['superadmin_id'] = superadmin_id
    
    flash(f'Exited impersonation of {impersonated_name}', 'success')
    return redirect(url_for('superadmin.dashboard'))

@superadmin.route('/superadmin/logout')
def logout():
    session.pop('is_superadmin', None)
    session.pop('superadmin_id', None)
    return redirect(url_for('superadmin.login'))

@superadmin.route('/superadmin/bulk_spotify')
@superadmin_required
def bulk_spotify():
    """Page for superadmin to bulk fetch Spotify data for all tenants."""
    return render_template('superadmin/bulk_spotify.html')

@superadmin.route('/superadmin/bulk_spotify_status', methods=['GET'])
@superadmin_required
def bulk_spotify_status():
    """Get status of all tenants for bulk Spotify fetch."""
    import os
    
    # Get absolute path to the app directory (same method as app.py)
    app_dir = os.path.dirname(os.path.abspath(__file__))
    # Use the same base directory logic as app.py for consistency
    from app import app
    app_dir = os.path.dirname(os.path.abspath(app.root_path)) if hasattr(app, 'root_path') else app_dir
    
    conn = create_connection()
    cursor = conn.cursor()
    
    # Get all active tenants
    cursor.execute('SELECT id, name, slug FROM tenants WHERE active = 1 ORDER BY name')
    tenants = cursor.fetchall()
    
    tenant_stats = []
    for tenant in tenants:
        # Count what needs to be fetched for this tenant
        cursor.execute('''
            SELECT id, image, genre, language 
            FROM songs 
            WHERE tenant_id = ?
        ''', (tenant['id'],))
        songs = cursor.fetchall()
        
        missing_images = 0
        missing_genres = 0
        missing_languages = 0
        
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
                image_path = os.path.join(app_dir, 'static', 'tenants', tenant['slug'], 'author_images', song['image'])
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
        
        total_songs = len(songs)
        needs_processing = missing_images > 0 or missing_genres > 0 or missing_languages > 0
        
        tenant_stats.append({
            'id': tenant['id'],
            'name': tenant['name'],
            'slug': tenant['slug'],
            'total_songs': total_songs,
            'missing_images': missing_images,
            'missing_genres': missing_genres,
            'missing_languages': missing_languages,
            'needs_processing': needs_processing
        })
    
    conn.close()
    
    return jsonify({
        'success': True,
        'tenants': tenant_stats
    })

@superadmin.route('/superadmin/bulk_spotify/debug/<int:tenant_id>', methods=['GET'])
@superadmin_required
def bulk_spotify_debug(tenant_id):
    """Debug endpoint to inspect songs that need images but aren't being processed."""
    import os
    
    conn = create_connection()
    cursor = conn.cursor()
    
    # Get tenant info
    cursor.execute('SELECT * FROM tenants WHERE id = ? AND active = 1', (tenant_id,))
    tenant = cursor.fetchone()
    
    if not tenant:
        conn.close()
        return jsonify({'success': False, 'message': 'Tenant not found'}), 404
    
    tenant_slug = tenant['slug']
    app_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Get songs that supposedly need images
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
            image LIKE '%default%'
        )
        LIMIT 20
    ''', (tenant_id,))
    
    songs = cursor.fetchall()
    conn.close()
    
    # Check which ones actually need images
    debug_info = []
    for song in songs:
        image_status = "Missing (NULL or empty)" if not song['image'] else f"Has value: {song['image']}"
        
        # Check if file exists
        file_exists = False
        if song['image']:
            image_path = os.path.join(app_dir, 'static', 'tenants', tenant_slug, 'author_images', song['image'])
            file_exists = os.path.exists(image_path)
        
        debug_info.append({
            'id': song['id'],
            'title': song['title'],
            'author': song['author'],
            'image_db_value': song['image'],
            'image_status': image_status,
            'file_exists': file_exists,
            'genre': song['genre'],
            'language': song['language']
        })
    
    return jsonify({
        'success': True,
        'tenant_name': tenant['name'],
        'tenant_slug': tenant_slug,
        'debug_info': debug_info
    })

@superadmin.route('/superadmin/bulk_spotify_process', methods=['POST'])
@superadmin_required
def bulk_spotify_process():
    """Process Spotify data for a single tenant (called repeatedly)."""
    import time
    import os
    from app import get_spotify_image, download_image
    
    # Get absolute path to the app directory
    app_dir = os.path.dirname(os.path.abspath(__file__))
    
    data = request.json
    tenant_id = data.get('tenant_id')
    
    # Get batch size from system settings (can be set in superadmin settings)
    from app import get_system_setting
    from flask import request as flask_request
    import os
    
    default_batch_size = get_system_setting('spotify_batch_size', default=20, value_type=int)
    requested_batch_size = data.get('batch_size', default_batch_size)
    
    # Detect PythonAnywhere and limit batch size automatically (30-second server timeout)
    is_pythonanywhere = (
        'pythonanywhere.com' in flask_request.host or 
        os.environ.get('PYTHONANYWHERE', '').lower() == 'true' or
        os.path.exists('/home/vittorioviarengo')  # PythonAnywhere user directory
    )
    
    if is_pythonanywhere:
        # PythonAnywhere has strict 30-second timeout, use smaller batches
        default_batch_size = min(default_batch_size, 10)  # Cap at 10 for PythonAnywhere
    
    batch_size = min(requested_batch_size, default_batch_size)
    
    conn = create_connection()
    cursor = conn.cursor()
    
    # Get tenant info
    cursor.execute('SELECT * FROM tenants WHERE id = ? AND active = 1', (tenant_id,))
    tenant = cursor.fetchone()
    
    if not tenant:
        conn.close()
        return jsonify({'success': False, 'message': 'Tenant not found'}), 404
    
    tenant_slug = tenant['slug']
    
    try:
        # Get more songs than batch_size to compensate for skips (same logic as tenant bulk)
        # Many songs match the query but get skipped in the loop (e.g., file exists, Spotify returns no data)
        # Use multiplier from settings (default 3x), can be adjusted for local vs PythonAnywhere
        batch_multiplier = get_system_setting('spotify_batch_multiplier', default=3, value_type=int)
        
        # PythonAnywhere needs smaller multiplier to avoid timeout
        if is_pythonanywhere:
            batch_multiplier = min(batch_multiplier, 1.5)  # Cap at 1.5x for PythonAnywhere (10 * 1.5 = 15 songs)
        
        extended_batch = int(batch_size * batch_multiplier)
        
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
        # This helps us find songs with images in DB that don't exist physically
        if len(songs) < extended_batch:
            remaining = extended_batch - len(songs)
            song_ids = [song['id'] for song in songs] if songs else []
            
            # Get additional songs that have missing genre/language (even if they have image values)
            # We'll check if the image file exists in the loop
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
                app.logger.info(f"[Superadmin Bulk] Added {len(additional_songs)} more songs with missing genre/language")
        
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
                app.logger.info(f"[Superadmin Bulk] Added {len(more_songs)} more songs with image values (will check if files exist)")
        
        total_songs = len(songs)
        
        stats = {
            'total': total_songs,
            'images_fetched': 0,
            'genres_added': 0,
            'languages_added': 0,
            'errors': 0,
            'skipped': 0,
            'skipped_reasons': []  # Track why songs are skipped
        }
        
        app.logger.info(f"[Superadmin Bulk] Tenant {tenant_slug}: Found {total_songs} songs to process")
        
        processed_artists = {}
        
        for song in songs:
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
                
                # Check if file exists (use absolute path)
                image_file_missing = False
                if not needs_image and song['image']:
                    image_path = os.path.join(app_dir, 'static', 'tenants', tenant_slug, 'author_images', song['image'])
                    if not os.path.exists(image_path):
                        needs_image = True
                        image_file_missing = True
                        app.logger.debug(f"[Superadmin Bulk] Song {song['id']} ({song['title']}) has image '{song['image']}' in DB but file doesn't exist")
                
                needs_genre = not song['genre'] or song['genre'] == ''
                needs_language = not song['language'] or song['language'] in ['', 'unknown']
                
                if not (needs_image or needs_genre or needs_language):
                    stats['skipped'] += 1
                    reason = f"Song {song['id']} ({song['title']} by {song['author']}): Already has all data"
                    stats['skipped_reasons'].append(reason)
                    app.logger.debug(f"[Superadmin Bulk] {reason}")
                    continue
                
                # Log what we're processing
                if needs_image:
                    app.logger.debug(f"[Superadmin Bulk] Processing song {song['id']} ({song['title']}): needs_image={needs_image} (file_missing={image_file_missing}), needs_genre={needs_genre}, needs_language={needs_language}")
                
                # Get artist data
                artist_name = song['author']
                if artist_name in processed_artists:
                    artist_data = processed_artists[artist_name]
                else:
                    artist_data = get_spotify_image(artist_name)
                    processed_artists[artist_name] = artist_data
                    
                    # Check for rate limiting
                    if artist_data and artist_data.get('rate_limited'):
                        app.logger.warning(f"[Superadmin Bulk] Spotify rate limit hit for tenant {tenant_slug}, waiting 30 seconds...")
                        stats['errors'] += 1  # Count as error
                        time.sleep(30)  # Wait 30 seconds for rate limit to reset
                        # Don't cache rate_limited result, try again next time
                        del processed_artists[artist_name]
                        continue
                    
                    time.sleep(0.1)  # Standard delay between calls (increased slightly to avoid rate limits)
                
                if artist_data and not artist_data.get('rate_limited'):
                    updates = []
                    params = []
                    
                    # Update image
                    if needs_image and artist_data.get('image_url'):
                        from app import normalize_artist_filename
                        normalized_artist = normalize_artist_filename(artist_name)
                        filename = f"{normalized_artist}.jpg"
                        saved_filename = download_image(artist_data['image_url'], filename, tenant_slug)
                        if saved_filename:
                            updates.append('image = ?')
                            params.append(saved_filename)
                            stats['images_fetched'] += 1
                            app.logger.info(f"[Superadmin Bulk] Downloaded image for {artist_name}: {saved_filename}")
                        else:
                            app.logger.warning(f"[Superadmin Bulk] Failed to download image for {artist_name}")
                    elif needs_image and not artist_data.get('image_url'):
                        app.logger.debug(f"[Superadmin Bulk] Spotify returned no image for {artist_name}")
                    
                    # Update genre
                    if needs_genre and artist_data.get('genre'):
                        updates.append('genre = ?')
                        params.append(artist_data['genre'])
                        stats['genres_added'] += 1
                    
                    # Update language
                    if needs_language and artist_data.get('language'):
                        updates.append('language = ?')
                        params.append(artist_data['language'])
                        stats['languages_added'] += 1
                    
                    if updates:
                        params.append(song['id'])
                        query = f"UPDATE songs SET {', '.join(updates)} WHERE id = ?"
                        cursor.execute(query, tuple(params))
                        conn.commit()
                else:
                    # Spotify returned no data for this artist
                    app.logger.warning(f"[Superadmin Bulk] Spotify returned no data for artist: {artist_name} (song: {song['title']})")
                    stats['errors'] += 1
                    
            except Exception as e:
                app.logger.error(f"Error processing song {song['id']} for tenant {tenant_id}: {e}")
                stats['errors'] += 1
                continue
        
        conn.close()
        
        # Log final summary
        app.logger.info(f"[Superadmin Bulk] Tenant {tenant_slug} batch complete: " +
                       f"Total={stats['total']}, Images={stats['images_fetched']}, " +
                       f"Genres={stats['genres_added']}, Languages={stats['languages_added']}, " +
                       f"Skipped={stats['skipped']}, Errors={stats['errors']}")
        
        # Check if there are more songs to process - must check physical files!
        # This is important to determine if we should continue processing
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
        
        remaining = max(remaining_images, remaining_genres, remaining_languages)
        has_more = remaining > 0
        
        app.logger.info(f"[Superadmin Bulk] Remaining: {remaining_images} images, {remaining_genres} genres, {remaining_languages} languages. Has more: {has_more}")
        
        # Remove skipped_reasons from stats before sending to frontend (too verbose)
        response_stats = {k: v for k, v in stats.items() if k != 'skipped_reasons'}
        
        return jsonify({
            'success': True,
            'tenant_name': tenant['name'],
            'stats': response_stats,
            'has_more': has_more,
            'remaining': remaining,
            'remaining_images': remaining_images,
            'remaining_genres': remaining_genres,
            'remaining_languages': remaining_languages
        })
        
    except Exception as e:
        conn.close()
        app.logger.error(f"Error in superadmin bulk Spotify for tenant {tenant_id}: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

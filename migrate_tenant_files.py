import os
import sqlite3
import shutil
from flask import Flask
from utils.tenant_utils import get_tenant_dir

# Create a temporary Flask app for configuration
app = Flask(__name__)
app.config['TENANTS_BASE_DIR'] = os.path.join(os.path.dirname(__file__), 'static', 'tenants')

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

def migrate_tenant_files():
    """Migrate existing tenant files to the new directory structure."""
    print("Starting tenant files migration...")
    
    # Get all tenants from database
    conn = create_connection()
    if not conn:
        print("Error: Could not connect to database")
        return
    
    cursor = conn.cursor()
    cursor.execute('SELECT id, slug, logo_image FROM tenants')
    tenants = cursor.fetchall()
    
    # Old directories
    old_logos_dir = os.path.join(os.path.dirname(__file__), 'static', 'tenant_logos')
    
    # Track changes for updating database
    updates = []
    
    for tenant in tenants:
        tenant_id = tenant['id']
        slug = tenant['slug']
        old_logo = tenant['logo_image']
        
        if not old_logo:
            continue
            
        print(f"\nProcessing tenant: {slug}")
        
        # Create new tenant directories
        logos_dir = get_tenant_dir(app, slug, 'logos')
        images_dir = get_tenant_dir(app, slug, 'images')
        uploads_dir = get_tenant_dir(app, slug, 'uploads')
        
        # Move logo file if it exists
        if old_logo:
            old_logo_path = os.path.join(old_logos_dir, old_logo)
            if os.path.exists(old_logo_path):
                # Generate new path
                new_filename = f"logo_{os.path.splitext(old_logo)[0]}_{tenant_id}{os.path.splitext(old_logo)[1]}"
                new_rel_path = os.path.join('tenants', slug, 'logos', new_filename)
                new_abs_path = os.path.join(logos_dir, new_filename)
                
                try:
                    # Copy file to new location
                    shutil.copy2(old_logo_path, new_abs_path)
                    print(f"  Moved logo: {old_logo} -> {new_rel_path}")
                    
                    # Add to updates list
                    updates.append((new_rel_path, tenant_id))
                    
                except Exception as e:
                    print(f"  Error moving logo for tenant {slug}: {e}")
            else:
                print(f"  Warning: Logo file not found: {old_logo_path}")
    
    # Update database with new file paths
    if updates:
        try:
            cursor.executemany('UPDATE tenants SET logo_image = ? WHERE id = ?', updates)
            conn.commit()
            print("\nSuccessfully updated database with new file paths")
        except Exception as e:
            print(f"\nError updating database: {e}")
            conn.rollback()
    
    conn.close()
    
    # Clean up old directories if they're empty
    try:
        if os.path.exists(old_logos_dir) and not os.listdir(old_logos_dir):
            os.rmdir(old_logos_dir)
            print(f"\nRemoved empty directory: {old_logos_dir}")
    except Exception as e:
        print(f"\nError removing old directory: {e}")
    
    print("\nMigration completed!")

if __name__ == '__main__':
    migrate_tenant_files()

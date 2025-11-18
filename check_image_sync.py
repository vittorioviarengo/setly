#!/usr/bin/env python3
"""
Script to check image sync between database and filesystem.
Can be run directly on PythonAnywhere console or locally.

Usage:
    python check_image_sync.py [tenant_slug]

Example:
    python check_image_sync.py sergio
"""

import os
import sys
import sqlite3

def create_connection():
    """Create a database connection."""
    app_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(app_dir, 'songs.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def check_image_sync(tenant_slug):
    """Check if images in database match files in filesystem."""
    conn = create_connection()
    cursor = conn.cursor()
    
    # Get tenant
    cursor.execute('SELECT * FROM tenants WHERE slug = ? AND active = 1', (tenant_slug,))
    tenant = cursor.fetchone()
    
    if not tenant:
        print(f"❌ Tenant '{tenant_slug}' not found or inactive")
        conn.close()
        return
    
    tenant_id = tenant['id']
    tenant_name = tenant['name']
    app_dir = os.path.dirname(os.path.abspath(__file__))
    images_dir = os.path.join(app_dir, 'static', 'tenants', tenant_slug, 'author_images')
    
    print(f"\n📊 Image Sync Check for: {tenant_name} ({tenant_slug})")
    print(f"📁 Images directory: {images_dir}")
    print("=" * 60)
    
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
    
    print(f"📦 Total songs with image in DB: {stats['total_with_image_in_db']}")
    print(f"🔍 Checking files in filesystem...\n")
    
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
            # Show first 10 missing files
            if len(stats['missing_files']) <= 10:
                print(f"  ⚠️  Missing: {song['title']} - {song['author']} ({song['image']})")
    
    print("\n" + "=" * 60)
    print(f"✅ Files exist: {stats['files_exist']} (green)")
    print(f"❌ Files missing: {stats['files_missing']} (red)")
    
    if stats['total_with_image_in_db'] > 0:
        percentage = (stats['files_exist'] / stats['total_with_image_in_db']) * 100
        print(f"📈 Sync percentage: {percentage:.1f}%")
    else:
        print("📈 Sync percentage: N/A (no images in DB)")
    
    if stats['files_missing'] > 0:
        print(f"\n⚠️  Warning: {stats['files_missing']} image files are missing from filesystem")
        if len(stats['missing_files']) > 10:
            print(f"   (Showing first 10 of {stats['files_missing']} missing files)")
    else:
        print("\n✅ All images are synchronized!")
    
    print("=" * 60 + "\n")
    
    return stats

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python check_image_sync.py <tenant_slug>")
        print("\nExample:")
        print("  python check_image_sync.py sergio")
        print("  python check_image_sync.py roberto")
        sys.exit(1)
    
    tenant_slug = sys.argv[1]
    check_image_sync(tenant_slug)


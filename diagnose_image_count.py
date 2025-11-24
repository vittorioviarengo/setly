#!/usr/bin/env python3
"""
Diagnostic script to understand the image count discrepancy.
Shows exactly what the Bulk Spotify page should count.
"""

import sqlite3
import os
import sys

def diagnose_tenant(tenant_slug, app_dir=None):
    """Diagnose image counts for a tenant."""
    if app_dir is None:
        app_dir = os.path.dirname(os.path.abspath(__file__))
    
    conn = sqlite3.connect('songs.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('SELECT id, slug FROM tenants WHERE slug = ?', (tenant_slug,))
    tenant = cursor.fetchone()
    if not tenant:
        print(f"❌ Tenant {tenant_slug} non trovato")
        return
    
    tenant_id = tenant['id']
    tenant_slug = tenant['slug']
    
    print(f"\n{'='*60}")
    print(f"📊 DIAGNOSTICA PER {tenant_slug.upper()} (ID: {tenant_id})")
    print(f"{'='*60}\n")
    
    # Get all songs
    cursor.execute('SELECT id, title, author, image, genre, language FROM songs WHERE tenant_id = ?', (tenant_id,))
    songs = cursor.fetchall()
    
    print(f"📊 Totale canzoni nel database: {len(songs)}")
    
    # Count by category
    missing_images = 0
    has_images = 0
    null_empty = 0
    placeholder = 0
    http_urls = 0
    file_exists = 0
    file_missing = 0
    
    images_dir = os.path.join(app_dir, 'static', 'tenants', tenant_slug, 'author_images')
    print(f"📁 Directory immagini: {images_dir}")
    print(f"📁 Directory esiste: {os.path.exists(images_dir)}\n")
    
    if os.path.exists(images_dir):
        actual_files = set([f for f in os.listdir(images_dir) if f.endswith('.jpg')])
        print(f"📁 File .jpg sul disco: {len(actual_files)}\n")
    else:
        actual_files = set()
        print(f"⚠️  Directory non esiste!\n")
    
    for song in songs:
        image_val = song['image'] or ''
        
        # Categorize
        if not image_val or image_val == '':
            null_empty += 1
            missing_images += 1
        elif 'placeholder' in image_val.lower():
            placeholder += 1
            missing_images += 1
        elif 'setly' in image_val.lower() or 'music-icon' in image_val.lower() or 'default' in image_val.lower():
            placeholder += 1
            missing_images += 1
        elif image_val.startswith('http'):
            http_urls += 1
            missing_images += 1
        else:
            # Has a filename - check if file exists
            image_path = os.path.join(images_dir, image_val)
            if os.path.exists(image_path):
                file_exists += 1
                has_images += 1
            else:
                file_missing += 1
                missing_images += 1
    
    print(f"{'='*60}")
    print(f"📊 RISULTATI:")
    print(f"{'='*60}")
    print(f"✅ Canzoni CON immagini (file esiste): {has_images}")
    print(f"❌ Canzoni SENZA immagini: {missing_images}")
    print(f"")
    print(f"   Breakdown:")
    print(f"   - NULL/empty: {null_empty}")
    print(f"   - Placeholder/setly/music-icon: {placeholder}")
    print(f"   - HTTP URLs: {http_urls}")
    print(f"   - File mancante: {file_missing}")
    print(f"")
    print(f"📊 Totale: {len(songs)} (dovrebbe essere {has_images + missing_images})")
    print(f"{'='*60}\n")
    
    conn.close()
    
    return {
        'total': len(songs),
        'has_images': has_images,
        'missing_images': missing_images,
        'file_exists': file_exists,
        'file_missing': file_missing
    }

if __name__ == '__main__':
    tenant_slug = sys.argv[1] if len(sys.argv) > 1 else 'roberto'
    diagnose_tenant(tenant_slug)


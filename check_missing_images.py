#!/usr/bin/env python3
"""
Script to check which image files are missing from the filesystem
and compare with database values.
"""

import sqlite3
import os
import sys
from collections import defaultdict

def check_missing_images(tenant_slug=None, app_dir=None):
    """Check missing images for a tenant or all tenants."""
    if app_dir is None:
        app_dir = os.path.dirname(os.path.abspath(__file__))
    
    conn = sqlite3.connect('songs.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get tenants to check
    if tenant_slug:
        cursor.execute('SELECT id, name, slug FROM tenants WHERE slug = ? AND active = 1', (tenant_slug,))
        tenants = cursor.fetchall()
    else:
        cursor.execute('SELECT id, name, slug FROM tenants WHERE active = 1 ORDER BY name')
        tenants = cursor.fetchall()
    
    if not tenants:
        print(f"❌ Nessun tenant trovato")
        return
    
    print(f"\n{'='*80}")
    print(f"📊 VERIFICA IMMAGINI MANCANTI SUL FILESYSTEM")
    print(f"{'='*80}\n")
    
    total_missing = 0
    total_existing = 0
    
    for tenant in tenants:
        tenant_id = tenant['id']
        tenant_name = tenant['name']
        tenant_slug = tenant['slug']
        
        print(f"\n{'─'*80}")
        print(f"🎵 {tenant_name} ({tenant_slug})")
        print(f"{'─'*80}")
        
        # Get all unique image filenames for this tenant
        cursor.execute('''
            SELECT DISTINCT image, COUNT(*) as song_count
            FROM songs 
            WHERE tenant_id = ? AND image IS NOT NULL AND image != ''
            GROUP BY image
            ORDER BY song_count DESC
        ''', (tenant_id,))
        image_files = cursor.fetchall()
        
        images_dir = os.path.join(app_dir, 'static', 'tenants', tenant_slug, 'author_images')
        print(f"📁 Directory: {images_dir}")
        print(f"📁 Esiste: {os.path.exists(images_dir)}")
        
        if os.path.exists(images_dir):
            actual_files = set([f for f in os.listdir(images_dir) if f.endswith('.jpg')])
            print(f"📁 File .jpg sul disco: {len(actual_files)}\n")
        else:
            actual_files = set()
            print(f"⚠️  Directory non esiste!\n")
        
        # Check which files exist
        missing_files = []
        existing_files = []
        
        for row in image_files:
            image_filename = row['image']
            song_count = row['song_count']
            
            if image_filename in actual_files:
                existing_files.append((image_filename, song_count))
            else:
                missing_files.append((image_filename, song_count))
        
        print(f"✅ File esistenti: {len(existing_files)}")
        print(f"❌ File mancanti: {len(missing_files)}")
        
        # Count songs
        songs_with_existing = sum(count for _, count in existing_files)
        songs_with_missing = sum(count for _, count in missing_files)
        
        print(f"\n📊 Canzoni:")
        print(f"   - Con file esistente: {songs_with_existing}")
        print(f"   - Con file mancante: {songs_with_missing}")
        
        total_missing += len(missing_files)
        total_existing += len(existing_files)
        
        # Show top missing files (by song count)
        if missing_files:
            print(f"\n📋 Top 20 file mancanti (per numero di canzoni):")
            missing_sorted = sorted(missing_files, key=lambda x: x[1], reverse=True)[:20]
            for filename, count in missing_sorted:
                print(f"   - {filename}: {count} canzoni")
        
        # Show some existing files
        if existing_files:
            print(f"\n✅ Alcuni file esistenti:")
            existing_sorted = sorted(existing_files, key=lambda x: x[1], reverse=True)[:10]
            for filename, count in existing_sorted:
                print(f"   - {filename}: {count} canzoni")
    
    print(f"\n{'='*80}")
    print(f"📊 RIEPILOGO TOTALE:")
    print(f"{'='*80}")
    print(f"✅ File esistenti: {total_existing}")
    print(f"❌ File mancanti: {total_missing}")
    print(f"{'='*80}\n")
    
    conn.close()

if __name__ == '__main__':
    tenant_slug = sys.argv[1] if len(sys.argv) > 1 else None
    check_missing_images(tenant_slug)


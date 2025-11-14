#!/usr/bin/env python3
"""
Migration script to copy existing author images from shared directory to tenant-specific directories.

This script:
1. Reads all tenants from the database
2. For each tenant, finds their songs
3. Copies images from /static/author_images/ to /static/tenants/<slug>/author_images/
4. Keeps original files intact (safe migration)
"""

import sqlite3
import os
import shutil
from pathlib import Path

def create_connection():
    database_path = os.path.join(os.path.dirname(__file__), 'songs.db')
    return sqlite3.connect(database_path)

def migrate_images():
    conn = create_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get all tenants
    cursor.execute('SELECT id, slug, name FROM tenants WHERE active = 1')
    tenants = cursor.fetchall()
    
    print(f"Found {len(tenants)} active tenant(s)")
    
    source_dir = os.path.join(os.path.dirname(__file__), 'static', 'author_images')
    
    for tenant in tenants:
        tenant_id = tenant['id']
        tenant_slug = tenant['slug']
        tenant_name = tenant['name']
        
        print(f"\n{'='*60}")
        print(f"Processing: {tenant_name} (slug: {tenant_slug})")
        print(f"{'='*60}")
        
        # Create tenant's author_images directory
        target_dir = os.path.join(os.path.dirname(__file__), 'static', 'tenants', tenant_slug, 'author_images')
        os.makedirs(target_dir, exist_ok=True)
        print(f"✓ Created directory: {target_dir}")
        
        # Get all songs for this tenant with images
        cursor.execute('''
            SELECT DISTINCT image 
            FROM songs 
            WHERE tenant_id = ? AND image IS NOT NULL AND image != ''
        ''', (tenant_id,))
        
        images = cursor.fetchall()
        
        if not images:
            print(f"  No images to migrate for {tenant_name}")
            continue
        
        print(f"  Found {len(images)} unique image(s) to migrate")
        
        copied = 0
        skipped = 0
        errors = 0
        
        for img_row in images:
            image_filename = img_row['image']
            source_path = os.path.join(source_dir, image_filename)
            target_path = os.path.join(target_dir, image_filename)
            
            try:
                if os.path.exists(source_path):
                    if not os.path.exists(target_path):
                        shutil.copy2(source_path, target_path)
                        copied += 1
                        print(f"    ✓ Copied: {image_filename}")
                    else:
                        skipped += 1
                        print(f"    ⊘ Skipped (already exists): {image_filename}")
                else:
                    print(f"    ⚠ Source not found: {image_filename}")
                    errors += 1
            except Exception as e:
                print(f"    ✗ Error copying {image_filename}: {e}")
                errors += 1
        
        print(f"\n  Summary for {tenant_name}:")
        print(f"    Copied: {copied}")
        print(f"    Skipped: {skipped}")
        print(f"    Errors: {errors}")
    
    conn.close()
    
    print(f"\n{'='*60}")
    print("Migration complete!")
    print(f"{'='*60}")
    print("\n📝 Notes:")
    print("  - Original files in /static/author_images/ are preserved")
    print("  - You can safely delete them after verifying the migration")
    print("  - Test your app to ensure images are loading correctly")
    print("  - If issues occur, original files are still available")

if __name__ == '__main__':
    print("🖼️  Author Images Migration Script")
    print("="*60)
    print("This will copy images from shared directory to tenant-specific directories")
    print()
    
    response = input("Continue? (yes/no): ").strip().lower()
    if response in ['yes', 'y']:
        migrate_images()
    else:
        print("Migration cancelled.")










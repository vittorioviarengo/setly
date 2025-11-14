#!/usr/bin/env python3
"""
Script to create a super admin account for Setly
Usage: python3 create_superadmin.py
"""

import sqlite3
import getpass
from werkzeug.security import generate_password_hash

def create_superadmin():
    print("🔐 Create Super Admin for Setly")
    print("=" * 40)
    print()
    
    # Get email
    email = input("Email address: ").strip()
    if not email or '@' not in email:
        print("❌ Invalid email address")
        return
    
    # Get password
    while True:
        password = getpass.getpass("Password (min 6 chars): ")
        if len(password) < 6:
            print("❌ Password must be at least 6 characters")
            continue
        
        password_confirm = getpass.getpass("Confirm password: ")
        if password != password_confirm:
            print("❌ Passwords don't match")
            continue
        
        break
    
    # Hash password
    hashed_password = generate_password_hash(password)
    
    # Connect to database
    try:
        conn = sqlite3.connect('songs.db')
        cursor = conn.cursor()
        
        # Check if email already exists
        cursor.execute('SELECT id FROM super_admins WHERE email = ?', (email,))
        existing = cursor.fetchone()
        
        if existing:
            print(f"⚠️  Super admin with email {email} already exists")
            response = input("Update password? (y/n): ").strip().lower()
            if response != 'y':
                print("❌ Cancelled")
                conn.close()
                return
            
            # Update existing
            cursor.execute('''
                UPDATE super_admins 
                SET password_hash = ?, updated_at = CURRENT_TIMESTAMP
                WHERE email = ?
            ''', (hashed_password, email))
            print(f"✅ Updated super admin: {email}")
        else:
            # Create new
            cursor.execute('''
                INSERT INTO super_admins (email, password_hash)
                VALUES (?, ?)
            ''', (email, hashed_password))
            print(f"✅ Created super admin: {email}")
        
        conn.commit()
        conn.close()
        
        print()
        print("🎉 Success!")
        print()
        print("You can now login at:")
        print("https://vittorioviarengo.pythonanywhere.com/superadmin")
        print(f"Email: {email}")
        
    except sqlite3.Error as e:
        print(f"❌ Database error: {e}")
        return
    except Exception as e:
        print(f"❌ Error: {e}")
        return

if __name__ == '__main__':
    try:
        create_superadmin()
    except KeyboardInterrupt:
        print("\n\n❌ Cancelled by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")


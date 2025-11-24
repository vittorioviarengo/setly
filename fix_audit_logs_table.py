#!/usr/bin/env python3
"""
Script to fix audit_logs table by adding missing user_name column.
Run this on PythonAnywhere after deploying the updated audit_logger.py
"""

import sqlite3
import sys
import os

# Get database path
if len(sys.argv) > 1:
    db_path = sys.argv[1]
else:
    db_path = 'songs.db'

if not os.path.exists(db_path):
    print(f"❌ Database {db_path} non trovato")
    sys.exit(1)

print(f"📊 Aggiungo colonna user_name a {db_path}...")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Check if column exists
cursor.execute("PRAGMA table_info(audit_logs)")
columns = [row[1] for row in cursor.fetchall()]

if 'user_name' in columns:
    print("✅ Colonna user_name già esiste")
else:
    try:
        cursor.execute('ALTER TABLE audit_logs ADD COLUMN user_name TEXT')
        conn.commit()
        print("✅ Colonna user_name aggiunta con successo")
    except sqlite3.OperationalError as e:
        print(f"❌ Errore: {e}")
        conn.rollback()

# Verify
cursor.execute("PRAGMA table_info(audit_logs)")
columns = [row[1] for row in cursor.fetchall()]
print(f"\n📋 Colonne in audit_logs: {', '.join(columns)}")

conn.close()
print("\n✅ Migrazione completata!")


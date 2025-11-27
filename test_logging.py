#!/usr/bin/env python3
"""Test script to verify audit logging is working"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(__file__))

try:
    from utils.audit_logger import log_user_action, log_event
    print("✅ audit_logger importato con successo")
    
    # Test logging
    print("\n📝 Test logging di un evento...")
    log_user_action(
        action='test_action',
        entity_type='test',
        entity_id=999,
        test_data='This is a test log entry'
    )
    
    print("✅ Log inviato alla coda")
    print("\n⏳ Attendo 3 secondi per permettere al worker di processare...")
    import time
    time.sleep(3)
    
    # Check if log was written
    import sqlite3
    db_path = 'songs.db'
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM audit_logs WHERE action = 'test_action'")
        count = cursor.fetchone()[0]
        conn.close()
        
        if count > 0:
            print(f"✅ Log scritto nel database! ({count} log trovati)")
        else:
            print("❌ Log NON trovato nel database. Il worker thread potrebbe non essere attivo.")
    else:
        print("❌ Database non trovato")
        
except ImportError as e:
    print(f"❌ Errore import: {e}")
    print("Il modulo audit_logger non è disponibile")
except Exception as e:
    print(f"❌ Errore: {e}")
    import traceback
    traceback.print_exc()


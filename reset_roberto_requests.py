#!/usr/bin/env python3
"""
Script per resettare i contatori richieste per ROB (tenant_id 15)
Solo se sono richieste di prova/test
"""
import sqlite3
import sys

def create_connection(db_file='songs.db'):
    """Create a database connection."""
    try:
        conn = sqlite3.connect(db_file)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        print(f"Error connecting to database: {e}")
        return None

def reset_roberto_requests():
    """Reset request counters for ROB tenant."""
    conn = create_connection()
    if not conn:
        return False
    
    cursor = conn.cursor()
    tenant_id = 15  # ROB
    
    print("=" * 60)
    print("RESET CONTATORI RICHIESTE PER ROB")
    print("=" * 60)
    print()
    
    # Verifica situazione attuale
    cursor.execute('SELECT COUNT(*) as count FROM requests WHERE tenant_id = ?', (tenant_id,))
    requests_count = cursor.fetchone()['count']
    
    cursor.execute('''
        SELECT 
            COUNT(*) as songs_with_requests,
            SUM(requests) as total_requests
        FROM songs
        WHERE tenant_id = ? AND requests > 0
    ''', (tenant_id,))
    song_stats = cursor.fetchone()
    
    print(f"📊 Situazione attuale:")
    print(f"   Richieste in tabella requests: {requests_count}")
    print(f"   Canzoni con richieste: {song_stats['songs_with_requests']}")
    print(f"   Totale richieste (da songs.requests): {song_stats['total_requests']}")
    print()
    
    if song_stats['total_requests'] == 0:
        print("✅ Nessun contatore da resettare")
        conn.close()
        return True
    
    # Chiedi conferma
    print("⚠️  ATTENZIONE: Questo resetterà tutti i contatori richieste per ROB")
    print(f"   Verranno resettati {song_stats['total_requests']} contatori su {song_stats['songs_with_requests']} canzoni")
    print()
    response = input("Vuoi procedere? (scrivi 'SI' per confermare): ").strip()
    
    if response != 'SI':
        print("❌ Operazione annullata")
        conn.close()
        return False
    
    # Reset contatori
    print()
    print("🔄 Reset contatori...")
    cursor.execute('''
        UPDATE songs
        SET requests = 0
        WHERE tenant_id = ? AND requests > 0
    ''', (tenant_id,))
    updated = cursor.rowcount
    conn.commit()
    
    print(f"✅ {updated} canzoni aggiornate - contatori resettati a 0")
    print()
    
    # Verifica
    cursor.execute('SELECT SUM(requests) as total FROM songs WHERE tenant_id = ?', (tenant_id,))
    new_total = cursor.fetchone()['total']
    print(f"📊 Verifica: Totale richieste dopo reset: {new_total or 0}")
    
    conn.close()
    print()
    print("=" * 60)
    print("✅ Reset completato!")
    print("=" * 60)
    
    return True

if __name__ == '__main__':
    reset_roberto_requests()


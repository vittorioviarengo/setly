#!/usr/bin/env python3
"""
Script per verificare lo stato delle richieste nel database
"""
import sqlite3
from datetime import datetime

def create_connection(db_file='songs.db'):
    """Create a database connection."""
    try:
        conn = sqlite3.connect(db_file)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        print(f"Error connecting to database: {e}")
        return None

def check_requests():
    conn = create_connection()
    if not conn:
        return
    
    cursor = conn.cursor()
    
    print("=" * 60)
    print("ANALISI RICHIESTE NEL DATABASE")
    print("=" * 60)
    print()
    
    # 1. Totale richieste
    cursor.execute('SELECT COUNT(*) as total FROM requests')
    total = cursor.fetchone()['total']
    print(f"📊 Totale richieste nel database: {total}")
    print()
    
    # 2. Richieste per status
    try:
        cursor.execute('''
            SELECT status, COUNT(*) as count 
            FROM requests 
            GROUP BY status
        ''')
        status_counts = cursor.fetchall()
        if status_counts:
            print("📋 Richieste per status:")
            for row in status_counts:
                status = row['status'] or 'NULL'
                count = row['count']
                print(f"   - {status}: {count}")
        else:
            print("   Nessuna richiesta trovata")
        print()
    except sqlite3.OperationalError as e:
        print(f"   ⚠️  Errore nel controllo status (colonna potrebbe non esistere): {e}")
        print()
    
    # 3. Richieste per tenant
    try:
        cursor.execute('''
            SELECT 
                t.name as tenant_name,
                t.id as tenant_id,
                COUNT(r.id) as request_count
            FROM tenants t
            LEFT JOIN requests r ON r.tenant_id = t.id
            GROUP BY t.id, t.name
            ORDER BY request_count DESC
        ''')
        tenant_requests = cursor.fetchall()
        if tenant_requests:
            print("🏢 Richieste per tenant:")
            for row in tenant_requests:
                tenant_name = row['tenant_name']
                tenant_id = row['tenant_id']
                count = row['request_count']
                print(f"   - {tenant_name} (ID: {tenant_id}): {count} richieste")
        print()
    except sqlite3.OperationalError as e:
        print(f"   ⚠️  Errore nel controllo tenant: {e}")
        print()
    
    # 4. Richieste senza tenant_id (vecchie richieste)
    try:
        cursor.execute('SELECT COUNT(*) as count FROM requests WHERE tenant_id IS NULL')
        no_tenant = cursor.fetchone()['count']
        if no_tenant > 0:
            print(f"⚠️  Richieste senza tenant_id (vecchie): {no_tenant}")
        print()
    except sqlite3.OperationalError:
        pass
    
    # 5. Ultime 20 richieste
    try:
        cursor.execute('''
            SELECT 
                r.id,
                r.requester,
                r.request_time,
                r.status,
                s.title,
                s.author,
                t.name as tenant_name
            FROM requests r
            LEFT JOIN songs s ON s.id = r.song_id
            LEFT JOIN tenants t ON t.id = r.tenant_id
            ORDER BY r.request_time DESC
            LIMIT 20
        ''')
        recent = cursor.fetchall()
        if recent:
            print("🕐 Ultime 20 richieste:")
            for row in recent:
                req_id = row['id']
                requester = row['requester']
                request_time = row['request_time']
                status = row['status'] or 'NULL'
                title = row['title'] or 'N/A'
                author = row['author'] or 'N/A'
                tenant = row['tenant_name'] or 'N/A'
                print(f"   [{req_id}] {requester} → {title} by {author} ({tenant}) - {request_time} [status: {status}]")
        print()
    except sqlite3.OperationalError as e:
        print(f"   ⚠️  Errore nel recupero richieste recenti: {e}")
        print()
    
    # 6. Richieste per data (ultimi 7 giorni)
    try:
        cursor.execute('''
            SELECT 
                DATE(request_time) as date,
                COUNT(*) as count
            FROM requests
            WHERE request_time >= datetime('now', '-7 days')
            GROUP BY DATE(request_time)
            ORDER BY date DESC
        ''')
        daily = cursor.fetchall()
        if daily:
            print("📅 Richieste per giorno (ultimi 7 giorni):")
            for row in daily:
                date = row['date']
                count = row['count']
                print(f"   - {date}: {count} richieste")
        print()
    except sqlite3.OperationalError as e:
        print(f"   ⚠️  Errore nel controllo per data: {e}")
        print()
    
    conn.close()
    print("=" * 60)

if __name__ == '__main__':
    check_requests()


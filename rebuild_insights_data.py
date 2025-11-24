#!/usr/bin/env python3
"""
Script per ricostruire i dati delle statistiche insights
da altre tabelle o dati esistenti
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

def rebuild_insights_data(tenant_slug=None, tenant_id=None):
    """Rebuild insights data for a tenant."""
    conn = create_connection()
    if not conn:
        return False
    
    cursor = conn.cursor()
    
    print("=" * 60)
    print("RICOSTRUZIONE DATI INSIGHTS")
    print("=" * 60)
    print()
    
    # Find tenant
    if tenant_slug:
        cursor.execute('SELECT id, name FROM tenants WHERE slug = ?', (tenant_slug,))
        tenant = cursor.fetchone()
        if tenant:
            tenant_id = tenant['id']
            tenant_name = tenant['name']
        else:
            print(f"❌ Tenant '{tenant_slug}' non trovato")
            conn.close()
            return False
    elif tenant_id:
        cursor.execute('SELECT id, name, slug FROM tenants WHERE id = ?', (tenant_id,))
        tenant = cursor.fetchone()
        if tenant:
            tenant_name = tenant['name']
            tenant_slug = tenant['slug']
        else:
            print(f"❌ Tenant ID {tenant_id} non trovato")
            conn.close()
            return False
    else:
        print("❌ Specifica tenant_slug o tenant_id")
        conn.close()
        return False
    
    print(f"📊 Analisi per: {tenant_name} (ID: {tenant_id}, slug: {tenant_slug})")
    print()
    
    # Check if status column exists
    cursor.execute("PRAGMA table_info(requests)")
    columns = [row[1] for row in cursor.fetchall()]
    has_status = 'status' in columns
    
    if not has_status:
        print("⚠️  Colonna 'status' non esiste - esegui prima la migrazione!")
        conn.close()
        return False
    
    # Count all requests for this tenant
    cursor.execute('SELECT COUNT(*) as total FROM requests WHERE tenant_id = ?', (tenant_id,))
    total = cursor.fetchone()['total']
    print(f"📊 Totale richieste per {tenant_name}: {total}")
    
    # Count by status
    cursor.execute('''
        SELECT 
            COALESCE(status, 'NULL') as status,
            COUNT(*) as count
        FROM requests
        WHERE tenant_id = ?
        GROUP BY status
    ''', (tenant_id,))
    status_counts = cursor.fetchall()
    
    print()
    print("📋 Richieste per status:")
    pending = 0
    fulfilled = 0
    cancelled = 0
    null_status = 0
    
    for row in status_counts:
        status = row['status']
        count = row['count']
        print(f"   - {status}: {count}")
        if status == 'pending':
            pending = count
        elif status == 'fulfilled':
            fulfilled = count
        elif status == 'cancelled':
            cancelled = count
        elif status == 'NULL':
            null_status = count
    
    print()
    
    # Check if we can infer status from other data
    if null_status > 0:
        print(f"⚠️  {null_status} richieste hanno status NULL")
        print("   Possiamo inferire lo status da altri dati?")
        print()
        
        # Check if there's a played_at timestamp
        cursor.execute('''
            SELECT COUNT(*) as count
            FROM requests
            WHERE tenant_id = ? AND status IS NULL AND played_at IS NOT NULL
        ''', (tenant_id,))
        with_played_at = cursor.fetchone()['count']
        
        if with_played_at > 0:
            print(f"   ✅ {with_played_at} richieste hanno played_at - possono essere marcate come 'fulfilled'")
            print()
            print("   Vuoi aggiornare queste richieste? (y/n): ", end='')
            response = input().strip().lower()
            if response == 'y':
                cursor.execute('''
                    UPDATE requests
                    SET status = 'fulfilled'
                    WHERE tenant_id = ? AND status IS NULL AND played_at IS NOT NULL
                ''', (tenant_id,))
                conn.commit()
                print(f"   ✅ {cursor.rowcount} richieste aggiornate a 'fulfilled'")
                fulfilled += cursor.rowcount
                null_status -= cursor.rowcount
    
    # Check songs table for request counts
    print()
    print("🎵 Verifica conteggi richieste nella tabella songs:")
    cursor.execute('''
        SELECT 
            COUNT(*) as songs_with_requests,
            SUM(requests) as total_song_requests
        FROM songs
        WHERE tenant_id = ? AND requests > 0
    ''', (tenant_id,))
    song_stats = cursor.fetchone()
    print(f"   Canzoni con richieste: {song_stats['songs_with_requests']}")
    print(f"   Totale richieste (da songs.requests): {song_stats['total_song_requests']}")
    print()
    
    # Summary
    print("=" * 60)
    print("RIEPILOGO STATISTICHE")
    print("=" * 60)
    print(f"Total Requests: {total}")
    print(f"Pending: {pending + null_status}")
    print(f"Fulfilled: {fulfilled}")
    print(f"Cancelled: {cancelled}")
    if total > 0:
        conversion_rate = (fulfilled / total * 100)
        print(f"Conversion Rate: {conversion_rate:.1f}%")
    print()
    
    # Most requested songs
    print("🎵 Canzoni più richieste:")
    cursor.execute('''
        SELECT 
            s.title,
            s.author,
            COUNT(r.id) as request_count
        FROM requests r
        JOIN songs s ON r.song_id = s.id
        WHERE r.tenant_id = ?
        GROUP BY s.id
        ORDER BY request_count DESC
        LIMIT 10
    ''', (tenant_id,))
    top_songs = cursor.fetchall()
    
    if top_songs:
        for i, song in enumerate(top_songs, 1):
            print(f"   {i}. {song['title']} by {song['author']} - {song['request_count']} richieste")
    else:
        print("   Nessuna richiesta trovata")
    
    conn.close()
    print()
    print("=" * 60)
    
    return True

if __name__ == '__main__':
    if len(sys.argv) > 1:
        tenant_arg = sys.argv[1]
        if tenant_arg.isdigit():
            rebuild_insights_data(tenant_id=int(tenant_arg))
        else:
            rebuild_insights_data(tenant_slug=tenant_arg)
    else:
        print("Usage: python3 rebuild_insights_data.py <tenant_slug|tenant_id>")
        print("Example: python3 rebuild_insights_data.py roberto")
        print("Example: python3 rebuild_insights_data.py 15")


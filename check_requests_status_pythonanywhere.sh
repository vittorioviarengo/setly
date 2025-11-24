#!/bin/bash
# Script da eseguire su PythonAnywhere per verificare lo stato delle richieste

cd ~/setly
workon setly-env  # o source venv/bin/activate

python3 << 'EOF'
import sqlite3

conn = sqlite3.connect('songs.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("=" * 60)
print("VERIFICA STATO RICHIESTE SU PYTHONANYWHERE")
print("=" * 60)
print()

# Verifica se colonna status esiste
try:
    cursor.execute("PRAGMA table_info(requests)")
    columns = [col[1] for col in cursor.fetchall()]
    has_status = 'status' in columns
    print(f"✅ Colonna 'status' esiste: {has_status}")
    print()
except Exception as e:
    print(f"❌ Errore: {e}")
    conn.close()
    exit(1)

if has_status:
    # Conta per status
    cursor.execute('''
        SELECT 
            COALESCE(status, 'NULL') as status,
            COUNT(*) as count
        FROM requests
        GROUP BY status
        ORDER BY count DESC
    ''')
    status_counts = cursor.fetchall()
    
    print("📊 Richieste per status:")
    for row in status_counts:
        print(f"   - {row['status']}: {row['count']}")
    print()
    
    # Totali
    cursor.execute("SELECT COUNT(*) as total FROM requests")
    total = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as pending FROM requests WHERE status = 'pending'")
    pending = cursor.fetchone()['pending']
    
    cursor.execute("SELECT COUNT(*) as fulfilled FROM requests WHERE status = 'fulfilled'")
    fulfilled = cursor.fetchone()['fulfilled']
    
    cursor.execute("SELECT COUNT(*) as cancelled FROM requests WHERE status = 'cancelled'")
    cancelled = cursor.fetchone()['cancelled']
    
    cursor.execute("SELECT COUNT(*) as null_status FROM requests WHERE status IS NULL")
    null_status = cursor.fetchone()['null_status']
    
    print("📈 Riepilogo:")
    print(f"   Total All-Time: {total}")
    print(f"   Currently Open (pending): {pending}")
    print(f"   Fulfilled (played): {fulfilled}")
    print(f"   Cancelled: {cancelled}")
    print(f"   NULL status (vecchie): {null_status}")
    print()
    
    if total == pending:
        print("⚠️  Tutte le richieste sono pending - questo è normale se:")
        print("   1. Nessuna richiesta è stata ancora marcata come 'played'")
        print("   2. Le richieste cancellate sono state eliminate (vecchio codice)")
        print()
        print("💡 Dopo il deploy del nuovo codice, le richieste cancellate")
        print("   verranno marcate come 'cancelled' invece di essere eliminate.")
else:
    print("⚠️  La colonna 'status' non esiste ancora!")
    print("   Esegui la migrazione: python3 migrate_requests_table.py songs.db")

conn.close()
print("=" * 60)
EOF


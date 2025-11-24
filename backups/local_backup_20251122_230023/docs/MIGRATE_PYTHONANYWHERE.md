# 🔧 Migrazione Database su PythonAnywhere

## Problema
Il database su PythonAnywhere non ha le colonne necessarie (`status`, `session_id`, `tip_amount`, `played_at`) nella tabella `requests`, causando errori 500 quando si cerca di caricare la coda.

## Soluzione

### Step 1: Carica lo script di migrazione

1. Vai su PythonAnywhere → **Files** tab
2. Naviga in `~/setly/`
3. Carica il file `migrate_requests_table.py` (dalla directory locale)

### Step 2: Esegui la migrazione

Dalla **Bash console** su PythonAnywhere:

```bash
cd ~/setly
workon setly-env  # o source venv/bin/activate
python3 migrate_requests_table.py songs.db
```

Lo script:
- ✅ Verifica quali colonne mancano
- ✅ Aggiunge le colonne mancanti (`status`, `session_id`, `tip_amount`, `played_at`)
- ✅ Crea gli indici necessari per le performance
- ✅ Aggiorna le richieste esistenti con status 'pending'

### Step 3: Verifica

Dopo la migrazione, verifica che tutto funzioni:

```bash
python3 << 'EOF'
import sqlite3
conn = sqlite3.connect('songs.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Verifica struttura
cursor.execute("PRAGMA table_info(requests)")
columns = cursor.fetchall()
print("Colonne nella tabella requests:")
for col in columns:
    print(f"  - {col[1]} ({col[2]})")

# Conta richieste per ROB
cursor.execute("SELECT COUNT(*) as count FROM requests WHERE tenant_id = 15")
count = cursor.fetchone()['count']
print(f"\nRichieste per ROB (tenant_id 15): {count}")

conn.close()
EOF
```

### Step 4: Reload Web App

1. Vai al tab **Web** su PythonAnywhere
2. Clicca il bottone verde **"Reload vittorioviarengo.pythonanywhere.com"**

### Step 5: Test

1. Vai su `https://vittorioviarengo.pythonanywhere.com/vittorio/queue`
2. Verifica che la coda si carichi senza errori 500
3. Controlla che le richieste vengano visualizzate correttamente

---

## Note

- ✅ La migrazione è **sicura** - non elimina dati esistenti
- ✅ Le richieste esistenti verranno marcate con status 'pending'
- ✅ Gli indici miglioreranno le performance delle query
- ⚠️  Fai un backup del database prima della migrazione (già fatto se hai scaricato il DB)

---

## Troubleshooting

**Errore: "database is locked"**
- Chiudi tutte le connessioni al database
- Rilancia la web app dopo la migrazione

**Errore: "no such column" dopo la migrazione**
- Verifica che la migrazione sia stata completata con successo
- Controlla i log per eventuali errori

**Le richieste non appaiono**
- Verifica che le richieste abbiano `status = 'pending'`
- Controlla che `tenant_id` sia corretto


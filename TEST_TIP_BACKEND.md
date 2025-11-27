# Guida per Testare il Backend delle Mance

## 1. Verifica Database

Le tabelle vengono create automaticamente all'avvio dell'app. Verifica che esistano:

```bash
# Verifica tabella tip_intents
sqlite3 songs.db ".schema tip_intents"

# Verifica colonna tip_enabled in gigs (verrà aggiunta al prossimo avvio)
sqlite3 songs.db "PRAGMA table_info(gigs);" | grep tip_enabled
```

## 2. Avvia l'Applicazione

```bash
python app.py
```

L'app sarà disponibile su `http://localhost:5001`

## 3. Test Manuali con Browser DevTools

### Test 1: Verifica che le tabelle siano create
Dopo aver avviato l'app, controlla i log. Dovresti vedere:
- "Added tip_enabled column to gigs table" (se la colonna non esisteva)
- "Successfully created 'tip_intents' table and indexes"

### Test 2: Avvia un Gig con Tips Abilitati
1. Fai login come tenant admin
2. Vai alla pagina queue
3. Avvia un gig (dovresti vedere un checkbox per abilitare/disabilitare tips)
4. Verifica nel database:
```bash
sqlite3 songs.db "SELECT id, name, tip_enabled, is_active FROM gigs WHERE is_active = 1;"
```

### Test 3: Richiedi una Canzone con Mancia
1. Apri la console del browser (F12)
2. Fai una richiesta di canzone con mancia:
```javascript
fetch('/request_song/1', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
        user: 'TestUser',
        tip_amount: 5.0  // 5 euro
    })
})
.then(r => r.json())
.then(data => console.log('Response:', data));
```

3. Verifica nel database:
```bash
sqlite3 songs.db "SELECT * FROM tip_intents ORDER BY id DESC LIMIT 1;"
sqlite3 songs.db "SELECT id, song_id, requester, tip_amount FROM requests ORDER BY id DESC LIMIT 1;"
```

### Test 4: Richiedi una Canzone senza Mancia
```javascript
fetch('/request_song/1', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
        user: 'TestUser'
        // Nessun tip_amount
    })
})
.then(r => r.json())
.then(data => console.log('Response:', data));
```

Dovresti vedere `success: true` ma **nessun** `tip_intent` nella risposta.

### Test 5: Crea una Mancia Standalone
```javascript
fetch('/api/create_tip', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
        tip_amount: 10.0  // 10 euro
    })
})
.then(r => r.json())
.then(data => console.log('Response:', data));
```

### Test 6: Aggiorna tip_enabled per Gig Attivo
```javascript
fetch('/roberto/update_tip_enabled', {  // Sostituisci 'roberto' con il tuo tenant_slug
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
        tip_enabled: false
    })
})
.then(r => r.json())
.then(data => console.log('Response:', data));
```

Poi prova a richiedere una canzone con mancia - dovrebbe fallire con errore "Tips are not enabled for this event".

## 4. Test con Script Python

Esegui lo script di test:

```bash
python test_tip_backend.py
```

Lo script mostrerà gli endpoint disponibili e le istruzioni per testarli.

## 5. Verifica Errori Comuni

### Errore: "Tips are not enabled for this event"
- Verifica che il gig attivo abbia `tip_enabled = 1`
- Controlla: `sqlite3 songs.db "SELECT tip_enabled FROM gigs WHERE is_active = 1;"`

### Errore: "Tip intent not found"
- Verifica che il `tip_intent_id` esista
- Controlla: `sqlite3 songs.db "SELECT * FROM tip_intents WHERE id = X;"`

### Errore: "PayPal not configured"
- Per test completi PayPal, configura le variabili d'ambiente:
```bash
export PAYPAL_CLIENT_ID="your_sandbox_client_id"
export PAYPAL_CLIENT_SECRET="your_sandbox_client_secret"
export PAYPAL_MODE="sandbox"
```

## 6. Query Utili per Debug

```sql
-- Vedi tutti i tip_intents
SELECT * FROM tip_intents ORDER BY created_at DESC;

-- Vedi richieste con mance
SELECT r.id, r.requester, r.tip_amount, t.amount, t.status 
FROM requests r 
LEFT JOIN tip_intents t ON r.id = t.request_id 
WHERE r.tip_amount > 0 
ORDER BY r.id DESC;

-- Vedi gig attivo con tip_enabled
SELECT id, name, tip_enabled, is_active, start_time 
FROM gigs 
WHERE is_active = 1;

-- Conta tip_intents per stato
SELECT status, COUNT(*) as count 
FROM tip_intents 
GROUP BY status;
```

## 7. Checklist Test Completo

- [ ] Tabella `tip_intents` creata
- [ ] Colonna `tip_enabled` aggiunta a `gigs`
- [ ] Avviare gig con `tip_enabled = true` funziona
- [ ] Avviare gig con `tip_enabled = false` funziona
- [ ] Richiesta canzone senza mancia funziona (nessun tip_intent creato)
- [ ] Richiesta canzone con mancia funziona (tip_intent creato con status 'pending')
- [ ] Richiesta canzone con mancia fallisce se `tip_enabled = false`
- [ ] Endpoint `/api/create_tip` crea tip_intent standalone
- [ ] Endpoint `/api/create_paypal_order` restituisce order_id (mock per ora)
- [ ] Endpoint `/api/confirm_paypal_payment` aggiorna status a 'completed'

## Note

- Gli endpoint PayPal attualmente restituiscono mock data (order_id fittizio)
- Per test completi PayPal, devi integrare l'SDK PayPal reale
- Tutti gli endpoint richiedono una sessione valida (tranne alcuni GET pubblici)


# Future Features - Bassa Priorità

## Tabella Gigs/Eventi

### Descrizione
Creare un sistema per gestire eventi/spettacoli dove il cantante può:
- Creare un nuovo evento/gig
- Associare le richieste a un evento specifico
- Visualizzare statistiche per evento (richieste totali, canzoni suonate, etc.)
- Analisi storiche per confrontare performance tra eventi

### Utilità
- Permette al cantante di vedere quante richieste erano state fatte in un evento specifico
- Confrontare performance tra diversi eventi
- Tracciare l'evoluzione nel tempo
- Analisi più dettagliate per evento

### Implementazione Suggerita

#### Database Schema
```sql
CREATE TABLE gigs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    venue_name TEXT,
    gig_date DATE,
    start_time TIME,
    end_time TIME,
    status TEXT DEFAULT 'upcoming', -- 'upcoming', 'active', 'completed', 'cancelled'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(tenant_id) REFERENCES tenants(id)
);

-- Aggiungere gig_id alla tabella requests
ALTER TABLE requests ADD COLUMN gig_id INTEGER;
CREATE INDEX idx_requests_gig ON requests(gig_id);
```

#### Features
1. **Creazione Gig**: Form per creare nuovo evento con nome, data, luogo
2. **Associazione Richieste**: Quando un gig è "active", le nuove richieste vengono associate automaticamente
3. **Dashboard Gig**: Statistiche per singolo evento
4. **Storico**: Lista di tutti gli eventi passati con statistiche

### Note
- Bassa priorità - valutare utilità prima di implementare
- Potrebbe essere utile per artisti che fanno molti eventi
- Richiede UI per gestione gigs nella sezione admin


# Migrazione Tabella Gigs su PythonAnywhere

## Problema
La gestione dei gigs non funziona su PythonAnywhere perché la tabella `gigs` non esiste nel database.

## Soluzione
La tabella `gigs` viene ora creata automaticamente all'avvio dell'app. Tuttavia, se la tabella non esiste ancora, puoi eseguire manualmente lo script di migrazione.

## Opzione 1: Automatica (Consigliata)
La tabella viene creata automaticamente quando l'app si avvia. Basta:
1. Fare `git pull` su PythonAnywhere
2. Ricaricare la webapp

La funzione `ensure_gigs_table()` viene chiamata all'avvio e crea la tabella se non esiste.

## Opzione 2: Manuale (se necessario)
Se per qualche motivo la creazione automatica non funziona, puoi eseguire manualmente lo script di migrazione:

```bash
cd ~/setly
python3 migrate_gigs_table.py songs.db
```

Questo script:
- Crea la tabella `gigs` se non esiste
- Aggiunge la colonna `gig_id` alla tabella `requests` se non esiste
- Crea gli indici necessari per le performance

## Verifica
Dopo il deploy, verifica che la tabella esista:

```bash
cd ~/setly
sqlite3 songs.db ".tables" | grep gigs
```

Dovresti vedere `gigs` nell'output.

## Note
- La tabella viene creata automaticamente all'avvio dell'app
- Non è necessario eseguire manualmente la migrazione se usi la versione più recente del codice
- Le modifiche sono state committate su Git e sono disponibili con `git pull`


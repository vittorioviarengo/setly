#!/bin/bash
# Script per aggiornare l'app su PythonAnywhere
# Usa questo script dalla Bash console di PythonAnywhere

echo "🚀 Aggiornamento Songs 2.0 su PythonAnywhere"
echo "=========================================="

# Step 1: Backup database
echo ""
echo "📦 Step 1: Creo backup del database..."
cd ~/setly
mkdir -p backups
cp songs.db backups/songs_backup_$(date +%Y%m%d_%H%M%S).db
echo "✅ Backup creato in backups/"

# Step 2: Aggiorna codice (se usi git)
echo ""
echo "📥 Step 2: Aggiorno il codice..."
if [ -d .git ]; then
    git pull origin main
    echo "✅ Codice aggiornato via git"
else
    echo "⚠️  Directory non è un repo git - carica i file manualmente via Files tab"
fi

# Step 3: Attiva virtualenv e ricompila traduzioni
echo ""
echo "🌐 Step 3: Ricompilo le traduzioni..."
if [ -d ~/.virtualenvs/setly-env ]; then
    source ~/.virtualenvs/setly-env/bin/activate
elif [ -d venv ]; then
    source venv/bin/activate
else
    echo "⚠️  Virtualenv non trovato - usa: workon setly-env"
fi

pybabel compile -d translations
echo "✅ Traduzioni ricompilate"

# Step 4: Installa eventuali nuove dipendenze
echo ""
echo "📦 Step 4: Controllo dipendenze..."
pip install -r requirements.txt --quiet
echo "✅ Dipendenze aggiornate"

echo ""
echo "✅ Aggiornamento completato!"
echo ""
echo "📋 Prossimi passi:"
echo "1. Vai al tab 'Web' su PythonAnywhere"
echo "2. Clicca 'Reload vittorioviarengo.pythonanywhere.com'"
echo "3. Testa l'applicazione"
echo ""
echo "💾 Backup salvato in: ~/setly/backups/"


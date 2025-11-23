#!/bin/bash
# Script semplice per deployare su PythonAnywhere
# Esegui questo dalla Bash console su PythonAnywhere

echo "🚀 Deploy su PythonAnywhere"
echo "=========================="
echo ""

cd ~/setly

# Step 1: Git pull
echo "📥 Step 1: Aggiorno codice da Git..."
echo "   Controllo stato git..."
git fetch origin main
LOCAL=$(git rev-parse @)
REMOTE=$(git rev-parse @{u})
if [ "$LOCAL" = "$REMOTE" ]; then
    echo "   ⚠️  Il codice locale è già aggiornato (nessuna modifica su remote)"
    echo "   💡 Assicurati di aver fatto git push dal tuo computer locale!"
else
    echo "   📥 Trovate modifiche su remote, aggiorno..."
    git pull origin main
    if [ $? -eq 0 ]; then
        echo "✅ Codice aggiornato"
    else
        echo "❌ Errore nel git pull"
        exit 1
    fi
fi
echo ""

# Step 2: Attiva virtualenv
echo "🐍 Step 2: Attivo virtualenv..."
if [ -d ~/.virtualenvs/setly-env ]; then
    source ~/.virtualenvs/setly-env/bin/activate
elif [ -d venv ]; then
    source venv/bin/activate
else
    echo "⚠️  Virtualenv non trovato - usa: workon setly-env"
    exit 1
fi
echo "✅ Virtualenv attivato"
echo ""

# Step 3: Ricompila traduzioni
echo "🌐 Step 3: Ricompilo traduzioni..."
pybabel compile -d translations
if [ $? -eq 0 ]; then
    echo "✅ Traduzioni ricompilate"
else
    echo "❌ Errore nella ricompilazione traduzioni"
    exit 1
fi
echo ""

# Step 4: Installa dipendenze (se necessario)
echo "📦 Step 4: Verifico dipendenze..."
pip install -r requirements.txt --quiet
echo "✅ Dipendenze verificate"
echo ""

# Step 5: Reload webapp
echo "🔄 Step 5: Ricarico la webapp..."
# Metodo 1: Usa API se disponibile
if [ -n "$PYTHONANYWHERE_API_TOKEN" ]; then
    echo "   Tentativo reload via API..."
    curl -X POST \
        -H "Authorization: Token $PYTHONANYWHERE_API_TOKEN" \
        https://www.pythonanywhere.com/api/v0/user/vittorioviarengo/webapps/vittorioviarengo.pythonanywhere.com/reload/ \
        -s -o /dev/null -w "HTTP Status: %{http_code}\n"
    if [ $? -eq 0 ]; then
        echo "✅ Webapp ricaricata via API"
    else
        echo "⚠️  Errore nel reload via API"
    fi
fi

# Metodo 2: Touch sul file WSGI (forza reload)
if [ -f /var/www/vittorioviarengo_pythonanywhere_com_wsgi.py ]; then
    # Touch due volte per essere sicuri che il timestamp cambi
    touch /var/www/vittorioviarengo_pythonanywhere_com_wsgi.py
    sleep 1
    touch /var/www/vittorioviarengo_pythonanywhere_com_wsgi.py
    echo "✅ Webapp ricaricata (touch su WSGI file)"
    echo "   ⚠️  IMPORTANTE: Se il problema persiste, vai su PythonAnywhere > Web tab > Reload"
else
    echo "⚠️  File WSGI non trovato. Ricarica manualmente dal tab Web su PythonAnywhere"
fi

# Verifica che il codice sia aggiornato
echo ""
echo "🔍 Verifica codice aggiornato..."
if grep -q "PythonAnywhere detected - limiting batch size" app.py 2>/dev/null; then
    echo "   ❌ ERRORE: Il codice vecchio è ancora presente!"
    echo "   💡 Prova a ricaricare manualmente dal tab Web su PythonAnywhere"
else
    echo "   ✅ Codice nuovo confermato (limiti PythonAnywhere rimossi)"
fi
echo ""

echo "=================================================="
echo "✅ Deploy completato!"
echo "=================================================="
echo ""


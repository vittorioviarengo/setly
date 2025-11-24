#!/bin/bash
# Script per verificare e fixare il menu su PythonAnywhere

cd ~/setly
workon setly-env

echo "🔍 Verifica traduzioni..."
echo ""

# Verifica se la traduzione è corretta nel .po
if grep -q 'msgstr "Istruzioni"' translations/it/LC_MESSAGES/messages.po; then
    echo "✅ File .po ha 'Istruzioni'"
else
    echo "❌ File .po NON ha 'Istruzioni' - aggiorna il file"
fi

# Ricompila le traduzioni
echo ""
echo "🔄 Ricompilo traduzioni..."
pybabel compile -d translations

# Verifica che il .mo sia stato aggiornato
echo ""
echo "🔍 Verifica file .mo compilato..."
if [ -f translations/it/LC_MESSAGES/messages.mo ]; then
    echo "✅ File .mo esiste"
    ls -lh translations/it/LC_MESSAGES/messages.mo
else
    echo "❌ File .mo non trovato"
fi

echo ""
echo "✅ Procedura completata!"
echo ""
echo "📋 Prossimi passi:"
echo "1. Vai al tab 'Web' su PythonAnywhere"
echo "2. Clicca 'Reload vittorioviarengo.pythonanywhere.com'"
echo "3. Fai hard refresh nel browser (Ctrl+Shift+R)"


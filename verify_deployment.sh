#!/bin/bash
# Script per verificare che il deploy sia completo su PythonAnywhere

echo "🔍 Verifica Deploy su PythonAnywhere"
echo "====================================="
echo ""

cd ~/setly

# 1. Verifica git
echo "📥 Verifica Git:"
git log -1 --oneline
echo ""

# 2. Verifica file modificati
echo "📄 Verifica file help.html:"
if [ -f templates/help.html ]; then
    # Controlla se ha il nuovo header
    if grep -q "back-to-search-link-wrapper" templates/help.html; then
        echo "   ✅ File help.html aggiornato (contiene nuovo header)"
    else
        echo "   ❌ File help.html NON aggiornato"
    fi
    
    # Controlla se la sezione "Iniziamo" è stata rimossa
    if grep -q "help-card-header" templates/help.html && grep -q "Iniziamo" templates/help.html; then
        echo "   ⚠️  Sezione 'Iniziamo' ancora presente"
    else
        echo "   ✅ Sezione 'Iniziamo' rimossa"
    fi
else
    echo "   ❌ File templates/help.html non trovato"
fi
echo ""

# 3. Verifica traduzioni
echo "🌐 Verifica traduzioni:"
if [ -f translations/it/LC_MESSAGES/messages.po ]; then
    if grep -q 'msgstr "Istruzioni"' translations/it/LC_MESSAGES/messages.po; then
        echo "   ✅ Traduzione 'Istruzioni' presente"
    else
        echo "   ❌ Traduzione 'Istruzioni' NON trovata"
    fi
else
    echo "   ⚠️  File traduzioni non trovato"
fi
echo ""

# 4. Verifica file CSS
echo "🎨 Verifica CSS:"
if [ -f static/css/search-mobile.css ]; then
    if grep -q "font-size: 14px" static/css/search-mobile.css; then
        echo "   ✅ Font size menu aggiornato a 14px"
    else
        echo "   ❌ Font size menu NON aggiornato"
    fi
else
    echo "   ❌ File CSS non trovato"
fi
echo ""

echo "✅ Verifica completata!"
echo ""
echo "Se tutti i file sono aggiornati ma la pagina non cambia:"
echo "1. Ricarica la web app dal tab Web"
echo "2. Fai hard refresh nel browser (Ctrl+Shift+R)"
echo "3. Prova in modalità incognito"


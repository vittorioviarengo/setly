#!/bin/bash
# Script per scaricare il database da PythonAnywhere

echo "📥 Download database da PythonAnywhere"
echo "========================================"
echo ""

# Crea directory per i backup se non esiste
mkdir -p backups/pythonanywhere

# Scarica il database
echo "Scarico songs.db da PythonAnywhere..."
scp vittorioviarengo@ssh.pythonanywhere.com:~/setly/songs.db backups/pythonanywhere/songs_$(date +%Y%m%d_%H%M%S).db

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Database scaricato con successo!"
    echo "📁 Percorso: backups/pythonanywhere/"
    echo ""
    echo "Ora puoi analizzarlo con:"
    echo "   python3 check_requests.py"
    echo ""
    echo "Oppure copialo come songs.db locale per analisi:"
    echo "   cp backups/pythonanywhere/songs_*.db songs.db"
else
    echo ""
    echo "❌ Errore durante il download"
    echo ""
    echo "Alternative:"
    echo "1. Vai su PythonAnywhere → Files tab"
    echo "2. Naviga in ~/setly/"
    echo "3. Clicca su songs.db → Download"
fi


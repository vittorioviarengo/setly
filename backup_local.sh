#!/bin/bash
# Script per fare backup completo locale del progetto

echo "💾 Backup Locale Completo"
echo "========================"
echo ""

# Crea directory backup con timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="backups/local_backup_${TIMESTAMP}"
mkdir -p "$BACKUP_DIR"

echo "📁 Creo backup in: $BACKUP_DIR"
echo ""

# 1. Backup database
echo "📦 1. Backup database..."
if [ -f "songs.db" ]; then
    cp songs.db "$BACKUP_DIR/songs.db"
    echo "   ✅ Database copiato"
else
    echo "   ⚠️  Database non trovato"
fi
echo ""

# 2. Backup file di configurazione
echo "📄 2. Backup file di configurazione..."
if [ -f ".env" ]; then
    cp .env "$BACKUP_DIR/.env"
    echo "   ✅ .env copiato"
fi
if [ -f "requirements.txt" ]; then
    cp requirements.txt "$BACKUP_DIR/requirements.txt"
    echo "   ✅ requirements.txt copiato"
fi
echo ""

# 3. Backup traduzioni
echo "🌐 3. Backup traduzioni..."
if [ -d "translations" ]; then
    cp -r translations "$BACKUP_DIR/translations"
    echo "   ✅ Traduzioni copiate"
fi
echo ""

# 4. Backup script importanti
echo "🔧 4. Backup script..."
mkdir -p "$BACKUP_DIR/scripts"
for script in migrate_requests_table.py check_requests.py migrate_to_tenant.py; do
    if [ -f "$script" ]; then
        cp "$script" "$BACKUP_DIR/scripts/"
        echo "   ✅ $script copiato"
    fi
done
echo ""

# 5. Backup file di documentazione
echo "📚 5. Backup documentazione..."
mkdir -p "$BACKUP_DIR/docs"
for doc in *.md DEPLOYMENT.md PYTHONANYWHERE*.md MIGRATE*.md; do
    if [ -f "$doc" ]; then
        cp "$doc" "$BACKUP_DIR/docs/" 2>/dev/null || true
    fi
done
echo "   ✅ Documentazione copiata"
echo ""

# 6. Crea archivio compresso
echo "🗜️  6. Creo archivio compresso..."
cd backups
tar -czf "local_backup_${TIMESTAMP}.tar.gz" "local_backup_${TIMESTAMP}"
cd ..
echo "   ✅ Archivio creato: backups/local_backup_${TIMESTAMP}.tar.gz"
echo ""

# 7. Calcola dimensione
SIZE=$(du -sh "$BACKUP_DIR" | cut -f1)
ARCHIVE_SIZE=$(du -sh "backups/local_backup_${TIMESTAMP}.tar.gz" | cut -f1)
echo "📊 Dimensione backup:"
echo "   Directory: $SIZE"
echo "   Archivio: $ARCHIVE_SIZE"
echo ""

# 8. Lista file nel backup
echo "📋 Contenuto backup:"
ls -lh "$BACKUP_DIR"
echo ""

echo "=" * 50
echo "✅ Backup completato!"
echo "=" * 50
echo ""
echo "📁 Posizione: $BACKUP_DIR"
echo "📦 Archivio: backups/local_backup_${TIMESTAMP}.tar.gz"
echo ""
echo "💡 Per ripristinare:"
echo "   tar -xzf backups/local_backup_${TIMESTAMP}.tar.gz"
echo ""


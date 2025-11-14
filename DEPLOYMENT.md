# 🚀 Deployment Guide - PythonAnywhere

## Step 1: Preparare il Repository

### 1.1 Inizializza Git (se non l'hai già fatto)
```bash
cd "/Users/vittorioviarengo/Code/Songs 2.0"
git init
git add .
git commit -m "Initial commit for deployment"
```

### 1.2 Crea un repository su GitHub
1. Vai su https://github.com/new
2. Nome repository: `setly-app` (o quello che preferisci)
3. NON aggiungere README, .gitignore, o license (li hai già)
4. Crea il repository

### 1.3 Push del codice
```bash
git remote add origin https://github.com/TUO-USERNAME/setly-app.git
git branch -M main
git push -u origin main
```

---

## Step 2: Setup su PythonAnywhere

### 2.1 Login e Console
1. Vai su https://www.pythonanywhere.com
2. Login con il tuo account `vittorioviarengo`
3. Clicca su **"Consoles"** → **"Bash"**

### 2.2 Clone del Repository
Nella console Bash:
```bash
cd ~
git clone https://github.com/TUO-USERNAME/setly-app.git
cd setly-app
```

### 2.3 Crea Virtual Environment
```bash
mkvirtualenv --python=/usr/bin/python3.10 setly-env
```

### 2.4 Installa Dipendenze
```bash
workon setly-env
pip install -r requirements.txt
```

### 2.5 Compila le Traduzioni
```bash
pybabel compile -d translations
```

---

## Step 3: Configurazione Web App

### 3.1 Crea Web App
1. Vai su **"Web"** tab
2. Clicca **"Add a new web app"**
3. Scegli dominio: `vittorioviarengo.pythonanywhere.com`
4. Scegli **"Manual configuration"**
5. Scegli **Python 3.10**

### 3.2 Configura Virtual Environment
Nella sezione "Virtualenv":
```
/home/vittorioviarengo/.virtualenvs/setly-env
```

### 3.3 Configura WSGI File
1. Clicca sul link del WSGI file (es: `/var/www/vittorioviarengo_pythonanywhere_com_wsgi.py`)
2. **CANCELLA TUTTO** il contenuto
3. **INCOLLA QUESTO**:

```python
import sys
import os

# Add your project directory to the sys.path
project_home = '/home/vittorioviarengo/setly-app'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Set environment variables
os.environ['SECRET_KEY'] = 'CHANGE-THIS-TO-A-RANDOM-STRING-XXXXX'
os.environ['FLASK_ENV'] = 'production'

# Import Flask app
from app import app as application
```

4. **SALVA** il file

### 3.4 Genera un SECRET_KEY Sicuro
Nella console Bash:
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```
Copia l'output e sostituisci `CHANGE-THIS-TO-A-RANDOM-STRING-XXXXX` nel WSGI file.

---

## Step 4: Configura Static Files

Nel tab **"Web"**:

### 4.1 Static files
Aggiungi queste mappature in "Static files":

| URL | Directory |
|-----|-----------|
| `/static/` | `/home/vittorioviarengo/setly-app/static` |

---

## Step 5: Inizializza Database

Nella console Bash:
```bash
cd ~/setly-app
workon setly-env
python3 -c "from app import create_connection, init_db; init_db()"
```

---

## Step 6: Crea Super Admin

Nella console Bash:
```bash
python3 -c "
import sqlite3
from werkzeug.security import generate_password_hash

conn = sqlite3.connect('songs.db')
cursor = conn.cursor()

# Create super admin
email = 'vittorio@viarengo.com'  # CHANGE THIS
password = 'YourSecurePassword123'  # CHANGE THIS
hashed = generate_password_hash(password)

cursor.execute('''
    INSERT OR REPLACE INTO super_admins (email, password_hash)
    VALUES (?, ?)
''', (email, hashed))

conn.commit()
conn.close()
print('Super admin created!')
"
```

---

## Step 7: Reload e Test

1. Torna al tab **"Web"**
2. Clicca il grosso bottone verde **"Reload vittorioviarengo.pythonanywhere.com"**
3. Vai su: `https://vittorioviarengo.pythonanywhere.com`
4. Login come super admin: `https://vittorioviarengo.pythonanywhere.com/superadmin`

---

## Step 8: Troubleshooting

### 8.1 Vedi gli Error Logs
Nel tab "Web", clicca su:
- **Error log**: Per vedere gli errori
- **Server log**: Per vedere le richieste

### 8.2 Problemi Comuni

**Errore: "ImportError: No module named..."**
```bash
workon setly-env
pip install NOME-MODULO
# Poi reload web app
```

**Errore: "OperationalError: no such table..."**
```bash
cd ~/setly-app
python3
>>> from app import init_db
>>> init_db()
>>> exit()
```

**Errore: "Permission denied" per database**
```bash
chmod 664 ~/setly-app/songs.db
chmod 775 ~/setly-app
```

**Static files non caricano**
- Verifica i path in "Static files" (devono essere assoluti)
- Reload web app

---

## Step 9: Post-Deployment

### 9.1 Test Completo
- [ ] Login super admin funziona
- [ ] Crea tenant di test
- [ ] Login tenant funziona
- [ ] Wizard setup funziona
- [ ] Carica canzoni (CSV)
- [ ] Spotify fetch funziona
- [ ] QR code genera
- [ ] PDF genera
- [ ] End-user può richiedere canzone
- [ ] Queue aggiorna in real-time

### 9.2 Backup
```bash
# Setup backup giornaliero (crontab)
crontab -e
```
Aggiungi:
```
0 2 * * * cp ~/setly-app/songs.db ~/backups/songs-$(date +\%Y\%m\%d).db
```

---

## 🎉 Congratulazioni!

La tua app è live su: `https://vittorioviarengo.pythonanywhere.com`

---

## 📝 Note Importanti

1. **FREE Account Limits**:
   - 1 web app
   - 512MB storage
   - 100k hits/giorno
   - MySQL database (optional, stai usando SQLite)

2. **Upgrade Consigliato ($5/mese "Hacker")**:
   - 2 web apps
   - 1GB storage
   - Custom domain (vittorio.com)
   - SSH access
   - Always-on tasks (per backup automatici)

3. **Database SQLite**:
   - Va bene per beta (10-20 artisti)
   - Per scala maggiore, considera PostgreSQL/MySQL

4. **Updates**:
   ```bash
   cd ~/setly-app
   git pull
   workon setly-env
   pip install -r requirements.txt
   pybabel compile -d translations
   # Poi reload web app
   ```

---

## 🆘 Serve Aiuto?

- PythonAnywhere Help: https://help.pythonanywhere.com
- Forum: https://www.pythonanywhere.com/forums/
- Contattami per problemi specifici!


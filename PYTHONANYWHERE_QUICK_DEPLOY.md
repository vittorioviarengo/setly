# 🚀 PythonAnywhere Quick Deploy - Setly

## Step 1: Login
1. Vai su: https://www.pythonanywhere.com/login/
2. Login con: `vittorioviarengo`

---

## Step 2: Bash Console
1. Clicca **"Consoles"** (top menu)
2. Clicca **"Bash"**

---

## Step 3: Clone Repository
Nella console Bash, copia e incolla questi comandi **UNO ALLA VOLTA**:

```bash
cd ~
git clone https://github.com/vittorioviarengo/setly.git
cd setly
```

---

## Step 4: Create Virtual Environment
```bash
mkvirtualenv --python=/usr/bin/python3.10 setly-env
```

---

## Step 5: Install Dependencies
```bash
pip install -r requirements.txt
```

Questo prenderà qualche minuto... ☕

---

## Step 6: Compile Translations
```bash
pybabel compile -d translations
```

---

## Step 7: Create Web App
1. Clicca su **"Web"** tab (top menu)
2. Clicca **"Add a new web app"**
3. Dominio: `vittorioviarengo.pythonanywhere.com` → **Next**
4. Scegli: **"Manual configuration"** → **Next**
5. Scegli: **"Python 3.10"** → **Next**

---

## Step 8: Configure Virtual Environment
Nella pagina "Web":

1. Trova sezione **"Virtualenv"**
2. Clicca **"Enter path to a virtualenv..."**
3. Incolla: `/home/vittorioviarengo/.virtualenvs/setly-env`
4. Clicca ✓ (checkmark)

---

## Step 9: Configure WSGI File
1. Trova sezione **"Code"**
2. Clicca sul link **WSGI configuration file** (es: `/var/www/vittorioviarengo_pythonanywhere_com_wsgi.py`)
3. **CANCELLA TUTTO** il contenuto
4. **INCOLLA QUESTO**:

```python
import sys
import os

# Add project directory
project_home = '/home/vittorioviarengo/setly'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Set environment variables
os.environ['SECRET_KEY'] = 'CHANGE-THIS-NOW-TO-RANDOM-STRING-XXXXX'
os.environ['FLASK_ENV'] = 'production'

# Import Flask app
from app import app as application
```

5. **SALVA** (Ctrl+S o bottone Save)

---

## Step 10: Generate SECRET_KEY
Torna alla Bash console e esegui:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Copia l'output (una lunga stringa tipo: `a1b2c3d4e5f6...`)

Torna al WSGI file e sostituisci `CHANGE-THIS-NOW-TO-RANDOM-STRING-XXXXX` con quella stringa.

**SALVA** di nuovo!

---

## Step 11: Configure Static Files
Nella pagina **"Web"**:

1. Trova sezione **"Static files"**
2. Clicca **"Enter URL"**
3. URL: `/static/`
4. Directory: `/home/vittorioviarengo/setly/static`
5. Clicca ✓

---

## Step 12: Initialize Database
Torna alla Bash console:

```bash
cd ~/setly
workon setly-env
python3 -c "from app import init_db; init_db()"
```

---

## Step 13: Create Super Admin
```bash
python3 create_superadmin.py
```

Ti chiederà:
- Email: `vittorio@viarengo.com` (o la tua email)
- Password: (scegli una password forte!)
- Conferma password

---

## Step 14: Reload Web App
1. Torna al tab **"Web"**
2. Clicca il GROSSO bottone verde: **"Reload vittorioviarengo.pythonanywhere.com"**

---

## Step 15: 🎉 TEST!
Apri: **https://vittorioviarengo.pythonanywhere.com**

Se vedi la pagina, funziona! 🚀

---

## Step 16: Login Super Admin
Vai su: **https://vittorioviarengo.pythonanywhere.com/superadmin**

Login con l'email e password che hai creato!

---

## 🐛 Problemi?

Se qualcosa non funziona:

1. Vai al tab **"Web"**
2. Clicca **"Error log"** (link rosso in alto)
3. Cerca l'errore più recente in fondo al file
4. Fammi vedere l'errore!

---

## ✅ Checklist Finale
- [ ] App carica su vittorioviarengo.pythonanywhere.com
- [ ] Login super admin funziona
- [ ] Crea un tenant di test
- [ ] Testa il wizard
- [ ] Carica qualche canzone
- [ ] Testa QR code
- [ ] Testa PDF generation

---

**Tempo stimato: 15-20 minuti** ⏱️

Buon deploy! 🚀


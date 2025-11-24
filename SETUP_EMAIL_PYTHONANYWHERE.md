# 📧 Setup Email su PythonAnywhere

## Opzione 1: Via Web Tab (Consigliato)

1. Vai su PythonAnywhere → **Web** tab
2. Scorri fino a **"Environment variables"**
3. Aggiungi queste variabili:
   ```
   MAIL_USERNAME=your-email@gmail.com
   MAIL_PASSWORD=your-app-password
   MAIL_SERVER=smtp.gmail.com
   MAIL_PORT=587
   MAIL_USE_TLS=true
   MAIL_DEFAULT_SENDER=noreply@setly.app
   ```
4. Clicca **"Reload"** per applicare le modifiche

## Opzione 2: Via WSGI File

1. Vai su PythonAnywhere → **Web** tab
2. Clicca sul link **"WSGI configuration file"**
3. Aggiungi le variabili d'ambiente prima di `from app import app`:

```python
import sys
import os

# Add your project directory to the sys.path
project_home = '/home/vittorioviarengo/setly'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Set environment variables
os.environ['SECRET_KEY'] = 'your-secret-key-here'
os.environ['MAIL_USERNAME'] = 'your-email@gmail.com'
os.environ['MAIL_PASSWORD'] = 'your-app-password'
os.environ['MAIL_SERVER'] = 'smtp.gmail.com'
os.environ['MAIL_PORT'] = '587'
os.environ['MAIL_USE_TLS'] = 'true'
os.environ['MAIL_DEFAULT_SENDER'] = 'noreply@setly.app'

# Import your Flask app
from app import app as application
```

4. **SALVA** il file
5. Clicca **"Reload"** nel tab Web

## Generare Gmail App Password

1. Vai su: https://myaccount.google.com/apppasswords
2. Se non vedi "App passwords", abilita prima la 2-Factor Authentication
3. Genera una nuova App Password:
   - App: Mail
   - Device: Other (Custom name) → "Setly PythonAnywhere"
4. Copia la password a 16 caratteri (rimuovi gli spazi)

## Test

Dopo aver configurato:
1. Vai su `/superadmin/tenants`
2. Clicca "Invite" su un tenant
3. Dovresti vedere "Invitation email sent successfully!" invece dell'errore

## Troubleshooting

**Errore: "Email not configured"**
- Verifica che le variabili siano state aggiunte correttamente
- Ricarica la web app dopo aver aggiunto le variabili
- Controlla che non ci siano spazi extra nei valori

**Errore: "Authentication failed"**
- Stai usando la password normale invece di App Password
- Genera una nuova App Password e usala

**Email non arriva**
- Controlla la cartella spam
- Verifica che l'indirizzo email del tenant sia corretto
- Controlla i log errori su PythonAnywhere


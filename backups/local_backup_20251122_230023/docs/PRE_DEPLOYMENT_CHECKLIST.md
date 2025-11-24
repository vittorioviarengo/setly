# ✅ Pre-Deployment Checklist

Usa questa checklist prima di fare il deployment su PythonAnywhere.

## 📋 Codice

- [x] `requirements.txt` aggiornato con tutte le dipendenze
- [x] `.gitignore` configurato (no database, no .env, no logs)
- [x] `README.md` creato
- [x] `DEPLOYMENT.md` creato con istruzioni complete
- [ ] Tutti i file committati su git
- [ ] Repository creato su GitHub
- [ ] Push del codice su GitHub completato

## 🔐 Sicurezza

- [ ] SECRET_KEY generato e configurato nel WSGI file
- [ ] Password del super admin scelta (forte!)
- [ ] .env non committato (controllare .gitignore)
- [ ] Database locale non committato

## 🗄️ Database

- [ ] `songs.db` esiste localmente
- [ ] Tabelle create (super_admins, tenants, songs, requests, etc.)
- [ ] Un tenant di test creato localmente per verificare

## 🌍 Traduzioni

- [ ] File `.mo` compilati (`pybabel compile -d translations`)
- [ ] Testato almeno Italiano e Inglese
- [ ] Nessun errore di traduzione visibile

## 🎨 Assets

- [ ] Tutte le immagini in `/static/` committate
- [ ] CSS compilato/minificato (se applicabile)
- [ ] JavaScript testato in produzione mode
- [ ] Favicon presente

## ✅ Testing Locale

Prima del deployment, testa tutto localmente:

### Super Admin
- [ ] Login super admin: http://localhost:5001/superadmin
- [ ] Crea nuovo tenant
- [ ] Modifica settings
- [ ] Visualizza lista tenants

### Tenant Admin
- [ ] Login tenant: http://localhost:5001/SLUG/login
- [ ] Wizard completo
- [ ] Carica CSV canzoni
- [ ] Modifica profilo (nome, bio, logo, banner)
- [ ] Spotify fetch funziona
- [ ] Genera PDF
- [ ] Genera QR code
- [ ] Queue management

### End User
- [ ] Apri pagina pubblica: http://localhost:5001/SLUG
- [ ] Ricerca canzoni
- [ ] Richiedi canzone
- [ ] Vedi "Your Requests"
- [ ] Auto-refresh funziona

## 🚀 Ready for Deployment!

Se tutti i check sono ✅, sei pronto per:
1. Seguire `DEPLOYMENT.md`
2. Deploy su PythonAnywhere
3. Test in produzione

---

## 📝 Post-Deployment Testing

Dopo il deployment, ripeti questi test su:
`https://vittorioviarengo.pythonanywhere.com`

- [ ] Super admin login
- [ ] Crea tenant di test
- [ ] Tenant login
- [ ] Wizard funziona
- [ ] CSV upload
- [ ] Spotify fetch
- [ ] PDF generation
- [ ] QR code
- [ ] End-user flow completo
- [ ] Mobile responsive (testa su telefono!)

## 🐛 Known Issues to Monitor

- Performance con 10+ tenants
- Spotify API rate limits
- Database size growth
- Static files caching

## 📧 Support

Se qualcosa non funziona:
1. Controlla error log su PythonAnywhere
2. Controlla server log
3. Verifica file WSGI configuration
4. Verifica virtual environment attivo
5. Contattami!

---

Buon deployment! 🚀


# Setup PayPal per i Contributi

Per abilitare i contributi con PayPal, ogni musicista deve configurare il proprio **link PayPal.me**.

## 🎯 Come Funziona (Semplificato!)

Il sistema usa **PayPal.me**, che è molto più semplice:
- Il musicista inserisce solo il suo link PayPal.me (es. `paypal.me/vittorio`)
- Quando un utente lascia un contributo, viene reindirizzato a PayPal.me
- Il pagamento va direttamente all'account PayPal del musicista
- Nessuna configurazione complessa necessaria!

## 1. Configurazione per il Musicista

Ogni musicista deve:

1. **Avere un account PayPal** (personale o business)
2. **Creare il proprio link PayPal.me**:
   - Vai su https://www.paypal.com/paypalme
   - Accedi con il tuo account PayPal
   - Crea il tuo link personalizzato (es. `paypal.me/vittorio`)
3. **Inserire il link nella pagina admin**:
   - Vai su `http://localhost:5001/<tuo-slug>/admin`
   - Cerca la sezione "PayPal Link"
   - Inserisci il tuo link PayPal.me
   - Clicca "Save PayPal Link"

### Esempio:
- Link PayPal.me: `paypal.me/vittorio`
- Quando qualcuno lascia un contributo di 5€, viene reindirizzato a: `paypal.me/vittorio?amount=5.00`

## 2. Configurazione (Opzionale) per Credenziali API

**Nota:** Se vuoi usare l'SDK PayPal integrato (più complesso ma con più controllo), puoi ancora configurare le credenziali API. Ma per la maggior parte dei casi, PayPal.me è sufficiente e molto più semplice.

Se vuoi usare l'SDK PayPal, aggiungi queste variabili d'ambiente:

```bash
# PayPal API Configuration (Opzionale - solo se vuoi usare SDK)
PAYPAL_CLIENT_ID=your_client_id_here
PAYPAL_CLIENT_SECRET=your_client_secret_here
PAYPAL_MODE=sandbox  # o "live" per produzione
```

## 3. Come Funziona il Flusso

1. **Utente richiede canzone con contributo**:
   - Seleziona importo (2€, 5€, 10€, o altro)
   - Clicca "Invia richiesta + contributo X €"

2. **Richiesta inviata**:
   - La canzone viene aggiunta alla coda
   - Il contributo viene registrato nel database

3. **Pagamento PayPal.me**:
   - Si apre un dialog con il link PayPal.me
   - L'utente clicca "Vai a PayPal"
   - Viene reindirizzato a PayPal.me con l'importo precompilato
   - Completa il pagamento su PayPal
   - Il pagamento va direttamente al musicista

## 4. Vantaggi di PayPal.me

✅ **Semplice**: Il musicista inserisce solo un link  
✅ **Sicuro**: Nessuna gestione di credenziali API  
✅ **Diretto**: I pagamenti vanno direttamente al musicista  
✅ **Scalabile**: Ogni musicista ha il proprio link  
✅ **Nessuna configurazione complessa**: Funziona subito!

## 5. Test

1. Il musicista inserisce il suo link PayPal.me nella pagina admin
2. Avvia un gig con "Enable tips" selezionato
3. Quando un utente prova a lasciare un contributo:
   - Vede il dialog con l'importo
   - Clicca "Vai a PayPal"
   - Viene reindirizzato a PayPal.me
   - Completa il pagamento

## Troubleshooting

### Il link PayPal.me non funziona
- Verifica che il link sia nel formato corretto: `paypal.me/tuonome`
- Assicurati che il link sia stato salvato nella pagina admin
- Controlla che il link sia valido su paypal.com/paypalme

### Il contributo non viene registrato
- Verifica che il gig abbia "Enable tips" selezionato
- Controlla i log del backend per errori
- Verifica che la tabella `tip_intents` esista nel database



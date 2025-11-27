#!/usr/bin/env python3
"""
Script per testare il backend delle mance (tips)
Esegui questo script dopo aver avviato l'app Flask
"""

import requests
import json
import sys

# Configurazione
BASE_URL = "http://localhost:5001"  # Modifica se necessario
TEST_USER = "TestUser"
TEST_TENANT_SLUG = "roberto"  # Modifica con il tuo tenant slug

def print_section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")

def test_database_tables():
    """Verifica che le tabelle del database esistano"""
    print_section("TEST 1: Verifica Tabelle Database")
    print("Verifica manuale necessaria:")
    print("1. Controlla che la tabella 'gigs' abbia la colonna 'tip_enabled'")
    print("2. Controlla che la tabella 'tip_intents' esista")
    print("\nPuoi verificare con:")
    print("  sqlite3 songs.db '.schema gigs'")
    print("  sqlite3 songs.db '.schema tip_intents'")

def test_get_active_gig():
    """Test: Ottieni gig attivo"""
    print_section("TEST 2: Get Active Gig")
    try:
        url = f"{BASE_URL}/{TEST_TENANT_SLUG}/get_active_gig"
        response = requests.get(url)
        print(f"URL: {url}")
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.json() if response.status_code == 200 else None
    except Exception as e:
        print(f"Errore: {e}")
        return None

def test_start_gig_with_tips():
    """Test: Avvia un gig con tips abilitati"""
    print_section("TEST 3: Start Gig con Tips Abilitati")
    try:
        url = f"{BASE_URL}/{TEST_TENANT_SLUG}/start_gig"
        # Nota: Richiede autenticazione come tenant admin
        data = {
            "gig_name": "Test Gig con Tips",
            "tip_enabled": True
        }
        print(f"URL: {url}")
        print(f"Data: {json.dumps(data, indent=2)}")
        print("\n⚠️  Questo endpoint richiede autenticazione come tenant admin")
        print("   Esegui manualmente dal frontend o con una sessione autenticata")
    except Exception as e:
        print(f"Errore: {e}")

def test_request_song_without_tip():
    """Test: Richiedi canzone senza contributo"""
    print_section("TEST 4: Request Song senza Tip")
    try:
        # Assumendo song_id = 1 (modifica se necessario)
        song_id = 1
        url = f"{BASE_URL}/request_song/{song_id}"
        data = {
            "user": TEST_USER
        }
        headers = {"Content-Type": "application/json"}
        
        print(f"URL: {url}")
        print(f"Data: {json.dumps(data, indent=2)}")
        print("\n⚠️  Questo endpoint richiede una sessione valida")
        print("   Esegui manualmente dal frontend o con una sessione autenticata")
        
        # Uncomment per test reale (richiede sessione)
        # response = requests.post(url, json=data, headers=headers)
        # print(f"Status: {response.status_code}")
        # print(f"Response: {json.dumps(response.json(), indent=2)}")
    except Exception as e:
        print(f"Errore: {e}")

def test_request_song_with_tip():
    """Test: Richiedi canzone con contributo"""
    print_section("TEST 5: Request Song con Tip")
    try:
        song_id = 1
        url = f"{BASE_URL}/request_song/{song_id}"
        data = {
            "user": TEST_USER,
            "tip_amount": 5.0  # 5 euro
        }
        headers = {"Content-Type": "application/json"}
        
        print(f"URL: {url}")
        print(f"Data: {json.dumps(data, indent=2)}")
        print("\n⚠️  Questo endpoint richiede una sessione valida")
        print("   Esegui manualmente dal frontend o con una sessione autenticata")
    except Exception as e:
        print(f"Errore: {e}")

def test_create_paypal_order():
    """Test: Crea ordine PayPal"""
    print_section("TEST 6: Create PayPal Order")
    try:
        url = f"{BASE_URL}/api/create_paypal_order"
        data = {
            "tip_intent_id": 1  # Sostituisci con un ID reale
        }
        headers = {"Content-Type": "application/json"}
        
        print(f"URL: {url}")
        print(f"Data: {json.dumps(data, indent=2)}")
        print("\n⚠️  Questo endpoint richiede:")
        print("   1. Una sessione valida")
        print("   2. Un tip_intent_id esistente")
        print("   3. Variabili d'ambiente PAYPAL_CLIENT_ID e PAYPAL_CLIENT_SECRET")
    except Exception as e:
        print(f"Errore: {e}")

def test_create_standalone_tip():
    """Test: Crea contributo standalone"""
    print_section("TEST 7: Create Standalone Tip")
    try:
        url = f"{BASE_URL}/api/create_tip"
        data = {
            "tip_amount": 10.0  # 10 euro
        }
        headers = {"Content-Type": "application/json"}
        
        print(f"URL: {url}")
        print(f"Data: {json.dumps(data, indent=2)}")
        print("\n⚠️  Questo endpoint richiede una sessione valida")
    except Exception as e:
        print(f"Errore: {e}")

def test_update_tip_enabled():
    """Test: Aggiorna tip_enabled per gig attivo"""
    print_section("TEST 8: Update Tip Enabled")
    try:
        url = f"{BASE_URL}/{TEST_TENANT_SLUG}/update_tip_enabled"
        data = {
            "tip_enabled": False
        }
        headers = {"Content-Type": "application/json"}
        
        print(f"URL: {url}")
        print(f"Data: {json.dumps(data, indent=2)}")
        print("\n⚠️  Questo endpoint richiede autenticazione come tenant admin")
    except Exception as e:
        print(f"Errore: {e}")

def main():
    print("\n" + "="*60)
    print("  TEST BACKEND - SISTEMA MANCE (TIPS)")
    print("="*60)
    print(f"\nBase URL: {BASE_URL}")
    print(f"Tenant Slug: {TEST_TENANT_SLUG}")
    print(f"Test User: {TEST_USER}")
    
    # Esegui tutti i test
    test_database_tables()
    test_get_active_gig()
    test_start_gig_with_tips()
    test_request_song_without_tip()
    test_request_song_with_tip()
    test_create_paypal_order()
    test_create_standalone_tip()
    test_update_tip_enabled()
    
    print_section("ISTRUZIONI PER TEST MANUALI")
    print("""
Per testare completamente il backend:

1. VERIFICA DATABASE:
   sqlite3 songs.db ".schema gigs"
   sqlite3 songs.db ".schema tip_intents"
   sqlite3 songs.db "SELECT * FROM gigs LIMIT 1;"

2. AVVIA L'APP:
   python app.py
   (L'app dovrebbe essere su http://localhost:5001)

3. TEST CON CURL (dopo aver fatto login):
   
   # Get active gig
   curl http://localhost:5001/roberto/get_active_gig
   
   # Start gig con tips
   curl -X POST http://localhost:5001/roberto/start_gig \\
     -H "Content-Type: application/json" \\
     -H "Cookie: session=YOUR_SESSION_COOKIE" \\
     -d '{"gig_name": "Test Gig", "tip_enabled": true}'
   
   # Request song con tip
   curl -X POST http://localhost:5001/request_song/1 \\
     -H "Content-Type: application/json" \\
     -H "Cookie: session=YOUR_SESSION_COOKIE" \\
     -d '{"user": "TestUser", "tip_amount": 5.0}'

4. VERIFICA NEL DATABASE:
   sqlite3 songs.db "SELECT * FROM tip_intents ORDER BY id DESC LIMIT 5;"
   sqlite3 songs.db "SELECT id, name, tip_enabled FROM gigs WHERE is_active = 1;"

5. CONFIGURA PAYPAL (opzionale per test completi):
   export PAYPAL_CLIENT_ID="your_client_id"
   export PAYPAL_CLIENT_SECRET="your_client_secret"
   export PAYPAL_MODE="sandbox"  # o "live"
    """)
    
    print("\n" + "="*60)
    print("  Test completati!")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()


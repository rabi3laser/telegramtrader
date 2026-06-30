"""
GÉNÉRATEUR DE STRING SESSION TELEGRAM
Exécutez ce script UNE SEULE FOIS localement pour obtenir votre StringSession

Usage:
    python generate_session.py

Vous devrez:
1. Entrer votre numéro de téléphone
2. Entrer le code reçu par SMS
3. Copier la StringSession générée dans les Secrets Streamlit
"""
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
import os
from dotenv import load_dotenv

# Charger variables d'environnement
load_dotenv()

API_ID = int(os.getenv("TELEGRAM_API_ID", "26848264"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "da038e8c2be2ee1530bbd75fea679ff6")

print("="*70)
print("  GÉNÉRATEUR DE STRING SESSION TELEGRAM")
print("="*70)
print("\nCe script va générer une StringSession pour votre compte Telegram.")
print("Vous devrez entrer le code SMS reçu sur votre téléphone.\n")

async def main():
    # Créer client avec StringSession vide
    async with TelegramClient(StringSession(), API_ID, API_HASH) as client:
        print("✅ Connexion établie!")
        print("\nVotre StringSession (à copier dans Streamlit Secrets):")
        print("-" * 70)
        print(client.session.save())
        print("-" * 70)
        print("\n📋 Instructions:")
        print("1. Copiez la StringSession ci-dessus")
        print("2. Allez sur Streamlit Cloud → Settings → Secrets")
        print("3. Ajoutez:")
        print("""
[telegram]
api_id = "{}"
api_hash = "{}"
session_string = "COLLEZ_ICI_LA_STRING_SESSION"
        """.format(API_ID, API_HASH))
        print("\n✅ Terminé! Vous pouvez fermer ce script.")

if __name__ == "__main__":
    asyncio.run(main())

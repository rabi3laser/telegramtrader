"""
OUTIL DE DIAGNOSTIC - Verifier le detecteur de signaux sur de vrais canaux
Usage: python test_real_channel.py @username_du_canal [nombre_messages]
"""
import asyncio
import sys
import io
from pathlib import Path

# Forcer l'encodage UTF-8 pour Windows (support des emojis)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Charger les secrets depuis le fichier .streamlit/secrets.toml
secrets_path = Path(__file__).parent / ".streamlit" / "secrets.toml"
if secrets_path.exists():
    import tomllib
    with open(secrets_path, "rb") as f:
        secrets = tomllib.load(f)
    if "telegram" in secrets:
        API_ID = int(secrets["telegram"]["api_id"])
        API_HASH = secrets["telegram"]["api_hash"]
    else:
        API_ID = int(secrets.get("TELEGRAM_API_ID", 0))
        API_HASH = secrets.get("TELEGRAM_API_HASH", "")
else:
    print("Erreur: Fichier .streamlit/secrets.toml introuvable")
    sys.exit(1)

# Demander la session string
SESSION_FILE = Path(__file__).parent / "session_string.txt"
if SESSION_FILE.exists():
    SESSION_STRING = SESSION_FILE.read_text().strip()
else:
    print("Collez votre StringSession (generee par generate_session.py):")
    SESSION_STRING = input().strip()
    if not SESSION_STRING:
        print("Session requise")
        sys.exit(1)
    SESSION_FILE.write_text(SESSION_STRING)
    print(f"Session sauvegardee dans {SESSION_FILE}")

from telethon import TelegramClient
from telethon.sessions import StringSession
from signal_detector import is_signal_message, detect_signal_type, detect_markets, extract_signal_data, calculate_signal_quality


async def diagnose_channel(username, limit=50):
    """Recupere les messages d'un canal et affiche ce que le detecteur trouve."""
    print(f"\n{'='*70}")
    print(f"DIAGNOSTIC DU CANAL: @{username}")
    print(f"Analyse des {limit} derniers messages")
    print(f"{'='*70}\n")

    async with TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH) as client:
        try:
            entity = await client.get_entity(username)
            print(f"Canal trouve: {entity.title}")
            print(f"Membres: {getattr(entity, 'participants_count', '?')}")
        except Exception as e:
            print(f"Erreur: {e}")
            return

        messages = []
        async for msg in client.iter_messages(entity, limit=limit):
            if msg.text:
                messages.append({'text': msg.text, 'date': msg.date, 'id': msg.id})

        print(f"{len(messages)} messages avec texte recuperes\n")
        if not messages:
            print("Aucun message avec texte dans ce canal")
            return

        signals_found = 0
        not_signals = 0

        for i, msg in enumerate(messages):
            text = msg['text']
            is_sig = is_signal_message(text)
            sig_type = detect_signal_type(text)
            markets = detect_markets(text)

            if is_sig:
                signals_found += 1
                data = extract_signal_data(text, msg['date'])
                quality = calculate_signal_quality(data) if data else 0
                entry = data.get('entry_price') if data else None
                tp = data.get('target_price') if data else None
                sl = data.get('stop_loss') if data else None
                print(f"  SIGNAL #{signals_found} (msg {i+1}/{len(messages)})")
                print(f"   Type: {sig_type.upper()} | Marches: {markets}")
                print(f"   Entry: {entry} | TP: {tp} | SL: {sl} | Qualite: {quality}/10")
                preview = text[:150].replace('\n', ' | ')
                print(f"   Texte: {preview}...")
                print()
            else:
                not_signals += 1
                if i < 10:
                    preview = text[:100].replace('\n', ' | ')
                    reason = []
                    if not sig_type:
                        reason.append("pas de BUY/SELL")
                    if not markets:
                        reason.append("pas de marche")
                    print(f"  Non-signal (msg {i+1}): {preview[:80]}...")
                    if reason:
                        print(f"   Raison: {', '.join(reason)}")
                    print()

        print(f"\n{'='*70}")
        print(f"RESUME")
        print(f"{'='*70}")
        print(f"Total messages: {len(messages)}")
        print(f"Signaux detectes: {signals_found}")
        print(f"Non-signaux: {not_signals}")
        if len(messages) > 0:
            print(f"Taux: {(signals_found/len(messages)*100):.1f}%")
        print(f"\nSi 0 signaux detectes, verifiez:")
        print(f"   1. Le canal poste-t-il vraiment des signaux (pas juste des analyses/news)?")
        print(f"   2. Les signaux utilisent-ils les mots BUY/SELL/LONG/SHORT?")
        print(f"   3. Mentionnent-ils un marche (GOLD/NASDAQ/OIL/BTC/etc.)?")
        print(f"   4. Les signaux sont-ils dans des images (non detectables par texte)?")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_real_channel.py @username_du_canal [nombre_messages]")
        print("Exemple: python test_real_channel.py TURBOtradersInternationals 100")
        sys.exit(1)
    username = sys.argv[1].lstrip('@')
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 50
    asyncio.run(diagnose_channel(username, limit))

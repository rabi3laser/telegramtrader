"""
SCAN DE TOUS VOS CANAUX TELEGRAM - Analyse la derniere semaine
Usage: python scan_my_channels.py

Recupere tous les canaux dont vous etes membre, analyse les messages
de la derniere semaine, et affiche un rapport complet.
"""
import asyncio
import sys
import io
from pathlib import Path
from datetime import datetime, timedelta, timezone

# Forcer l'encodage UTF-8 pour Windows (support des emojis)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Charger les secrets
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

# Charger la session
SESSION_FILE = Path(__file__).parent / "session_string.txt"
if SESSION_FILE.exists():
    SESSION_STRING = SESSION_FILE.read_text().strip()
else:
    print("Collez votre StringSession:")
    SESSION_STRING = input().strip()
    if not SESSION_STRING:
        sys.exit(1)
    SESSION_FILE.write_text(SESSION_STRING)

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.types import Channel, InputPeerEmpty
from signal_detector import is_signal_message, detect_signal_type, detect_markets, extract_signal_data, calculate_signal_quality


async def scan_all_channels():
    """Scanne tous les canaux dont l'utilisateur est membre."""

    print(f"\n{'='*70}")
    print(f"SCAN DE TOUS VOS CANAUX TELEGRAM")
    print(f"Periode: 7 derniers jours")
    print(f"{'='*70}\n")

    async with TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH) as client:
        # 1. Recuperer tous les dialogues
        print("Recuperation de vos canaux...")
        result = await client(GetDialogsRequest(
            offset_date=None,
            offset_id=0,
            offset_peer=InputPeerEmpty(),
            limit=500,
            hash=0
        ))

        # Filtrer uniquement les canaux (pas les megagroups)
        channels = []
        for chat in result.chats:
            if not isinstance(chat, Channel):
                continue
            if getattr(chat, 'megagroup', False):
                continue
            if getattr(chat, 'left', False):
                continue
            channels.append(chat)

        print(f"{len(channels)} canaux trouves\n")

        if not channels:
            print("Aucun canal trouve. Vous etes peut-etre seulement dans des groupes.")
            return

        # 2. Analyser chaque canal
        one_week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        all_results = []

        for idx, chat in enumerate(channels):
            title = chat.title
            username = chat.username or f"id_{chat.id}"
            members = getattr(chat, 'participants_count', 0) or 0

            print(f"[{idx+1}/{len(channels)}] {title} (@{username})...", end=" ")

            try:
                # Recuperer les messages de la derniere semaine
                messages = []
                async for msg in client.iter_messages(chat, offset_date=one_week_ago, limit=500):
                    if msg.text:
                        messages.append({
                            'text': msg.text,
                            'date': msg.date,
                            'id': msg.id
                        })

                if not messages:
                    print(f"0 messages cette semaine")
                    all_results.append({
                        'title': title,
                        'username': username,
                        'members': members,
                        'total_messages': 0,
                        'signals': 0,
                        'buy': 0,
                        'sell': 0,
                        'avg_quality': 0,
                        'sample_signals': [],
                    })
                    continue

                # Analyser les signaux
                signals_found = []
                for msg in messages:
                    text = msg['text']
                    if is_signal_message(text):
                        data = extract_signal_data(text, msg['date'])
                        quality = calculate_signal_quality(data) if data else 0
                        signals_found.append({
                            'type': detect_signal_type(text),
                            'markets': detect_markets(text),
                            'quality': quality,
                            'entry': data.get('entry_price') if data else None,
                            'tp': data.get('target_price') if data else None,
                            'sl': data.get('stop_loss') if data else None,
                            'preview': text[:120].replace('\n', ' '),
                        })

                buy_count = sum(1 for s in signals_found if s['type'] == 'buy')
                sell_count = sum(1 for s in signals_found if s['type'] == 'sell')
                avg_q = sum(s['quality'] for s in signals_found) / len(signals_found) if signals_found else 0

                print(f"{len(messages)} msg, {len(signals_found)} signaux")

                all_results.append({
                    'title': title,
                    'username': username,
                    'members': members,
                    'total_messages': len(messages),
                    'signals': len(signals_found),
                    'buy': buy_count,
                    'sell': sell_count,
                    'avg_quality': round(avg_q, 1),
                    'sample_signals': signals_found[:3],
                })

            except Exception as e:
                print(f"ERREUR: {e}")
                all_results.append({
                    'title': title,
                    'username': username,
                    'members': members,
                    'total_messages': 0,
                    'signals': 0,
                    'buy': 0,
                    'sell': 0,
                    'avg_quality': 0,
                    'sample_signals': [],
                    'error': str(e),
                })

            # Petit delai pour eviter le rate limit
            await asyncio.sleep(0.5)

        # 3. Afficher le rapport complet
        print(f"\n\n{'='*70}")
        print(f"RAPPORT COMPLET - {len(all_results)} CANAUX ANALYSES")
        print(f"{'='*70}\n")

        # Trier par nombre de signaux (decroissant)
        all_results.sort(key=lambda x: x['signals'], reverse=True)

        # Tableau resume
        print(f"{'Canal':<40} {'Msgs':>5} {'Signaux':>8} {'BUY':>5} {'SELL':>5} {'Qual':>5}")
        print(f"{'-'*40} {'-'*5} {'-'*8} {'-'*5} {'-'*5} {'-'*5}")

        for r in all_results:
            title_short = r['title'][:38]
            print(f"{title_short:<40} {r['total_messages']:>5} {r['signals']:>8} {r['buy']:>5} {r['sell']:>5} {r['avg_quality']:>5}")

        # Details des canaux avec signaux
        channels_with_signals = [r for r in all_results if r['signals'] > 0]
        if channels_with_signals:
            print(f"\n\n{'='*70}")
            print(f"DETAILS DES {len(channels_with_signals)} CANAUX AVEC SIGNAUX")
            print(f"{'='*70}")

            for r in channels_with_signals:
                print(f"\n--- {r['title']} (@{r['username']}) ---")
                print(f"    Membres: {r['members']} | Messages: {r['total_messages']} | Signaux: {r['signals']} ({r['buy']} BUY / {r['sell']} SELL)")
                print(f"    Qualite moyenne: {r['avg_quality']}/10")
                if r.get('sample_signals'):
                    print(f"    Exemples de signaux:")
                    for s in r['sample_signals']:
                        print(f"      [{s['type'].upper()}] {s['markets']} | Q={s['quality']}/10 | {s['preview'][:80]}...")
        else:
            print(f"\nAUCUN CANAL N'A PRODUIT DE SIGNAUX DETECTES.")
            print(f"Verifiez si vos canaux postent des signaux en texte ou en images.")

        # Statistiques globales
        total_msgs = sum(r['total_messages'] for r in all_results)
        total_signals = sum(r['signals'] for r in all_results)
        print(f"\n\n{'='*70}")
        print(f"STATISTIQUES GLOBALES")
        print(f"{'='*70}")
        print(f"Canaux analyses:     {len(all_results)}")
        print(f"Total messages:      {total_msgs}")
        print(f"Total signaux:       {total_signals}")
        print(f"Canaux avec signaux: {len(channels_with_signals)}")
        if total_msgs > 0:
            print(f"Taux global:         {(total_signals/total_msgs*100):.1f}%")


if __name__ == "__main__":
    asyncio.run(scan_all_channels())

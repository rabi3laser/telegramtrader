"""
MODULE DE RECHERCHE TELEGRAM POUR STREAMLIT
Recherche de canaux Telegram par marché avec Telethon
VERSION UNIVERSELLE - Compatible SaaS multi-utilisateurs
"""
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.contacts import SearchRequest
from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.types import Channel, InputPeerEmpty
from datetime import datetime, timedelta
import streamlit as st

# Mots-clés enrichis par marché (multi-langues, multi-noms)
MARKET_KEYWORDS = {
    "gold_mgc": [
        # Anglais
        "gold", "gold signals", "XAUUSD", "XAU", "xau/usd", "MGC", "GC futures",
        "gold trading", "gold forex", "gold pips", "forex gold", "gold analysis",
        "free gold signals", "gold trade", "comex gold", "gold futures",
        # Français
        "or", "or signals", "or trading", "or forex", "lingot", "analyse or",
        "signaux or", "trading or", "or xauusd"
    ],
    "mnq_nasdaq": [
        # Anglais
        "nasdaq", "nasdaq signals", "NQ", "MNQ", "nasdaq 100", "nasdaq futures",
        "nasdaq trading", "NQ signals", "NQ futures", "tech futures", "QQQ",
        "nasdaq analysis", "nasdaq forex", "nasdaq pips", "micro nasdaq",
        "nasdaq index", "tech index", "nasdaq 100 signals", "NQ trading",
        # Français
        "nasdaq signaux", "indices tech", "nasdaq trading"
    ],
    "mcl_crude": [
        # Anglais
        "crude", "crude oil", "oil", "WTI", "MCL", "CL futures", "crude futures",
        "oil signals", "crude signals", "oil trading", "crude trading",
        "crude oil signals", "crude oil forex", "oil analysis", "crude analysis",
        "petroleum signals", "energy trading", "brent", "gas oil",
        # Français
        "pétrole", "petrole", "pétrole brut", "signaux pétrole", "trading pétrole"
    ],
    "mes_sp500": [
        # Anglais
        "s&p", "sp500", "spx", "MES", "ES", "ES futures", "s&p 500", "sp 500",
        "s&p signals", "sp500 signals", "ES signals", "ES trading", "micro sp500",
        "sp500 trading", "s&p forex", "spy signals", "indices", "index futures",
        "wall street signals", "market indices", "s&p 500 futures",
        # Français
        "sp500 signaux", "indices américains", "wall street"
    ]
}

# Critères de filtrage - RELÂCHÉS pour plus de résultats
MIN_MEMBERS = 100  # Réduit de 1000 à 100
MAX_MEMBERS = 1000000  # Augmenté de 50000 à 1000000


# Fonction helper pour Streamlit - Compatible avec st.secrets
async def search_telegram_channels(market: str, max_results: int = 20) -> list:
    """
    Fonction helper pour rechercher des canaux depuis Streamlit
    VERSION UNIVERSELLE - Utilise la session de l'utilisateur connecté
    
    Args:
        market: Marché à rechercher (gold_mgc, mnq_nasdaq, etc.)
        max_results: Nombre de résultats
        
    Returns:
        Liste de canaux trouvés
    """
    # Vérifier que l'utilisateur est connecté (nouvelle variable tg_session)
    if not st.session_state.get('tg_session'):
        raise ValueError("⚠️ Veuillez d'abord vous connecter à Telegram (Étape 0)")
    
    # Utiliser les credentials de l'application (st.secrets) + session utilisateur
    try:
        api_id = int(st.secrets["telegram"]["api_id"])
        api_hash = st.secrets["telegram"]["api_hash"]
    except (KeyError, AttributeError):
        api_id = int(st.secrets.get("TELEGRAM_API_ID", 0))
        api_hash = st.secrets.get("TELEGRAM_API_HASH", "")
    
    session_string = st.session_state.tg_session
    
    print(f"✅ Utilisation de la session utilisateur (SaaS mode)")
    
    if market not in MARKET_KEYWORDS:
        raise ValueError(f"Marché inconnu: {market}")
    
    keywords = MARKET_KEYWORDS[market]
    found_channels = {}
    total_searched = 0
    
    print(f"🔍 Recherche pour marché: {market}")
    print(f"📋 {len(keywords)} mots-clés à tester")
    print(f"🎯 Critères: MIN={MIN_MEMBERS}, MAX={MAX_MEMBERS}")
    
    async with TelegramClient(StringSession(session_string), api_id, api_hash) as client:
        print(f"✅ Connecté à Telegram")
        
        for idx, keyword in enumerate(keywords, 1):
            if len(found_channels) >= max_results:
                break
            
            try:
                print(f"🔎 [{idx}/{len(keywords)}] Recherche: '{keyword}'")
                result = await client(SearchRequest(q=keyword, limit=20))
                total_searched += len(result.chats)
                print(f"   📊 {len(result.chats)} résultats bruts")
                
                channels_found_this_keyword = 0
                for chat in result.chats:
                    if not isinstance(chat, Channel):
                        continue
                    
                    # Accepter les canaux SANS participants_count aussi
                    members = getattr(chat, 'participants_count', 0) or 0
                    
                    # Si pas de count, on accepte quand même le canal
                    if members > 0 and (members < MIN_MEMBERS or members > MAX_MEMBERS):
                        continue
                    
                    username = chat.username or f"id_{chat.id}"
                    if username in found_channels:
                        continue
                    
                    # Estimer activité
                    activity = "Inconnu"
                    try:
                        messages = await client.get_messages(chat, limit=10)
                        if messages:
                            now = datetime.now(messages[0].date.tzinfo)
                            recent_count = sum(1 for msg in messages if (now - msg.date) < timedelta(hours=24))
                            if recent_count >= 5:
                                activity = "Très actif"
                            elif recent_count >= 2:
                                activity = "Actif"
                            elif recent_count >= 1:
                                activity = "Modéré"
                            else:
                                activity = "Faible"
                    except:
                        pass
                    
                    found_channels[username] = {
                        "username": username,
                        "title": chat.title,
                        "members": members if members > 0 else 1000,  # Valeur par défaut si inconnu
                        "description": getattr(chat, 'about', None) or "Pas de description",
                        "is_verified": getattr(chat, 'verified', False),
                        "recent_activity": activity,
                        "id": chat.id
                    }
                    channels_found_this_keyword += 1
                    
                    if len(found_channels) >= max_results:
                        break
                
                print(f"   ✅ {channels_found_this_keyword} canaux ajoutés (total: {len(found_channels)})")
                await asyncio.sleep(2)  # Délai plus long pour éviter rate limiting
                
            except Exception as e:
                print(f"   ❌ Erreur: {e}")
                continue
    
    print(f"\n📊 RÉSUMÉ:")
    print(f"   - Résultats bruts: {total_searched}")
    print(f"   - Canaux filtrés: {len(found_channels)}")
    print(f"   - Critères: MIN={MIN_MEMBERS}, MAX={MAX_MEMBERS}")
    
    return list(found_channels.values())


async def get_joined_channels() -> list:
    """
    Liste tous les canaux Telegram auxquels l'utilisateur est déjà abonné.
    Utilise GetDialogsRequest pour récupérer les dialogues.
    
    Returns:
        Liste de canaux (format identique aux résultats de recherche)
    """
    if not st.session_state.get('tg_session'):
        raise ValueError("⚠️ Veuillez d'abord vous connecter à Telegram")

    try:
        api_id = int(st.secrets["telegram"]["api_id"])
        api_hash = st.secrets["telegram"]["api_hash"]
    except (KeyError, AttributeError):
        api_id = int(st.secrets.get("TELEGRAM_API_ID", 0))
        api_hash = st.secrets.get("TELEGRAM_API_HASH", "")

    session_string = st.session_state.tg_session
    channels = []

    async with TelegramClient(StringSession(session_string), api_id, api_hash) as client:
        # Récupérer tous les dialogues (conversations, groupes, canaux)
        result = await client(GetDialogsRequest(
            offset_date=None,
            offset_id=0,
            offset_peer=InputPeerEmpty(),
            limit=200,
            hash=0
        ))

        for chat in result.chats:
            # Filtrer uniquement les canaux (pas les groupes/megagroups)
            if not isinstance(chat, Channel):
                continue
            if getattr(chat, 'megagroup', False):
                continue  # Exclure les supergroups
            if getattr(chat, 'left', False):
                continue  # Exclure les canaux quittés

            username = chat.username or f"id_{chat.id}"
            members = getattr(chat, 'participants_count', 0) or 0

            channels.append({
                "username": username,
                "title": chat.title,
                "members": members,
                "description": getattr(chat, 'about', None) or "",
                "is_verified": getattr(chat, 'verified', False),
                "recent_activity": "Inconnu",
                "id": chat.id,
                "is_joined": True,  # Marqueur : canal déjà rejoint
            })

    print(f"✅ {len(channels)} canaux trouvés dans vos abonnements")
    return channels


async def search_custom_market(keywords: list, max_results: int = 20) -> list:
    """
    Recherche libre avec mots-clés personnalisés
    VERSION UNIVERSELLE - Utilise la session de l'utilisateur connecté
    
    Args:
        keywords: Liste de mots-clés à rechercher
        max_results: Nombre maximum de résultats
        
    Returns:
        Liste de canaux trouvés
    """
    # Vérifier que l'utilisateur est connecté (nouvelle variable tg_session)
    if not st.session_state.get('tg_session'):
        raise ValueError("⚠️ Veuillez d'abord vous connecter à Telegram (Étape 0)")
    
    # Utiliser les credentials de l'application (st.secrets) + session utilisateur
    try:
        api_id = int(st.secrets["telegram"]["api_id"])
        api_hash = st.secrets["telegram"]["api_hash"]
    except (KeyError, AttributeError):
        api_id = int(st.secrets.get("TELEGRAM_API_ID", 0))
        api_hash = st.secrets.get("TELEGRAM_API_HASH", "")
    
    session_string = st.session_state.tg_session
    
    found_channels = {}
    
    async with TelegramClient(StringSession(session_string), api_id, api_hash) as client:
        for keyword in keywords:
            if len(found_channels) >= max_results:
                break
            
            try:
                result = await client(SearchRequest(q=keyword, limit=20))
                
                for chat in result.chats:
                    if not isinstance(chat, Channel):
                        continue
                    
                    members = getattr(chat, 'participants_count', 0) or 0
                    
                    if members > 0 and (members < MIN_MEMBERS or members > MAX_MEMBERS):
                        continue
                    
                    username = chat.username or f"id_{chat.id}"
                    if username in found_channels:
                        continue
                    
                    # Estimer activité
                    activity = "Inconnu"
                    try:
                        messages = await client.get_messages(chat, limit=10)
                        if messages:
                            now = datetime.now(messages[0].date.tzinfo)
                            recent_count = sum(1 for msg in messages if (now - msg.date) < timedelta(hours=24))
                            if recent_count >= 5:
                                activity = "Très actif"
                            elif recent_count >= 2:
                                activity = "Actif"
                            elif recent_count >= 1:
                                activity = "Modéré"
                            else:
                                activity = "Faible"
                    except:
                        pass
                    
                    found_channels[username] = {
                        "username": username,
                        "title": chat.title,
                        "members": members if members > 0 else 1000,
                        "description": getattr(chat, 'about', None) or "Pas de description",
                        "is_verified": getattr(chat, 'verified', False),
                        "recent_activity": activity,
                        "id": chat.id
                    }
                    
                    if len(found_channels) >= max_results:
                        break
                
                await asyncio.sleep(2)
                
            except Exception as e:
                print(f"Erreur recherche '{keyword}': {e}")
                continue
    
    return list(found_channels.values())

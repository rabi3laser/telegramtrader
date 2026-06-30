"""
MODULE DE CALIBRATION RÉELLE DES CANAUX TELEGRAM
Analyse les canaux Telegram pour déterminer leur qualité
VERSION UNIVERSELLE SaaS - Rejoindre les canaux avant calibration
"""
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.errors import ChannelPrivateError, InviteRequestSentError
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import streamlit as st
from signal_detector import analyze_messages


# Critères de décision pour la calibration
CALIBRATION_CRITERIA = {
    'activated': {
        'min_signals': 15,
        'min_signals_per_day': 1.5,
        'min_quality': 6.0,
        'max_hours_since_last': 12,
        'min_score': 70
    },
    'short_test': {
        'min_signals': 8,
        'min_signals_per_day': 0.8,
        'min_quality': 4.0,
        'max_hours_since_last': 48,
        'min_score': 50
    },
    # Tout ce qui est en dessous est rejeté
}


def _resolve_channel_entity(channel_info: Dict):
    """
    Résout l'identifiant du canal pour Telethon.
    
    Gère 3 cas :
    - username réel : "channelname" → utilisé tel quel
    - ID numérique préfixé : "id_1804350972" → int(1804350972)
    - ID numérique direct dans channel_id : int
    
    Returns:
        str ou int utilisable par client.iter_messages()
    """
    username = channel_info.get('username', '')
    channel_id = channel_info.get('channel_id') or channel_info.get('id')
    
    # Cas 1 : username de la forme "id_XXXXXXX" → ID numérique
    if username and username.startswith('id_'):
        try:
            return int(username[3:])
        except ValueError:
            pass
    
    # Cas 2 : channel_id numérique disponible
    if channel_id:
        try:
            cid = int(str(channel_id).replace('-100', '').replace('-', ''))
            return cid
        except ValueError:
            pass
    
    # Cas 3 : username réel (sans @)
    if username:
        return username.lstrip('@')
    
    return None


async def calibrate_channel(client: TelegramClient, channel_info: Dict, config: Dict = None) -> Dict:
    """
    Calibration RÉELLE d'un canal Telegram
    
    Args:
        client: Client Telegram connecté
        channel_info: Informations du canal (username, title, etc.)
        config: Configuration optionnelle
        
    Returns:
        Résultat de la calibration avec statut et métriques
    """
    entity = _resolve_channel_entity(channel_info)
    username = channel_info.get('username', str(entity) if entity else '')
    
    if not entity:
        return {
            'status': 'rejected',
            'reason': 'Identifiant de canal invalide (pas de username ni d\'ID)',
            'score': 0
        }
    
    # Configuration par défaut
    if config is None:
        config = {
            'max_messages': 200,
            'min_messages': 50
        }
    
    try:
        # 1. Récupérer les messages du canal
        display_name = f"@{username}" if not str(entity).lstrip('-').isdigit() else f"ID:{entity}"
        print(f"📥 Récupération des messages de {display_name}...")
        messages = []
        async for message in client.iter_messages(entity, limit=config['max_messages']):
            if message.text:
                messages.append({
                    'text': message.text,
                    'date': message.date,
                    'id': message.id
                })
        
        print(f"   ✅ {len(messages)} messages récupérés")
        
        # Vérifier qu'on a assez de messages
        if len(messages) < config['min_messages']:
            return {
                'status': 'rejected',
                'reason': f'Pas assez de messages ({len(messages)} < {config["min_messages"]})',
                'score': 0,
                'metrics': {
                    'total_messages': len(messages),
                    'total_signals': 0
                }
            }
        
        # 2. Analyser les messages pour détecter les signaux
        print(f"🔍 Analyse des signaux...")
        analysis = analyze_messages(messages)
        
        print(f"   📊 {analysis['total_signals']} signaux détectés")
        print(f"   📈 Qualité moyenne: {analysis['avg_quality']}/10")
        print(f"   🎯 Marchés: {', '.join(analysis['markets_covered']) if analysis['markets_covered'] else 'Aucun'}")
        
        # 3. Calculer les métriques temporelles
        if analysis['total_signals'] > 0 and analysis['signals']:
            # Trouver le dernier signal
            latest_signal = max(analysis['signals'], key=lambda s: s['date'])
            hours_since_last = (datetime.now(latest_signal['date'].tzinfo) - latest_signal['date']).total_seconds() / 3600
            
            # Calculer la période couverte
            oldest_signal = min(analysis['signals'], key=lambda s: s['date'])
            days_covered = (latest_signal['date'] - oldest_signal['date']).total_seconds() / 86400
            days_covered = max(days_covered, 1)  # Au moins 1 jour
            
            signals_per_day = analysis['total_signals'] / days_covered
        else:
            hours_since_last = 999
            signals_per_day = 0
        
        # 4. Calculer le score global (0-100)
        score = calculate_calibration_score(
            total_signals=analysis['total_signals'],
            signals_per_day=signals_per_day,
            avg_quality=analysis['avg_quality'],
            hours_since_last=hours_since_last,
            markets_count=len(analysis['markets_covered']),
            members=channel_info.get('members', 0)
        )
        
        # 5. Déterminer le statut basé sur les critères
        status = determine_status(
            total_signals=analysis['total_signals'],
            signals_per_day=signals_per_day,
            avg_quality=analysis['avg_quality'],
            hours_since_last=hours_since_last,
            score=score
        )
        
        # 6. Préparer le résultat
        result = {
            'status': status,
            'score': round(score, 1),
            'metrics': {
                'total_messages': len(messages),
                'total_signals': analysis['total_signals'],
                'signals_per_day': round(signals_per_day, 2),
                'avg_quality': analysis['avg_quality'],
                'hours_since_last_signal': round(hours_since_last, 1),
                'markets_covered': analysis['markets_covered'],
                'buy_signals': analysis['buy_signals'],
                'sell_signals': analysis['sell_signals'],
                'signal_rate': analysis['signal_rate']
            },
            'signals_sample': analysis['signals'][:5] if analysis['signals'] else []  # 5 premiers signaux
        }
        
        # Ajouter une raison si rejeté
        if status == 'rejected':
            result['reason'] = get_rejection_reason(
                analysis['total_signals'],
                signals_per_day,
                analysis['avg_quality'],
                hours_since_last
            )
        
        print(f"   🎯 Statut: {status.upper()} (score: {score}/100)")
        
        return result
        
    except Exception as e:
        print(f"   ❌ Erreur lors de la calibration: {e}")
        return {
            'status': 'rejected',
            'reason': f'Erreur: {str(e)}',
            'score': 0,
            'metrics': {}
        }


def calculate_calibration_score(
    total_signals: int,
    signals_per_day: float,
    avg_quality: float,
    hours_since_last: float,
    markets_count: int,
    members: int
) -> float:
    """
    Calcule un score de calibration (0-100)
    
    Pondération:
    - Nombre de signaux: 30%
    - Fréquence (signaux/jour): 25%
    - Qualité moyenne: 20%
    - Récence du dernier signal: 15%
    - Diversité des marchés: 5%
    - Nombre de membres: 5%
    """
    score = 0.0
    
    # 1. Nombre de signaux (0-30 points)
    if total_signals >= 30:
        score += 30
    elif total_signals >= 20:
        score += 25
    elif total_signals >= 15:
        score += 20
    elif total_signals >= 10:
        score += 15
    elif total_signals >= 5:
        score += 10
    else:
        score += total_signals * 2
    
    # 2. Fréquence (0-25 points)
    if signals_per_day >= 3:
        score += 25
    elif signals_per_day >= 2:
        score += 20
    elif signals_per_day >= 1.5:
        score += 15
    elif signals_per_day >= 1:
        score += 10
    elif signals_per_day >= 0.5:
        score += 5
    else:
        score += signals_per_day * 10
    
    # 3. Qualité moyenne (0-20 points)
    score += (avg_quality / 10) * 20
    
    # 4. Récence (0-15 points)
    if hours_since_last <= 6:
        score += 15
    elif hours_since_last <= 12:
        score += 12
    elif hours_since_last <= 24:
        score += 8
    elif hours_since_last <= 48:
        score += 4
    else:
        score += max(0, 4 - (hours_since_last - 48) / 24)
    
    # 5. Diversité des marchés (0-5 points)
    score += min(markets_count * 2, 5)
    
    # 6. Nombre de membres (0-5 points)
    if members >= 5000:
        score += 5
    elif members >= 2000:
        score += 4
    elif members >= 1000:
        score += 3
    elif members >= 500:
        score += 2
    elif members >= 100:
        score += 1
    
    return min(score, 100.0)


def determine_status(
    total_signals: int,
    signals_per_day: float,
    avg_quality: float,
    hours_since_last: float,
    score: float
) -> str:
    """
    Détermine le statut du canal basé principalement sur le score global.
    Le score (0-100) intègre déjà tous les critères pondérés.
    
    Returns:
        'activated', 'short_test', ou 'rejected'
    """
    # Critères minimaux absolus (éliminatoires)
    if total_signals < CALIBRATION_CRITERIA['short_test']['min_signals']:
        return 'rejected'
    if avg_quality < CALIBRATION_CRITERIA['short_test']['min_quality']:
        return 'rejected'
    
    # Décision basée sur le score global
    if score >= CALIBRATION_CRITERIA['activated']['min_score']:
        return 'activated'
    elif score >= CALIBRATION_CRITERIA['short_test']['min_score']:
        return 'short_test'
    else:
        return 'rejected'


def get_rejection_reason(
    total_signals: int,
    signals_per_day: float,
    avg_quality: float,
    hours_since_last: float
) -> str:
    """
    Génère une raison de rejet claire
    """
    reasons = []
    
    if total_signals < CALIBRATION_CRITERIA['short_test']['min_signals']:
        reasons.append(f"Trop peu de signaux ({total_signals} < {CALIBRATION_CRITERIA['short_test']['min_signals']})")
    
    if signals_per_day < CALIBRATION_CRITERIA['short_test']['min_signals_per_day']:
        reasons.append(f"Fréquence trop faible ({signals_per_day:.1f} < {CALIBRATION_CRITERIA['short_test']['min_signals_per_day']} signaux/jour)")
    
    if avg_quality < CALIBRATION_CRITERIA['short_test']['min_quality']:
        reasons.append(f"Qualité insuffisante ({avg_quality:.1f}/10 < {CALIBRATION_CRITERIA['short_test']['min_quality']}/10)")
    
    if hours_since_last > CALIBRATION_CRITERIA['short_test']['max_hours_since_last']:
        reasons.append(f"Dernier signal trop ancien ({hours_since_last:.0f}h > {CALIBRATION_CRITERIA['short_test']['max_hours_since_last']}h)")
    
    if not reasons:
        reasons.append("Score global insuffisant")
    
    return " | ".join(reasons)


async def join_channel(client: TelegramClient, username: str) -> Tuple[bool, str]:
    """
    Rejoint un canal Telegram avant de le calibrer
    
    Args:
        client: Client Telegram connecté
        username: Username du canal (sans @)
        
    Returns:
        (success, message)
    """
    try:
        # Nettoyer le username
        clean_username = username.replace('@', '')
        
        # Essayer de rejoindre le canal
        await client(JoinChannelRequest(clean_username))
        return True, f"✅ Rejoint @{clean_username}"
        
    except ChannelPrivateError:
        return False, f"🔒 Canal privé - Nécessite un lien d'invitation"
    except InviteRequestSentError:
        return False, f"📨 Demande d'adhésion envoyée - En attente d'approbation"
    except Exception as e:
        error_str = str(e).lower()
        if "already" in error_str or "participant" in error_str:
            # Déjà membre
            return True, f"✅ Déjà membre de @{clean_username}"
        else:
            return False, f"❌ Erreur: {str(e)}"


async def calibrate_channels_batch(
    channels: List[Dict],
    config: Dict = None,
    on_channel_done=None,
    skip_usernames: set = None
) -> Dict:
    """
    Calibre plusieurs canaux en batch avec sauvegarde progressive.
    VERSION UNIVERSELLE - Utilise la session de l'utilisateur connecté
    
    Args:
        channels: Liste de canaux à calibrer
        config: Configuration optionnelle
        on_channel_done: Callback appelé après chaque canal (channel_result: dict)
        skip_usernames: Set de usernames déjà calibrés à ignorer
        
    Returns:
        Résultats groupés par statut
    """
    # Vérifier que l'utilisateur est connecté (nouvelle variable tg_session)
    if not st.session_state.get('tg_session'):
        raise ValueError("⚠️ Veuillez d'abord vous connecter à Telegram")
    
    # Utiliser les credentials de l'application (st.secrets) + session utilisateur
    try:
        api_id = int(st.secrets["telegram"]["api_id"])
        api_hash = st.secrets["telegram"]["api_hash"]
    except (KeyError, AttributeError):
        api_id = int(st.secrets.get("TELEGRAM_API_ID", 0))
        api_hash = st.secrets.get("TELEGRAM_API_HASH", "")
    
    session_string = st.session_state.tg_session
    skip_usernames = skip_usernames or set()
    
    print(f"✅ Utilisation de la session utilisateur (SaaS mode)")
    
    results = {
        'activated': [],
        'short_test': [],
        'rejected': []
    }
    
    async with TelegramClient(StringSession(session_string), api_id, api_hash) as client:
        for channel in channels:
            username = channel.get('username', '')
            
            # Skip les canaux déjà calibrés
            if username in skip_usernames:
                print(f"⏭️ Skip (déjà calibré): @{username}")
                continue
            
            print(f"\n{'='*60}")
            print(f"📡 Calibration: {channel['title']} (@{username})")
            print(f"{'='*60}")
            
            result = await calibrate_channel(client, channel, config)
            
            # Enrichir avec winrate et signals_count
            metrics = result.get('metrics', {})
            result['winrate'] = int(result.get('score', 0))
            result['signals_count'] = metrics.get('total_signals', 0)
            result['date_calibration'] = datetime.now().isoformat()
            
            # Ajouter les infos du canal au résultat
            channel_result = {**channel, **result}
            
            # Classer par statut
            status = result['status']
            results[status].append(channel_result)
            
            # Callback de sauvegarde progressive (appelé immédiatement)
            if on_channel_done:
                on_channel_done(channel_result)
            
            # Petit délai entre les canaux
            await asyncio.sleep(1)
    
    return results

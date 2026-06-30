"""
MODULE DE DÉTECTION DE SIGNAUX TRADING
Détecte et extrait les signaux de trading depuis les messages Telegram
VERSION RÉELLE - Pas de simulation
"""
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# Patterns de détection de signaux (multi-langues)
SIGNAL_PATTERNS = {
    'buy': [
        r'\b(BUY|ACHETER|LONG|CALL|UP)\b',
        r'🟢',
        r'✅',
        r'\b(GOLD|XAU|NASDAQ|NQ|CRUDE|OIL|SP500|ES).*?(BUY|LONG|UP)\b',
    ],
    'sell': [
        r'\b(SELL|VENDRE|SHORT|PUT|DOWN)\b',
        r'🔴',
        r'❌',
        r'\b(GOLD|XAU|NASDAQ|NQ|CRUDE|OIL|SP500|ES).*?(SELL|SHORT|DOWN)\b',
    ],
    'targets': [
        r'(TP|TARGET|OBJ|OBJECTIF)\s*:?\s*(\d+\.?\d*)',
        r'(TP|TARGET)\s*(\d+)',
    ],
    'stop_loss': [
        r'(SL|STOP\s*LOSS|STOP)\s*:?\s*(\d+\.?\d*)',
    ],
    'entry': [
        r'(ENTRY|ENTRÉE|PRICE|PRIX|@)\s*:?\s*(\d+\.?\d*)',
        r'(BUY|SELL).*?(@|AT|À)\s*(\d+\.?\d*)',
    ],
}

# Patterns pour détecter les marchés
MARKET_PATTERNS = {
    'gold': [r'\b(GOLD|XAU|XAUUSD|OR|GC|MGC)\b'],
    'nasdaq': [r'\b(NASDAQ|NQ|MNQ|TECH|QQQ)\b'],
    'crude': [r'\b(CRUDE|OIL|WTI|CL|MCL|PÉTROLE|PETROLE)\b'],
    'sp500': [r'\b(SP500|SPX|ES|MES|S&P)\b'],
    'forex': [r'\b(EUR|USD|GBP|JPY|CHF|AUD|CAD|NZD)\b'],
    'crypto': [r'\b(BTC|ETH|BITCOIN|ETHEREUM|CRYPTO)\b'],
}


def detect_signal_type(text: str) -> Optional[str]:
    """
    Détecte le type de signal (BUY ou SELL)
    
    Args:
        text: Texte du message
        
    Returns:
        'buy', 'sell', ou None
    """
    text_upper = text.upper()
    
    # Compter les matches pour BUY
    buy_count = 0
    for pattern in SIGNAL_PATTERNS['buy']:
        if re.search(pattern, text_upper, re.IGNORECASE):
            buy_count += 1
    
    # Compter les matches pour SELL
    sell_count = 0
    for pattern in SIGNAL_PATTERNS['sell']:
        if re.search(pattern, text_upper, re.IGNORECASE):
            sell_count += 1
    
    # Décision basée sur le nombre de matches
    if buy_count > sell_count and buy_count > 0:
        return 'buy'
    elif sell_count > buy_count and sell_count > 0:
        return 'sell'
    
    return None


def extract_price(text: str, pattern_type: str = 'entry') -> Optional[float]:
    """
    Extrait un prix depuis le texte
    
    Args:
        text: Texte du message
        pattern_type: Type de prix ('entry', 'targets', 'stop_loss')
        
    Returns:
        Prix extrait ou None
    """
    patterns = SIGNAL_PATTERNS.get(pattern_type, [])
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            # Extraire le nombre (dernier groupe capturé)
            groups = match.groups()
            for group in reversed(groups):
                if group and re.match(r'\d+\.?\d*', group):
                    try:
                        return float(group)
                    except ValueError:
                        continue
    
    return None


def detect_markets(text: str) -> List[str]:
    """
    Détecte les marchés mentionnés dans le texte
    
    Args:
        text: Texte du message
        
    Returns:
        Liste des marchés détectés
    """
    detected = []
    text_upper = text.upper()
    
    for market, patterns in MARKET_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text_upper):
                detected.append(market)
                break
    
    return detected


def is_signal_message(text: str) -> bool:
    """
    Détermine si un message contient un signal de trading
    
    Args:
        text: Texte du message
        
    Returns:
        True si c'est un signal, False sinon
    """
    if not text or len(text) < 10:
        return False
    
    # Doit avoir un type de signal (BUY ou SELL)
    signal_type = detect_signal_type(text)
    if not signal_type:
        return False
    
    # Doit mentionner un marché
    markets = detect_markets(text)
    if not markets:
        return False
    
    # Bonus : a un prix ou target
    has_price = extract_price(text, 'entry') is not None
    has_target = extract_price(text, 'targets') is not None
    
    return has_price or has_target


def extract_signal_data(text: str, message_date: datetime = None) -> Optional[Dict]:
    """
    Extrait toutes les données d'un signal
    
    Args:
        text: Texte du message
        message_date: Date du message
        
    Returns:
        Dictionnaire avec les données du signal ou None
    """
    if not is_signal_message(text):
        return None
    
    signal_type = detect_signal_type(text)
    markets = detect_markets(text)
    entry_price = extract_price(text, 'entry')
    target_price = extract_price(text, 'targets')
    stop_loss = extract_price(text, 'stop_loss')
    
    return {
        'type': signal_type,
        'markets': markets,
        'entry_price': entry_price,
        'target_price': target_price,
        'stop_loss': stop_loss,
        'date': message_date or datetime.now(),
        'raw_text': text[:200],  # Premiers 200 caractères
        'has_complete_data': all([signal_type, markets, entry_price or target_price])
    }


def calculate_signal_quality(signal_data: Dict) -> float:
    """
    Calcule un score de qualité pour un signal (0-10)
    
    Args:
        signal_data: Données du signal
        
    Returns:
        Score de qualité (0-10)
    """
    score = 0.0
    
    # Type de signal défini (+2)
    if signal_data.get('type'):
        score += 2.0
    
    # Marché identifié (+2)
    if signal_data.get('markets'):
        score += 2.0
    
    # Prix d'entrée (+2)
    if signal_data.get('entry_price'):
        score += 2.0
    
    # Target défini (+2)
    if signal_data.get('target_price'):
        score += 2.0
    
    # Stop-loss défini (+2)
    if signal_data.get('stop_loss'):
        score += 2.0
    
    return min(score, 10.0)


def analyze_messages(messages: List[Dict]) -> Dict:
    """
    Analyse une liste de messages et extrait les statistiques
    
    Args:
        messages: Liste de messages avec 'text' et 'date'
        
    Returns:
        Statistiques sur les signaux détectés
    """
    signals = []
    total_messages = len(messages)
    
    for msg in messages:
        text = msg.get('text', '')
        date = msg.get('date')
        
        signal_data = extract_signal_data(text, date)
        if signal_data:
            signal_data['quality_score'] = calculate_signal_quality(signal_data)
            signals.append(signal_data)
    
    # Calculer les statistiques
    if not signals:
        return {
            'total_signals': 0,
            'signal_rate': 0.0,
            'avg_quality': 0.0,
            'markets_covered': [],
            'buy_signals': 0,
            'sell_signals': 0,
            'signals': []
        }
    
    # Compter par type
    buy_count = sum(1 for s in signals if s['type'] == 'buy')
    sell_count = sum(1 for s in signals if s['type'] == 'sell')
    
    # Marchés couverts
    all_markets = []
    for s in signals:
        all_markets.extend(s.get('markets', []))
    markets_covered = list(set(all_markets))
    
    # Qualité moyenne
    avg_quality = sum(s['quality_score'] for s in signals) / len(signals)
    
    # Taux de signaux
    signal_rate = (len(signals) / total_messages * 100) if total_messages > 0 else 0
    
    return {
        'total_signals': len(signals),
        'signal_rate': round(signal_rate, 2),
        'avg_quality': round(avg_quality, 2),
        'markets_covered': markets_covered,
        'buy_signals': buy_count,
        'sell_signals': sell_count,
        'signals': signals
    }

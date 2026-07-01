"""
MODULE DE CALCUL DU VRAI WINRATE - API TWELVE DATA
Compare les signaux Telegram extraits (entry/TP/SL/date) aux prix RÉELS
du marché pour déterminer si chaque trade aurait été gagnant ou perdant.

Fonctionne à la fois en local ET sur Streamlit Cloud (contrairement à une
intégration NinjaTrader locale, impossible à joindre depuis un serveur distant).

API gratuite : https://twelvedata.com (plan gratuit: 800 requêtes/jour, 8/min)
"""
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
import requests
import streamlit as st

TWELVE_DATA_BASE = "https://api.twelvedata.com"

# Mapping marché interne -> symbole Twelve Data
# NB: Les futures MGC/MNQ/MCL/MES ne sont pas disponibles sur le plan gratuit
# Twelve Data (données "commodities"/"futures" = payantes). On utilise donc
# des proxies liquides et fortement corrélés, disponibles gratuitement :
MARKET_SYMBOL_MAP = {
    "gold_mgc":   "XAU/USD",   # Forex spot Gold — corrélation quasi parfaite avec MGC
    "mnq_nasdaq": "QQQ",       # ETF Nasdaq-100 — proxy pour les futures MNQ
    "mcl_crude":  "USO",       # ETF Crude Oil — proxy pour les futures MCL
    "mes_sp500":  "SPY",       # ETF S&P 500 — proxy pour les futures MES
}

MAX_CANDLES_PER_REQUEST = 5000  # Limite du plan gratuit Twelve Data
INTERVAL = "15min"


def _get_api_key() -> Optional[str]:
    """Récupère la clé API Twelve Data depuis st.secrets."""
    try:
        return st.secrets["twelvedata"]["api_key"]
    except Exception:
        pass
    try:
        return st.secrets.get("TWELVE_DATA_API_KEY")
    except Exception:
        return None


def _fetch_chunk(symbol: str, start_dt: datetime, end_dt: datetime, api_key: str) -> List[Dict]:
    """Récupère un lot de bougies OHLC depuis Twelve Data (max ~52 jours en 15min)."""
    params = {
        "symbol": symbol,
        "interval": INTERVAL,
        "start_date": start_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "end_date": end_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "apikey": api_key,
        "timezone": "UTC",
        "outputsize": MAX_CANDLES_PER_REQUEST,
        "format": "JSON",
    }
    try:
        resp = requests.get(f"{TWELVE_DATA_BASE}/time_series", params=params, timeout=15)
        data = resp.json()
    except Exception:
        return []

    if not isinstance(data, dict) or data.get("status") == "error" or "values" not in data:
        return []

    candles = []
    for v in data["values"]:
        try:
            candles.append({
                "datetime": datetime.strptime(v["datetime"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc),
                "open":  float(v["open"]),
                "high":  float(v["high"]),
                "low":   float(v["low"]),
                "close": float(v["close"]),
            })
        except Exception:
            continue

    candles.sort(key=lambda c: c["datetime"])
    return candles


def fetch_ohlc_range(symbol: str, start_dt: datetime, end_dt: datetime, api_key: str) -> List[Dict]:
    """
    Récupère toutes les bougies OHLC entre start_dt et end_dt, en découpant
    automatiquement en plusieurs requêtes si la période dépasse la limite
    du plan gratuit (~52 jours en 15min).
    """
    all_candles = []
    chunk_days = 45  # Marge de sécurité sous la limite de 5000 bougies en 15min
    cursor = start_dt

    while cursor < end_dt:
        chunk_end = min(cursor + timedelta(days=chunk_days), end_dt)
        chunk = _fetch_chunk(symbol, cursor, chunk_end, api_key)
        all_candles.extend(chunk)
        cursor = chunk_end
        if cursor < end_dt:
            time.sleep(1.2)  # Respect rate limit (8 req/min plan gratuit)

    # Dédupliquer par datetime
    seen = set()
    unique = []
    for c in all_candles:
        if c["datetime"] not in seen:
            seen.add(c["datetime"])
            unique.append(c)
    unique.sort(key=lambda c: c["datetime"])
    return unique


def evaluate_signal_outcome(
    direction: str,
    entry: float,
    tp: float,
    sl: float,
    signal_date: datetime,
    candles: List[Dict],
    max_hold_hours: int = 48
) -> str:
    """
    Détermine si un signal aurait été WIN, LOSS ou UNKNOWN (indéterminé)
    en comparant TP/SL aux prix HIGH/LOW réels après le signal.
    """
    if signal_date.tzinfo is None:
        signal_date = signal_date.replace(tzinfo=timezone.utc)

    deadline = signal_date + timedelta(hours=max_hold_hours)
    relevant = [c for c in candles if signal_date <= c["datetime"] <= deadline]

    if not relevant:
        return "UNKNOWN"

    direction = (direction or "").upper()
    for c in relevant:
        if direction == "BUY":
            if c["high"] >= tp:
                return "WIN"
            if c["low"] <= sl:
                return "LOSS"
        elif direction == "SELL":
            if c["low"] <= tp:
                return "WIN"
            if c["high"] >= sl:
                return "LOSS"
        else:
            return "UNKNOWN"

    return "UNKNOWN"  # Ni TP ni SL touché dans la fenêtre de temps


def calculate_channel_real_winrate(signals: List[Dict], market: str, max_hold_hours: int = 48) -> Dict:
    """
    Calcule le VRAI winrate d'un canal en comparant ses signaux aux prix
    réels du marché (via Twelve Data) — et non plus une estimation textuelle.

    Args:
        signals: Liste de signaux extraits par signal_detector.py
                 (doivent contenir type, entry_price, target_price, stop_loss, date)
        market: Marché interne (gold_mgc, mnq_nasdaq, mcl_crude, mes_sp500)
        max_hold_hours: Durée max pour attendre que TP/SL soit touché

    Returns:
        Dict avec winrate réel, wins, losses, unknown, symbole utilisé, etc.
    """
    api_key = _get_api_key()
    if not api_key:
        return {"available": False, "reason": "Clé API Twelve Data non configurée (voir CONFIGURATION_SECRETS.md)"}

    symbol = MARKET_SYMBOL_MAP.get(market)
    if not symbol:
        return {"available": False, "reason": f"Marché non supporté pour winrate réel: {market}"}

    # Filtrer les signaux complets et exploitables (entry + TP + SL + date)
    usable = [
        s for s in (signals or [])
        if s.get("entry_price") and s.get("target_price") and s.get("stop_loss") and s.get("date")
    ]
    if not usable:
        return {"available": False, "reason": "Aucun signal avec entry+TP+SL complet pour ce canal"}

    dates = [s["date"] for s in usable]
    start_dt = min(dates) - timedelta(hours=1)
    end_dt = max(dates) + timedelta(hours=max_hold_hours + 1)

    # Normaliser timezone et ne jamais dépasser "maintenant"
    if start_dt.tzinfo is None:
        start_dt = start_dt.replace(tzinfo=timezone.utc)
    if end_dt.tzinfo is None:
        end_dt = end_dt.replace(tzinfo=timezone.utc)
    now_utc = datetime.now(timezone.utc)
    end_dt = min(end_dt, now_utc)

    if start_dt >= end_dt:
        return {"available": False, "reason": "Plage de dates invalide pour la récupération des prix"}

    candles = fetch_ohlc_range(symbol, start_dt, end_dt, api_key)
    if not candles:
        return {"available": False, "reason": f"Impossible de récupérer les prix réels pour {symbol} (API indisponible ou quota atteint)"}

    wins = losses = unknown = 0
    for s in usable:
        outcome = evaluate_signal_outcome(
            direction=s.get("type", ""),
            entry=s["entry_price"],
            tp=s["target_price"],
            sl=s["stop_loss"],
            signal_date=s["date"],
            candles=candles,
            max_hold_hours=max_hold_hours,
        )
        if outcome == "WIN":
            wins += 1
        elif outcome == "LOSS":
            losses += 1
        else:
            unknown += 1

    total_decided = wins + losses
    winrate = round((wins / total_decided) * 100, 1) if total_decided > 0 else None

    return {
        "available": True,
        "winrate": winrate,
        "wins": wins,
        "losses": losses,
        "unknown": unknown,
        "total_evaluated": len(usable),
        "symbol_used": symbol,
        "candles_fetched": len(candles),
        "max_hold_hours": max_hold_hours,
    }
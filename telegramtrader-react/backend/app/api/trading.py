"""
Routes API Trading - Exécution et gestion des trades (via CrossTrade)

Chaque utilisateur peut désormais lier SON PROPRE compte NinjaTrader 8 /
Tradovate via sa clé secrète CrossTrade personnelle (voir /trading/account),
au lieu d'utiliser uniquement la configuration serveur partagée (.env).
"""
import json
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, List

from app.services.crosstrade_service import get_crosstrade_bridge
from app.services import user_trading_config_service as user_cfg
from app.services import nt8_agent_service as agent_service
from app.api.deps import get_session_string, get_optional_session_string

router = APIRouter()

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
TRADE_HISTORY_FILE = DATA_DIR / "trade_history.json"


def _load_trade_history() -> List[Dict]:
    if not TRADE_HISTORY_FILE.exists():
        return []
    try:
        with open(TRADE_HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save_trade_entry(entry: Dict) -> None:
    history = _load_trade_history()
    history.insert(0, entry)
    history = history[:500]  # limiter la taille de l'historique
    with open(TRADE_HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2, default=str)


def _bridge_for(session_string: Optional[str]):
    """Construit un bridge CrossTrade en utilisant la config personnelle
    de l'utilisateur si elle existe, sinon la config serveur (.env)."""
    user_config = user_cfg.get_user_config(session_string) if session_string else None
    return get_crosstrade_bridge(user_config)


class SignalExecutionRequest(BaseModel):
    signal: Dict
    destination: str  # "tradovate" ou "nt8"
    account: Optional[str] = None


class ClosePositionRequest(BaseModel):
    destination: str
    account: Optional[str] = None
    market: Optional[str] = None
    quantity: Optional[int] = None


class UserTradingAccountRequest(BaseModel):
    secret_key: str
    webhook_url: Optional[str] = None
    default_destination: Optional[str] = None
    account_name: Optional[str] = None
    platform: Optional[str] = None


@router.get("/account")
async def get_trading_account(session_string: str = Depends(get_session_string)):
    """
    Récupère la configuration de liaison compte de l'utilisateur connecté
    (NinjaTrader 8 / Tradovate via CrossTrade). La clé secrète est masquée.
    """
    config = user_cfg.get_user_config(session_string)
    if not config:
        return {"linked": False}
    return {
        "linked": True,
        "secret_key_masked": user_cfg.mask_secret_key(config.get("secret_key", "")),
        "webhook_url": config.get("webhook_url"),
        "default_destination": config.get("default_destination"),
        "account_name": config.get("account_name"),
        "platform": config.get("platform"),
    }


@router.post("/account")
async def save_trading_account(
    data: UserTradingAccountRequest, session_string: str = Depends(get_session_string)
):
    """
    Lie le compte NinjaTrader 8 / Tradovate de l'utilisateur en enregistrant
    sa propre clé secrète CrossTrade personnelle (remplace la config serveur
    partagée pour cet utilisateur).
    """
    if not data.secret_key or not data.secret_key.strip():
        raise HTTPException(status_code=400, detail="La clé secrète CrossTrade est requise")

    config = user_cfg.save_user_config(
        session_string,
        secret_key=data.secret_key,
        webhook_url=data.webhook_url,
        default_destination=data.default_destination,
        account_name=data.account_name,
        platform=data.platform,
    )
    return {
        "linked": True,
        "secret_key_masked": user_cfg.mask_secret_key(config["secret_key"]),
        "webhook_url": config["webhook_url"],
        "default_destination": config["default_destination"],
        "account_name": config["account_name"],
        "platform": config["platform"],
    }


@router.delete("/account")
async def delete_trading_account(session_string: str = Depends(get_session_string)):
    """Supprime la liaison compte personnelle de l'utilisateur."""
    success = user_cfg.delete_user_config(session_string)
    return {"success": success}


@router.post("/execute")
async def execute_signal(
    data: SignalExecutionRequest, session_string: Optional[str] = Depends(get_optional_session_string)
):
    """
    Exécuter un signal de trading.

    - Pour NinjaTrader 8 : si l'utilisateur a un AGENT LOCAL lié (solution gratuite,
      sans CrossTrade), le signal est poussé dans sa file d'attente et récupéré par
      son script local au prochain polling.
    - Sinon (ou pour Tradovate) : on retombe sur le pont CrossTrade classique
      (compte personnel lié si disponible, sinon config serveur).

    IMPORTANT : si destination == "nt8" et que l'agent est lié, on n'appelle
    JAMAIS CrossTrade — même si session_string est None ou si le kill switch
    est actif (dans ce cas on retourne une erreur explicite, pas une erreur CrossTrade).
    """
    # ── Chemin NT8 via agent local ────────────────────────────────────────
    if data.destination == "nt8":
        if session_string and agent_service.is_agent_linked(session_string):
            pushed = agent_service.push_signal(session_string, data.signal)
            result = {
                "success": pushed,
                "message": (
                    "Signal envoyé à votre agent local NinjaTrader 8 (exécution dès son prochain polling)"
                    if pushed
                    else "Kill switch actif ou agent non disponible — signal non envoyé"
                ),
                "destination": data.destination,
            }
        else:
            # Agent NT8 non lié : on refuse d'appeler CrossTrade pour destination=nt8
            # (CrossTrade ne peut pas exécuter sur NT8 sans l'agent local)
            result = {
                "success": False,
                "message": (
                    "Aucun agent NinjaTrader 8 lié. Allez dans Paramètres → Agent local "
                    "pour configurer votre agent gratuit. CrossTrade n'est pas utilisé "
                    "pour la destination NT8."
                ),
                "destination": data.destination,
            }
    # ── Chemin Tradovate / CrossTrade ─────────────────────────────────────
    else:
        bridge = _bridge_for(session_string)
        result = bridge.execute_signal(data.signal, destination=data.destination, account=data.account)

    _save_trade_entry({
        "type": "execute",
        "signal": data.signal,
        "destination": data.destination,
        "account": data.account,
        "result": result,
        "timestamp": datetime.now().isoformat(),
    })

    return result


@router.get("/positions")
async def get_positions():
    """
    Récupérer les positions actives.
    NOTE: CrossTrade fonctionne en mode webhook "fire-and-forget" (pas d'API de lecture
    d'état de compte) — le suivi des positions doit se faire directement dans
    NinjaTrader 8 ou Tradovate. Cet endpoint retourne une liste vide par design.
    """
    return []


@router.post("/positions/{position_id}/close")
async def close_position(
    position_id: str, data: ClosePositionRequest, session_string: Optional[str] = Depends(get_optional_session_string)
):
    """Fermer une position via CrossTrade"""
    bridge = _bridge_for(session_string)
    market = data.market or ""
    result = bridge.close_position(
        market=market,
        account=data.account,
        destination=data.destination,
        quantity=data.quantity,
    )

    _save_trade_entry({
        "type": "close_position",
        "position_id": position_id,
        "destination": data.destination,
        "result": result,
        "timestamp": datetime.now().isoformat(),
    })

    return result


@router.post("/positions/close-all")
async def close_all_positions(
    data: ClosePositionRequest, session_string: Optional[str] = Depends(get_optional_session_string)
):
    """Fermer toutes les positions via CrossTrade (flatten)"""
    bridge = _bridge_for(session_string)
    result = bridge.flatten_all(account=data.account, destination=data.destination)

    _save_trade_entry({
        "type": "close_all",
        "destination": data.destination,
        "result": result,
        "timestamp": datetime.now().isoformat(),
    })

    return result


@router.get("/history")
async def get_trade_history(limit: int = 100):
    """Récupérer l'historique des trades exécutés"""
    return _load_trade_history()[:limit]


@router.post("/test-connection")
async def test_connection(
    data: ClosePositionRequest, session_string: Optional[str] = Depends(get_optional_session_string)
):
    """
    Tester RÉELLEMENT la connexion CrossTrade (appel réseau réel au webhook,
    avec la clé personnelle de l'utilisateur si liée, sinon la config serveur).
    """
    bridge = _bridge_for(session_string)
    return bridge.test_connection(destination=data.destination, account=data.account)

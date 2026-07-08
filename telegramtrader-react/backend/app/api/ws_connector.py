"""
WebSocket — Connecteur NT8 en temps réel.

Remplace le polling HTTP toutes les 5s par une connexion WebSocket persistante.
Le serveur push automatiquement les mises à jour dès qu'elles changent :
  - État de santé du connecteur (Backend / Agent / NinjaTrader 8)
  - Comptes & connexions NinjaTrader (sélection active, soldes)
  - Kill switch (trading suspendu ou non)
  - Files d'attente (signaux / commandes en attente)

Protocole :
  - Le client se connecte à ws://<host>/ws/connector?token=<session_token>
  - Le serveur envoie un message JSON initial complet dès la connexion
  - Puis envoie un diff (ou le payload complet) toutes les PUSH_INTERVAL_SEC
    secondes, ou immédiatement si un changement est détecté
  - Le client peut envoyer {"type": "ping"} pour maintenir la connexion vivante
  - Le serveur répond {"type": "pong"} aux pings

Format des messages serveur → client :
  {
    "type": "update",
    "health": { ... },       // ConnectorHealth
    "accounts": { ... },     // AccountsStatus
    "kill_switch": { ... },  // KillSwitchState
    "action_log": [ ... ],   // 5 dernières actions
    "ts": 1234567890.123     // timestamp serveur
  }

  ou {"type": "pong"} en réponse à un ping
  ou {"type": "error", "message": "..."} en cas d'erreur d'authentification
"""
import asyncio
import json
import time
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from fastapi.websockets import WebSocketState

from app.services import nt8_agent_service as agent_service
from app.api.deps import _decode_session_string  # helper interne

router = APIRouter()

# Intervalle de push en secondes (même si rien n'a changé, on envoie un
# heartbeat WS pour maintenir la connexion et détecter les déconnexions)
PUSH_INTERVAL_SEC = 3.0

# Nombre de secondes sans activité client avant de fermer la connexion
WS_IDLE_TIMEOUT_SEC = 120.0


def _build_payload(session_string: str) -> dict:
    """Construit le payload complet à envoyer au client WebSocket."""
    import time as _time

    status = agent_service.get_status(session_string)

    # ── Santé du connecteur ───────────────────────────────────────────────
    linked = status.get("linked", False)
    connected = status.get("connected", False)
    last_heartbeat = status.get("last_heartbeat")
    heartbeat_age_sec = None
    if last_heartbeat:
        heartbeat_age_sec = round(_time.time() - last_heartbeat, 1)

    last_price = status.get("last_price") or {}
    last_accounts = status.get("last_accounts") or {}
    nt8_active = connected and bool(last_price)

    health = {
        "backend": {"ok": True, "message": "Backend opérationnel"},
        "agent": {
            "ok": connected,
            "linked": linked,
            "connected": connected,
            "last_heartbeat_age_sec": heartbeat_age_sec,
            "message": (
                "Agent connecté ✅" if connected
                else ("Agent lié mais inactif (heartbeat expiré)" if linked else "Aucun agent lié")
            ),
        },
        "nt8": {
            "ok": nt8_active,
            "active": nt8_active,
            "selected_account": last_accounts.get("selected_account"),
            "trading_blocked": last_price.get("trading_blocked", False),
            "position_open": last_price.get("position_open", False),
            "balance": last_price.get("account_balance"),
            "daily_pnl": last_price.get("daily_pnl"),
            "message": (
                "NinjaTrader actif ✅" if nt8_active
                else ("Agent connecté, NinjaTrader non détecté" if connected else "NinjaTrader non joignable")
            ),
        },
        "queues": agent_service.get_queue_sizes(session_string),
        "overall_ok": connected and nt8_active,
    }

    # ── Comptes & connexions ──────────────────────────────────────────────
    # Si l'Add-On C# n'est pas installé, last_accounts est None.
    # On construit un accounts_status synthétique depuis last_price
    # (remonté par la stratégie V3 via nt8_current_price.json) pour
    # que le frontend affiche quand même le compte actif et le solde.
    accounts_status_payload = last_accounts if last_accounts else None

    if not accounts_status_payload and last_price:
        # Construire un accounts_status minimal depuis price_info
        # Champs écrits par la stratégie V3 : mid, daily_pnl, account_balance,
        # trading_blocked, position_open (pas d'account_name ni d'instrument)
        # Champs écrits par l'Add-On : + instrument, last_price, tick_size, point_value
        account_name = (
            last_price.get("account_name")
            or last_price.get("account")
            or status.get("account_name")  # stocké lors de la génération du token
        )
        balance = last_price.get("account_balance")
        daily_pnl = last_price.get("daily_pnl")
        instrument = last_price.get("instrument")
        # La V3 écrit "mid" (prix du close), l'Add-On écrit "last_price"
        last_px = last_price.get("last_price") or last_price.get("mid") or last_price.get("price")
        tick_size = last_price.get("tick_size")
        point_value = last_price.get("point_value")

        synthetic: dict = {}
        if account_name:
            synthetic["selected_account"] = account_name
            acc_entry: dict = {"name": account_name}
            if balance is not None:
                acc_entry["balance"] = balance
            if daily_pnl is not None:
                acc_entry["daily_pnl"] = daily_pnl
            synthetic["accounts"] = [acc_entry]

        if instrument:
            synthetic["instruments"] = [instrument]
            ai: dict = {"name": instrument}
            if tick_size is not None:
                ai["tick_size"] = tick_size
            if point_value is not None:
                ai["point_value"] = point_value
            if last_px is not None:
                ai["last_price"] = last_px
            synthetic["active_instrument"] = ai

        if synthetic:
            synthetic["_source"] = "price_info"  # indique que c'est un fallback
            accounts_status_payload = synthetic

    accounts = {
        "linked": linked,
        "connected": connected,
        "accounts_status": accounts_status_payload,
    }

    # ── Kill switch ───────────────────────────────────────────────────────
    kill_switch = agent_service.get_kill_switch(session_string)

    # ── 5 dernières actions ───────────────────────────────────────────────
    action_log = agent_service.get_action_log(session_string, limit=5)

    return {
        "type": "update",
        "health": health,
        "accounts": accounts,
        "kill_switch": kill_switch,
        "action_log": action_log,
        "ts": _time.time(),
    }


@router.websocket("/ws/connector")
async def ws_connector(
    websocket: WebSocket,
    token: Optional[str] = Query(default=None),
):
    """
    WebSocket temps réel pour le dashboard du connecteur NT8.

    Authentification : le client passe son session_string encodé en base64
    via le paramètre ?token=<base64(session_string)> dans l'URL.
    C'est la même mécanique que les routes HTTP (voir deps.py).

    Le serveur push un payload complet toutes les PUSH_INTERVAL_SEC secondes.
    """
    # ── Authentification ──────────────────────────────────────────────────
    session_string: Optional[str] = None
    if token:
        try:
            session_string = _decode_session_string(token)
        except Exception:
            session_string = None

    if not session_string:
        await websocket.accept()
        await websocket.send_json({"type": "error", "message": "Token d'authentification manquant ou invalide"})
        await websocket.close(code=4001)
        return

    await websocket.accept()

    last_activity = time.time()

    try:
        # Envoyer le payload initial immédiatement
        payload = _build_payload(session_string)
        await websocket.send_json(payload)

        while True:
            # Attendre soit un message client, soit l'expiration du timer
            try:
                # Timeout court pour pouvoir push régulièrement
                raw = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=PUSH_INTERVAL_SEC,
                )
                last_activity = time.time()

                # Traiter le message client
                try:
                    msg = json.loads(raw)
                    if msg.get("type") == "ping":
                        await websocket.send_json({"type": "pong", "ts": time.time()})
                except (json.JSONDecodeError, AttributeError):
                    pass  # Message malformé — on ignore

            except asyncio.TimeoutError:
                # Pas de message client → c'est normal, on push les données
                pass

            # Vérifier le timeout d'inactivité
            if time.time() - last_activity > WS_IDLE_TIMEOUT_SEC:
                await websocket.close(code=4002)
                break

            # Vérifier que la connexion est toujours ouverte
            if websocket.client_state != WebSocketState.CONNECTED:
                break

            # Push les données mises à jour
            try:
                payload = _build_payload(session_string)
                await websocket.send_json(payload)
            except Exception:
                break

    except WebSocketDisconnect:
        pass  # Déconnexion normale du client
    except Exception:
        pass  # Toute autre erreur — on ferme proprement
    finally:
        # Fermeture propre si la connexion est encore ouverte
        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.close()
        except Exception:
            pass

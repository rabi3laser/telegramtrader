"""
Routes API pour l'AGENT LOCAL NINJATRADER 8 (solution 100% gratuite, sans CrossTrade).

Flux :
  1. L'utilisateur clique "Générer mon token" dans Paramètres → POST /nt8-agent/token
  2. Il télécharge le script agent pré-configuré → GET /nt8-agent/download-script
  3. Il lance le script sur SA machine (là où tourne NinjaTrader 8)
  4. Le script fait un GET /nt8-agent/poll?token=... toutes les 2-3s (pas d'auth
     Telegram nécessaire ici, le token fait office de clé d'accès dédiée à l'agent)
  5. Quand un signal doit être exécuté, le backend appelle push_signal(), et le
     prochain poll de l'agent le récupère puis écrit telegram_signal.json localement
  6. Le script envoie un heartbeat régulier (avec le contenu de nt8_current_price.json)
     pour que l'UI affiche "Agent connecté" en temps réel
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from pathlib import Path

from app.services import nt8_agent_service as agent_service
from app.api.deps import get_session_string

router = APIRouter()

# Emplacement de l'exécutable universel pré-compilé (voir scripts/build_agent_exe.ps1)
# Cherche d'abord dans agent/dist/ (PyInstaller local), puis dans agent_dist/ (production)
_base = Path(__file__).resolve().parent.parent.parent
AGENT_EXE_PATH = (
    _base / "agent" / "dist" / "TelegramTraderAgent.exe"
    if (_base / "agent" / "dist" / "TelegramTraderAgent.exe").exists()
    else _base / "agent_dist" / "TelegramTraderAgent.exe"
)

# Emplacement du fichier NinjaScript (stratégie de trading + panneau de
# calibration fusionnés) à installer dans NinjaTrader 8.
STRATEGY_DIR = Path(__file__).resolve().parent.parent.parent / "nt8_strategy"
STRATEGY_FILE_PATH = STRATEGY_DIR / "TelegramSignalStrategyV3.cs"
ADDON_FILE_PATH    = STRATEGY_DIR / "TelegramTraderAddOn.cs"



class GenerateTokenRequest(BaseModel):
    account_name: Optional[str] = None


class HeartbeatRequest(BaseModel):
    token: str
    price_info: Optional[Dict[str, Any]] = None
    accounts_info: Optional[Dict[str, Any]] = None


class PushSignalRequest(BaseModel):
    signal: Dict[str, Any]


class PairRequest(BaseModel):
    code: str


class PushCommandRequest(BaseModel):
    action: str  # select_account | connect_connection | disconnect_connection
    account_name: Optional[str] = None
    connection_name: Optional[str] = None


class KillSwitchRequest(BaseModel):
    active: bool
    reason: Optional[str] = None




@router.post("/token")
async def generate_token(
    data: GenerateTokenRequest, session_string: str = Depends(get_session_string)
):
    """Génère (ou régénère) le token d'agent local pour l'utilisateur connecté."""
    config = agent_service.generate_agent_token(session_string, account_name=data.account_name)
    return {
        "linked": True,
        "connected": False,
        "token": config["token"],
        "account_name": config.get("account_name"),
    }


@router.get("/status")
async def get_status(session_string: str = Depends(get_session_string)):
    """Statut de la liaison agent (lié ou non, connecté en temps réel ou non)."""
    return agent_service.get_status(session_string)


@router.delete("/token")
async def revoke_token(session_string: str = Depends(get_session_string)):
    """Révoque le token de l'utilisateur (déconnecte l'agent)."""
    success = agent_service.revoke_agent(session_string)
    return {"success": success}


@router.get("/download-script")
async def download_script(session_string: str = Depends(get_session_string)):
    """
    Génère le script Python de l'agent local, PRÉ-CONFIGURÉ avec le token de
    l'utilisateur et l'URL de l'API, prêt à être exécuté tel quel sur sa machine.
    """
    config = agent_service.get_agent_config(session_string)
    if not config:
        raise HTTPException(status_code=400, detail="Générez d'abord un token avant de télécharger l'agent")

    script_content = _build_agent_script(config["token"])
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(
        content=script_content,
        media_type="text/x-python",
        headers={"Content-Disposition": "attachment; filename=telegramtrader_nt8_agent.py"},
    )


@router.get("/download-exe")
async def download_exe():
    """
    Télécharge l'exécutable universel (.exe) de l'agent local — AUCUN token
    n'est embarqué dedans (le même binaire est distribué à tout le monde).
    Au premier lancement, l'utilisateur saisit un code d'appairage (voir
    /pairing-code et /pair) OU l'exe peut être lancé avec un raccourci
    contenant déjà --code=XXXX-XX (généré dynamiquement par le bouton
    "Télécharger" de l'UI, via une redirection côté frontend).
    """
    if not AGENT_EXE_PATH.exists():
        raise HTTPException(
            status_code=404,
            detail=(
                "L'exécutable de l'agent n'a pas encore été généré sur ce serveur. "
                "Utilisez en attendant le script Python (bouton 'Télécharger le script agent')."
            ),
        )
    from fastapi.responses import FileResponse
    return FileResponse(
        path=str(AGENT_EXE_PATH),
        media_type="application/vnd.microsoft.portable-executable",
        filename="TelegramTraderAgent.exe",
    )


@router.get("/download-strategy")
async def download_strategy():
    """
    Télécharge le fichier NinjaScript TelegramSignalStrategyV3.cs (stratégie
    de trading + panneau de calibration fusionnés) à installer dans
    Documents\\NinjaTrader 8\\bin\\Custom\\Strategies\\, PUIS à compiler
    (Tools → Edit NinjaScript → F5) avant de l'appliquer comme Stratégie
    sur un graphique. Prérequis obligatoire avant que l'agent local ne
    puisse exécuter le moindre signal.
    """
    if not STRATEGY_FILE_PATH.exists():
        raise HTTPException(
            status_code=404,
            detail="Le fichier de stratégie n'est pas disponible sur ce serveur pour le moment.",
        )
    from fastapi.responses import FileResponse
    return FileResponse(
        path=str(STRATEGY_FILE_PATH),
        media_type="text/plain",
        filename="TelegramSignalStrategyV3.cs",
    )


@router.get("/download-addon")
async def download_addon():
    """
    Télécharge le fichier NinjaScript TelegramTraderAddOn.cs (Add-On multi-comptes
    avec démarrage automatique du moteur) à installer dans
    Documents\\NinjaTrader 8\\bin\\Custom\\AddOns\\, PUIS à compiler
    (Tools → Edit NinjaScript → F5). Remplace la stratégie V3 pour une
    utilisation multi-comptes sans graphique ouvert.
    """
    if not ADDON_FILE_PATH.exists():
        raise HTTPException(
            status_code=404,
            detail="Le fichier Add-On n'est pas disponible sur ce serveur pour le moment.",
        )
    from fastapi.responses import FileResponse
    return FileResponse(
        path=str(ADDON_FILE_PATH),
        media_type="text/plain",
        filename="TelegramTraderAddOn.cs",
    )


@router.post("/pairing-code")
async def create_pairing_code(
    data: GenerateTokenRequest, session_string: str = Depends(get_session_string)

):
    """
    Génère un code d'appairage court (ex: '4829-15'), valable 10 minutes, que
    l'utilisateur saisit UNE SEULE FOIS dans l'agent (script ou .exe). Évite
    de manipuler le token brut : façon WhatsApp Web / Netflix TV.
    """
    result = agent_service.generate_pairing_code(session_string, account_name=data.account_name)
    return result


@router.post("/pair")
async def pair_with_code(data: PairRequest):
    """
    Appelé par l'agent local avec le code saisi par l'utilisateur. Retourne
    le token définitif à mémoriser localement (%APPDATA%) — l'agent n'aura
    plus jamais besoin de redemander de code après ce premier appairage.
    """
    result = agent_service.claim_pairing_code(data.code)
    if not result:
        raise HTTPException(status_code=404, detail="Code invalide ou expiré. Générez-en un nouveau depuis l'application.")
    return result



@router.get("/poll")
async def poll_signals(token: str = Query(...)):
    """
    Appelé par l'agent local (polling toutes les 2-3s). Ne nécessite PAS
    d'authentification Telegram : le token dédié à l'agent suffit (généré
    depuis l'app, jamais partagé publiquement).
    """
    signals = agent_service.pop_pending_signals(token)
    return {"signals": signals}


@router.get("/poll-commands")
async def poll_commands(token: str = Query(...)):
    """
    Appelé par l'agent local (même fréquence que /poll) pour récupérer les
    commandes de gestion de comptes/connexions en attente (sélection de
    compte actif, connexion/déconnexion d'une connexion), poussées depuis
    l'application web. L'agent écrit ensuite ces commandes dans
    telegramtrader_addon_command.json, lu par TelegramTraderEngine.PollCommand().
    """
    commands = agent_service.pop_pending_commands(token)
    return {"commands": commands}


@router.post("/heartbeat")
async def heartbeat(data: HeartbeatRequest):
    """Reçoit un signe de vie régulier de l'agent local (+ prix/solde/PnL et/ou
    comptes/connexions NinjaTrader optionnels)."""
    success = agent_service.record_heartbeat(data.token, data.price_info, data.accounts_info)
    if not success:
        raise HTTPException(status_code=404, detail="Token d'agent inconnu ou révoqué")
    return {"success": True}


@router.post("/push-signal")
async def push_signal(
    data: PushSignalRequest, session_string: str = Depends(get_session_string)
):
    """
    Pousse un signal dans la file d'attente de l'agent de l'utilisateur.
    Utilisé en interne par le pipeline de détection de signaux Telegram et
    pour les tests manuels depuis la page Trading.
    """
    success = agent_service.push_signal(session_string, data.signal)
    if not success:
        raise HTTPException(status_code=400, detail="Aucun agent lié pour cet utilisateur")
    return {"success": True}


@router.post("/command")
async def push_command(
    data: PushCommandRequest, session_string: str = Depends(get_session_string)
):
    """
    Pousse une commande de gestion de compte/connexion (sélection du compte
    actif, connexion/déconnexion d'une connexion) dans la file d'attente de
    l'agent de l'utilisateur, pour pilotage à distance depuis l'application
    web (page Paramètres → section "Comptes NinjaTrader").
    """
    success = agent_service.push_command(session_string, data.model_dump())
    if not success:
        raise HTTPException(status_code=400, detail="Aucun agent lié pour cet utilisateur")
    # Journaliser l'action pour l'historique
    agent_service.log_action(session_string, data.action, {
        k: v for k, v in {
            "account_name": data.account_name,
            "connection_name": data.connection_name,
        }.items() if v is not None
    })
    return {"success": True}


@router.get("/accounts")
async def get_accounts_status(session_string: str = Depends(get_session_string)):
    """
    Retourne le dernier instantané connu des comptes/connexions NinjaTrader
    (remonté par l'Add-On via l'agent local lors du heartbeat), pour affichage
    dans la page Paramètres de l'application web.
    """
    status = agent_service.get_status(session_string)
    return {
        "linked": status.get("linked", False),
        "connected": status.get("connected", False),
        "accounts_status": status.get("last_accounts"),
    }


@router.get("/kill-switch")
async def get_kill_switch(session_string: str = Depends(get_session_string)):
    """Retourne l'état actuel du kill switch (trading suspendu ou non)."""
    return agent_service.get_kill_switch(session_string)


@router.post("/kill-switch")
async def set_kill_switch(
    data: KillSwitchRequest, session_string: str = Depends(get_session_string)
):
    """
    Active ou désactive le kill switch de trading.
    Quand actif, aucun nouveau signal ne sera exécuté sur NinjaTrader 8.
    L'agent et NinjaTrader restent connectés — seule l'exécution des signaux
    est bloquée. Réactivation manuelle obligatoire (sécurité intentionnelle).
    """
    result = agent_service.set_kill_switch(session_string, data.active, data.reason)
    return result


@router.get("/action-log")
async def get_action_log(
    session_string: str = Depends(get_session_string),
    limit: int = Query(default=20, ge=1, le=100),
):
    """
    Retourne l'historique des actions effectuées depuis l'application web
    (sélection de compte, connexion/déconnexion, kill switch...).
    Utile pour l'audit et le débogage.
    """
    entries = agent_service.get_action_log(session_string, limit=limit)
    return {"entries": entries, "count": len(entries)}


@router.get("/health")
async def get_connector_health(session_string: str = Depends(get_session_string)):
    """
    Dashboard de santé du connecteur NT8 — agrège l'état de chaque maillon
    de la chaîne : Backend ↔ Agent ↔ NinjaTrader 8 Add-On.

    Retourne un objet structuré avec :
    - backend : toujours OK si cette route répond (preuve que le backend tourne)
    - agent : lié/connecté, dernière communication, délai depuis le dernier heartbeat
    - nt8 : NinjaTrader détecté actif (via fraîcheur du fichier prix), compte sélectionné,
            moteur bloqué ou non, position ouverte
    - signal_queue : nombre de signaux en attente dans la file backend
    - command_queue : nombre de commandes en attente dans la file backend
    """
    import time as _time
    status = agent_service.get_status(session_string)

    # ── Maillon 1 : Backend (toujours OK si on est ici) ──────────────────
    backend_health = {
        "ok": True,
        "message": "Backend opérationnel",
    }

    # ── Maillon 2 : Agent Windows ─────────────────────────────────────────
    linked = status.get("linked", False)
    connected = status.get("connected", False)
    last_heartbeat = status.get("last_heartbeat")
    heartbeat_age_sec = None
    if last_heartbeat:
        heartbeat_age_sec = round(_time.time() - last_heartbeat, 1)

    agent_health = {
        "ok": connected,
        "linked": linked,
        "connected": connected,
        "last_heartbeat_age_sec": heartbeat_age_sec,
        "message": (
            "Agent connecté ✅" if connected
            else ("Agent lié mais inactif (heartbeat expiré)" if linked else "Aucun agent lié")
        ),
    }

    # ── Maillon 3 : NinjaTrader 8 (via les données remontées par heartbeat) ─
    last_price = status.get("last_price") or {}
    last_accounts = status.get("last_accounts") or {}

    # NinjaTrader est considéré actif si le prix a été remonté récemment
    # (le champ last_price est mis à jour à chaque heartbeat par l'agent)
    nt8_active = connected and bool(last_price)

    nt8_health = {
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
    }

    # ── Files d'attente backend ───────────────────────────────────────────
    # Permet de détecter un engorgement (signaux non consommés = agent mort)
    queue_info = agent_service.get_queue_sizes(session_string)

    return {
        "backend": backend_health,
        "agent": agent_health,
        "nt8": nt8_health,
        "queues": queue_info,
        "overall_ok": backend_health["ok"] and agent_health["ok"] and nt8_health["ok"],
    }



def _build_agent_script(token: str) -> str:
    """Construit dynamiquement le script agent Python pré-configuré."""
    return f'''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════════════════
 AGENT LOCAL TELEGRAMTRADER — NinjaTrader 8 (100% GRATUIT)
═══════════════════════════════════════════════════════════════════

Ce script fait le pont entre l'application TelegramTrader (cloud) et votre
NinjaTrader 8 local, SANS aucun abonnement tiers (pas de CrossTrade).

Fonctionnement :
  1. Il interroge l'API TelegramTrader toutes les 2 secondes pour récupérer
     les nouveaux signaux à exécuter.
  2. Il écrit chaque signal dans le fichier "telegram_signal.json" du dossier
     NinjaTrader 8, que la stratégie NinjaScript "TelegramSignalStrategyV3"
     (stratégie de trading + panneau de calibration fusionnés en un seul
     fichier) lit et exécute automatiquement (déjà installée dans votre NT8).
  3. Il envoie un signe de vie (heartbeat) régulier avec le contenu de
     "nt8_current_price.json" (P&L, solde, position) pour que l'application
     affiche en temps réel que votre compte est bien connecté.

PRÉREQUIS :
  - NinjaTrader 8 doit être OUVERT avec la stratégie TelegramSignalStrategyV3
    (stratégie de trading + panneau de calibration fusionnés) activée sur le
    graphique de votre instrument.
  - Python 3.8+ installé sur cette machine (aucune dépendance externe requise,
    uniquement des modules standards).
  - Laissez cette fenêtre ouverte pendant vos sessions de trading.

Token de connexion (personnel, ne le partagez jamais) : {token}
═══════════════════════════════════════════════════════════════════
"""
import json
import os
import time
import urllib.request
import urllib.error

# ── CONFIGURATION (pré-remplie automatiquement) ─────────────────
API_BASE_URL = "http://localhost:8000/api"  # Remplacez par l'URL de votre serveur en production
AGENT_TOKEN = "{token}"
POLL_INTERVAL_SEC = 2
HEARTBEAT_INTERVAL_SEC = 5

# ── Chemins locaux NinjaTrader 8 ─────────────────────────────────
DOCS_DIR = os.path.join(os.path.expanduser("~"), "Documents", "NinjaTrader 8")
SIGNAL_FILE = os.path.join(DOCS_DIR, "telegram_signal.json")
PRICE_FILE = os.path.join(DOCS_DIR, "nt8_current_price.json")
COMMAND_FILE = os.path.join(DOCS_DIR, "telegramtrader_addon_command.json")
ACCOUNTS_STATUS_FILE = os.path.join(DOCS_DIR, "nt8_accounts_status.json")



def http_get_json(url):
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"[AGENT] Erreur GET {{url}}: {{e}}")
        return None


def http_post_json(url, payload):
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={{"Content-Type": "application/json"}}, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"[AGENT] Erreur POST {{url}}: {{e}}")
        return None


def write_signal_file(signal):
    """Écrit le signal au format attendu par TelegramSignalStrategyV3.cs"""
    try:
        os.makedirs(DOCS_DIR, exist_ok=True)
        payload = {{
            "direction": signal.get("type", "BUY"),
            "entry": signal.get("entry_price", 0),
            "sl": signal.get("stop_loss", 0),
            "tp": signal.get("target_price", 0),
            "tp2": signal.get("target_price_2", 0),
            "contracts": signal.get("quantity", 1),
            "confidence": signal.get("confidence", 0),
            "channels": signal.get("source_channel", ""),
            "timestamp": signal.get("date", ""),
            "order_type": signal.get("order_type", ""),
            "risk_pct": signal.get("risk_pct", 0),
        }}
        with open(SIGNAL_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f)
        print(f"[AGENT] ✅ Signal écrit : {{payload['direction']}} @ {{payload['entry']}} (SL={{payload['sl']}} TP={{payload['tp']}})")
    except Exception as e:
        print(f"[AGENT] ❌ Erreur écriture signal : {{e}}")


def read_price_file():
    """Lit le fichier de prix/solde exporté par la stratégie NinjaScript."""
    try:
        if os.path.exists(PRICE_FILE):
            with open(PRICE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return None


def write_command_file(command):
    """Écrit une commande de gestion de compte/connexion, lue ensuite par
    TelegramTraderEngine.PollCommand() dans l'Add-On NinjaTrader."""
    try:
        os.makedirs(DOCS_DIR, exist_ok=True)
        with open(COMMAND_FILE, "w", encoding="utf-8") as f:
            json.dump(command, f)
        print(f"[AGENT] ✅ Commande écrite : {{command.get('action')}}")
    except Exception as e:
        print(f"[AGENT] ❌ Erreur écriture commande : {{e}}")


def read_accounts_status_file():
    """Lit le fichier de statut des comptes/connexions exporté par l'Add-On."""
    try:
        if os.path.exists(ACCOUNTS_STATUS_FILE):
            with open(ACCOUNTS_STATUS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return None


def main():
    print("═" * 60)
    print(" AGENT LOCAL TELEGRAMTRADER — NinjaTrader 8")
    print("═" * 60)
    print(f"Dossier NT8 détecté : {{DOCS_DIR}}")
    print(f"Serveur API : {{API_BASE_URL}}")
    print("En attente de signaux... (Ctrl+C pour arrêter)")
    print("═" * 60)

    last_heartbeat = 0

    while True:
        try:
            # ── Poll des signaux en attente ──────────────────────
            result = http_get_json(f"{{API_BASE_URL}}/nt8-agent/poll?token={{AGENT_TOKEN}}")
            if result and result.get("signals"):
                for signal in result["signals"]:
                    write_signal_file(signal)

            # ── Poll des commandes de gestion de comptes/connexions ──
            cmd_result = http_get_json(f"{{API_BASE_URL}}/nt8-agent/poll-commands?token={{AGENT_TOKEN}}")
            if cmd_result and cmd_result.get("commands"):
                for command in cmd_result["commands"]:
                    write_command_file(command)

            # ── Heartbeat régulier avec infos de prix/compte ─────
            now = time.time()
            if now - last_heartbeat >= HEARTBEAT_INTERVAL_SEC:
                price_info = read_price_file()
                accounts_info = read_accounts_status_file()
                http_post_json(f"{{API_BASE_URL}}/nt8-agent/heartbeat", {{
                    "token": AGENT_TOKEN,
                    "price_info": price_info,
                    "accounts_info": accounts_info,
                }})
                last_heartbeat = now

            time.sleep(POLL_INTERVAL_SEC)


        except KeyboardInterrupt:
            print("\\n[AGENT] Arrêt demandé par l'utilisateur.")
            break
        except Exception as e:
            print(f"[AGENT] Erreur inattendue : {{e}}")
            time.sleep(POLL_INTERVAL_SEC)


if __name__ == "__main__":
    main()
'''

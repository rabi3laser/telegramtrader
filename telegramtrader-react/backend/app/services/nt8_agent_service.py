"""
Service AGENT LOCAL NINJATRADER 8 — Solution 100% GRATUITE (sans CrossTrade).

Principe :
  - Chaque utilisateur génère un TOKEN unique dans l'application.
  - Il télécharge un petit script Python ("agent local") qu'il exécute sur SA
    machine (là où tourne NinjaTrader 8).
  - Cet agent interroge (polling) notre API cloud avec son token toutes les
    2-3 secondes pour récupérer les signaux en attente, et écrit le fichier
    JSON local (telegram_signal.json) que la stratégie NinjaScript existante
    (TelegramSignalStrategyV2.cs) lit déjà et exécute automatiquement.
  - Aucun add-on tiers, aucun abonnement mensuel : uniquement du code que
    nous maîtrisons de bout en bout.

Limite connue : NinjaTrader doit être ouvert ET l'agent local doit être lancé
sur la machine de l'utilisateur pour que les signaux soient exécutés. C'est
la même contrainte que pour CrossTrade (qui nécessite aussi NT8 ouvert), mais
sans coût récurrent.
"""
import hashlib
import json
import secrets
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
AGENTS_FILE = DATA_DIR / "nt8_agents.json"
QUEUES_FILE = DATA_DIR / "nt8_signal_queues.json"
PAIRING_FILE = DATA_DIR / "nt8_pairing_codes.json"
COMMAND_QUEUES_FILE = DATA_DIR / "nt8_command_queues.json"
ACTION_LOG_FILE = DATA_DIR / "nt8_action_log.json"
KILL_SWITCH_FILE = DATA_DIR / "nt8_kill_switch.json"

# CORRECTIF RACE CONDITIONS : FastAPI est async et peut traiter plusieurs
# requêtes HTTP concurrentes dans le même processus. Sans verrou, deux
# requêtes simultanées (ex: heartbeat + poll) peuvent lire le même fichier
# JSON, modifier leur copie en mémoire, puis écrire — la dernière écriture
# écrase silencieusement les modifications de l'autre (perte de données).
# Un threading.Lock() suffit ici car les opérations I/O fichier sont courtes
# et synchrones (pas d'await). Un seul lock global couvre tous les fichiers
# pour éviter les deadlocks inter-fichiers (ex: agents.json ↔ queues.json).
_file_lock = threading.Lock()


HEARTBEAT_TIMEOUT_SEC = 20  # au-delà, l'agent est considéré déconnecté
PAIRING_CODE_TTL_SEC = 600  # un code d'appairage expire après 10 minutes



def _user_key(session_string: str) -> str:
    return hashlib.sha256(session_string.encode("utf-8")).hexdigest()


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_json(path: Path, data: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ═══════════════════════════════════════════════════════════════
# GESTION DES AGENTS (1 agent = 1 utilisateur = 1 token)
# ═══════════════════════════════════════════════════════════════

def generate_agent_token(session_string: str, account_name: Optional[str] = None) -> Dict[str, Any]:
    """Génère (ou régénère) le token d'agent local pour l'utilisateur."""
    with _file_lock:
        agents = _load_json(AGENTS_FILE)
        key = _user_key(session_string)
        token = secrets.token_urlsafe(32)
        agents[key] = {
            "token": token,
            "account_name": account_name or "",
            "created_at": time.time(),
            "last_heartbeat": None,
            "last_price": None,
        }
        _save_json(AGENTS_FILE, agents)

        # Réinitialiser la file d'attente associée à ce token
        queues = _load_json(QUEUES_FILE)
        queues[token] = []
        _save_json(QUEUES_FILE, queues)

        return agents[key]


def get_agent_config(session_string: str) -> Optional[Dict[str, Any]]:
    agents = _load_json(AGENTS_FILE)
    return agents.get(_user_key(session_string))


def revoke_agent(session_string: str) -> bool:
    # Verrou nécessaire : lecture-modification-écriture atomique sur deux fichiers
    # (agents.json + queues.json) — sans verrou, un heartbeat concurrent pourrait
    # réécrire l'agent juste après qu'on l'ait supprimé.
    with _file_lock:
        agents = _load_json(AGENTS_FILE)
        key = _user_key(session_string)
        config = agents.pop(key, None)
        _save_json(AGENTS_FILE, agents)
        if config:
            queues = _load_json(QUEUES_FILE)
            queues.pop(config["token"], None)
            _save_json(QUEUES_FILE, queues)
            return True
    return False


def is_connected(config: Optional[Dict[str, Any]]) -> bool:
    if not config or not config.get("last_heartbeat"):
        return False
    return (time.time() - config["last_heartbeat"]) < HEARTBEAT_TIMEOUT_SEC


def get_status(session_string: str) -> Dict[str, Any]:
    config = get_agent_config(session_string)
    if not config:
        return {"linked": False, "connected": False}
    return {
        "linked": True,
        "connected": is_connected(config),
        "account_name": config.get("account_name"),
        "last_heartbeat": config.get("last_heartbeat"),
        "last_price": config.get("last_price"),
        "last_accounts": config.get("last_accounts"),
        "token_masked": _mask_token(config["token"]),
        "token": config["token"],  # nécessaire pour générer le script pré-configuré
    }



def _mask_token(token: str) -> str:
    if len(token) <= 8:
        return "*" * len(token)
    return f"{token[:4]}{'*' * (len(token) - 8)}{token[-4:]}"


def _find_key_by_token(token: str) -> Optional[str]:
    agents = _load_json(AGENTS_FILE)
    for key, cfg in agents.items():
        if cfg.get("token") == token:
            return key
    return None


# ═══════════════════════════════════════════════════════════════
# FILE D'ATTENTE DE SIGNAUX (poussés par le backend, tirés par l'agent)
# ═══════════════════════════════════════════════════════════════

def push_signal(session_string: str, signal: Dict[str, Any]) -> bool:
    """Ajoute un signal à la file d'attente de l'agent de l'utilisateur.
    Retourne False si l'agent n'existe pas OU si le kill switch est actif."""
    # Vérification kill switch AVANT d'acquérir le verrou (lecture seule)
    ks_state = get_kill_switch(session_string)
    if ks_state.get("active"):
        # Kill switch actif : on refuse silencieusement le signal
        # (l'appelant doit vérifier l'état du kill switch et informer l'utilisateur)
        return False

    # Verrou nécessaire : pop_pending_signals() vide la file en même temps que
    # push_signal() pourrait y ajouter un élément — sans verrou, le signal
    # ajouté serait silencieusement écrasé par l'écriture concurrente.
    with _file_lock:
        agents = _load_json(AGENTS_FILE)
        config = agents.get(_user_key(session_string))
        if not config:
            return False
        queues = _load_json(QUEUES_FILE)
        token = config["token"]
        queue = queues.get(token, [])
        queue.append({**signal, "queued_at": time.time()})
        queues[token] = queue
        _save_json(QUEUES_FILE, queues)
    return True


def pop_pending_signals(token: str) -> List[Dict[str, Any]]:
    """Récupère (et vide) la file d'attente pour un token d'agent donné.
    Appelé par l'agent local lors de son polling."""
    # Verrou nécessaire : opération "lire puis vider" doit être atomique —
    # deux polls simultanés (rare mais possible) renverraient les mêmes signaux
    # en double, ce qui déclencherait deux ordres identiques sur NinjaTrader.
    with _file_lock:
        queues = _load_json(QUEUES_FILE)
        pending = queues.get(token, [])
        if pending:
            queues[token] = []
            _save_json(QUEUES_FILE, queues)
    return pending


def record_heartbeat(
    token: str,
    price_info: Optional[Dict[str, Any]] = None,
    accounts_info: Optional[Dict[str, Any]] = None,
) -> bool:
    """Met à jour le heartbeat de l'agent (preuve que le script tourne bien
    et que NinjaTrader est ouvert), avec en option le dernier prix/solde/PnL
    remonté depuis nt8_current_price.json, et/ou le dernier instantané des
    comptes/connexions NinjaTrader remonté depuis nt8_accounts_status.json."""
    # Verrou nécessaire : heartbeat + revoke_agent peuvent s'exécuter en même
    # temps — sans verrou, le heartbeat pourrait réécrire un agent déjà révoqué.
    with _file_lock:
        # _find_key_by_token lit agents.json — on le refait DANS le verrou pour
        # éviter un TOCTOU (token révoqué entre la lecture et l'écriture).
        agents = _load_json(AGENTS_FILE)
        key = None
        for k, cfg in agents.items():
            if cfg.get("token") == token:
                key = k
                break
        if not key:
            return False
        agents[key]["last_heartbeat"] = time.time()
        if price_info:
            agents[key]["last_price"] = price_info
        if accounts_info:
            agents[key]["last_accounts"] = accounts_info
        _save_json(AGENTS_FILE, agents)
    return True


def is_agent_linked(session_string: str) -> bool:
    return get_agent_config(session_string) is not None


# ═══════════════════════════════════════════════════════════════
# FILE D'ATTENTE DE COMMANDES (pilotage à distance des comptes/connexions
# NinjaTrader depuis l'application web) — même principe que la file de
# signaux, mais consommée par l'agent local pour écrire
# telegramtrader_addon_command.json (lu par TelegramTraderEngine.PollCommand()).
# ═══════════════════════════════════════════════════════════════

def push_command(session_string: str, command: Dict[str, Any]) -> bool:
    """Ajoute une commande (select_account / connect_connection /
    disconnect_connection) à la file d'attente de l'agent de l'utilisateur."""
    # Même logique que push_signal : atomicité lecture-écriture indispensable
    # pour éviter qu'un pop_pending_commands concurrent n'écrase la commande.
    with _file_lock:
        agents = _load_json(AGENTS_FILE)
        config = agents.get(_user_key(session_string))
        if not config:
            return False
        queues = _load_json(COMMAND_QUEUES_FILE)
        token = config["token"]
        queue = queues.get(token, [])
        queue.append({**command, "queued_at": time.time()})
        queues[token] = queue
        _save_json(COMMAND_QUEUES_FILE, queues)
    return True


def pop_pending_commands(token: str) -> List[Dict[str, Any]]:
    """Récupère (et vide) la file de commandes en attente pour un token
    d'agent donné. Appelé par l'agent local lors de son polling."""
    # Même logique que pop_pending_signals : atomicité critique pour éviter
    # qu'une commande (ex: select_account) soit exécutée deux fois.
    with _file_lock:
        queues = _load_json(COMMAND_QUEUES_FILE)
        pending = queues.get(token, [])
        if pending:
            queues[token] = []
            _save_json(COMMAND_QUEUES_FILE, queues)
    return pending



# ═══════════════════════════════════════════════════════════════
# CODE D'APPAIRAGE (méthode "WhatsApp Web") — évite de manipuler le
# token en clair. L'utilisateur génère un code depuis l'interface web,
# le saisit UNE SEULE FOIS dans l'agent universel (ou l'exe), qui échange
# ensuite ce code contre le vrai token et le mémorise localement
# (%APPDATA%) pour ne plus jamais le redemander.
# ═══════════════════════════════════════════════════════════════

def _generate_code() -> str:
    """Génère un code court et lisible, ex: '4829-15' (façon WhatsApp Web)."""
    n = secrets.randbelow(10**6)
    s = f"{n:06d}"
    return f"{s[:4]}-{s[4:]}"


def _purge_expired_codes(codes: Dict[str, Any]) -> Dict[str, Any]:
    now = time.time()
    return {c: v for c, v in codes.items() if v.get("expires_at", 0) > now}


def generate_pairing_code(session_string: str, account_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Crée (ou réutilise) le token de l'utilisateur, puis génère un code
    d'appairage temporaire (10 minutes) qui pointe vers ce token. Ce code
    est ce que l'utilisateur communique à l'agent local — jamais le token
    brut.
    """
    # Verrou global : cette fonction touche à la fois agents.json ET pairing.json,
    # et appelle generate_agent_token() qui acquiert aussi le verrou — on évite
    # la réentrance en extrayant la logique inline plutôt qu'en appelant la
    # fonction wrappée. Le verrou est acquis UNE SEULE FOIS ici.
    with _file_lock:
        agents = _load_json(AGENTS_FILE)
        key = _user_key(session_string)
        config = agents.get(key)

        if not config:
            # Créer un nouveau token directement (sans appeler generate_agent_token
            # pour éviter une double acquisition du verrou)
            token = secrets.token_urlsafe(32)
            config = {
                "token": token,
                "account_name": account_name or "",
                "created_at": time.time(),
                "last_heartbeat": None,
                "last_price": None,
            }
            agents[key] = config
            _save_json(AGENTS_FILE, agents)
            queues = _load_json(QUEUES_FILE)
            queues[token] = []
            _save_json(QUEUES_FILE, queues)
        elif account_name:
            agents[key]["account_name"] = account_name
            config = agents[key]
            _save_json(AGENTS_FILE, agents)

        codes = _purge_expired_codes(_load_json(PAIRING_FILE))

        # Retirer d'éventuels anciens codes pointant déjà vers ce token
        codes = {c: v for c, v in codes.items() if v.get("token") != config["token"]}

        code = _generate_code()
        while code in codes:
            code = _generate_code()

        expires_at = time.time() + PAIRING_CODE_TTL_SEC
        codes[code] = {
            "token": config["token"],
            "account_name": config.get("account_name", ""),
            "expires_at": expires_at,
            "claimed": False,
        }
        _save_json(PAIRING_FILE, codes)

    return {"code": code, "expires_at": expires_at, "ttl_seconds": PAIRING_CODE_TTL_SEC}


def claim_pairing_code(code: str) -> Optional[Dict[str, Any]]:
    """
    Appelé par l'agent local (script générique ou .exe) avec le code saisi
    par l'utilisateur. Retourne le token correspondant si le code est valide
    et non expiré, puis invalide immédiatement le code (usage unique).
    """
    # Verrou critique : deux agents qui saisiraient le même code simultanément
    # (attaque par rejeu ou double-clic) ne doivent obtenir le token qu'une seule
    # fois — l'opération "lire + supprimer" doit être atomique.
    with _file_lock:
        code = (code or "").strip().upper().replace(" ", "")
        codes = _purge_expired_codes(_load_json(PAIRING_FILE))
        entry = codes.get(code)
        if not entry:
            return None

        # Usage unique : on supprime le code dès qu'il est réclamé
        codes.pop(code, None)
        _save_json(PAIRING_FILE, codes)

    return {"token": entry["token"], "account_name": entry.get("account_name", "")}


def get_pairing_status(session_string: str) -> Dict[str, Any]:
    """Permet à l'UI de savoir si un code généré a déjà été réclamé par
    l'agent (utile pour afficher automatiquement "Connecté" sans recharger)."""
    config = get_agent_config(session_string)
    if not config:
        return {"linked": False, "connected": False}
    return get_status(session_string)


def get_queue_sizes(session_string: str) -> Dict[str, Any]:
    """Retourne le nombre de signaux et de commandes en attente dans les files
    backend pour l'utilisateur donné. Utilisé par le dashboard de santé pour
    détecter un engorgement (signaux non consommés = agent probablement mort)."""
    config = get_agent_config(session_string)
    if not config:
        return {"signal_queue": 0, "command_queue": 0}
    token = config["token"]
    # Lecture sans verrou : lecture seule, pas de modification — acceptable ici
    # car le dashboard de santé est une vue informative, pas une opération critique.
    queues = _load_json(QUEUES_FILE)
    cmd_queues = _load_json(COMMAND_QUEUES_FILE)
    return {
        "signal_queue": len(queues.get(token, [])),
        "command_queue": len(cmd_queues.get(token, [])),
    }


# ═══════════════════════════════════════════════════════════════
# HISTORIQUE DES ACTIONS (log des commandes envoyées depuis l'UI)
# Permet à l'utilisateur de savoir qui a fait quoi et quand :
# sélection de compte, connexion/déconnexion, kill switch, etc.
# ═══════════════════════════════════════════════════════════════

ACTION_LOG_MAX_ENTRIES = 100  # on garde les 100 dernières actions par utilisateur


def log_action(session_string: str, action: str, details: Optional[Dict[str, Any]] = None) -> None:
    """Enregistre une action dans le journal de l'utilisateur.
    action : ex 'select_account', 'connect_connection', 'kill_switch_on', etc.
    details : données supplémentaires (nom du compte, connexion, etc.)
    """
    with _file_lock:
        logs = _load_json(ACTION_LOG_FILE)
        key = _user_key(session_string)
        user_log = logs.get(key, [])
        entry = {
            "timestamp": time.time(),
            "action": action,
            "details": details or {},
        }
        user_log.append(entry)
        # Garder seulement les N dernières entrées pour éviter une croissance infinie
        if len(user_log) > ACTION_LOG_MAX_ENTRIES:
            user_log = user_log[-ACTION_LOG_MAX_ENTRIES:]
        logs[key] = user_log
        _save_json(ACTION_LOG_FILE, logs)


def get_action_log(session_string: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Retourne les dernières actions de l'utilisateur, du plus récent au plus ancien."""
    logs = _load_json(ACTION_LOG_FILE)
    key = _user_key(session_string)
    user_log = logs.get(key, [])
    # Retourner les `limit` dernières entrées, ordre décroissant (plus récent en premier)
    return list(reversed(user_log[-limit:]))


# ═══════════════════════════════════════════════════════════════
# KILL SWITCH — "Suspendre le Trading"
# Permet de bloquer instantanément l'exécution de TOUS les nouveaux
# signaux pour un utilisateur, sans déconnecter l'agent ni NinjaTrader.
# L'agent continue de tourner et de faire ses heartbeats, mais
# push_signal() refuse d'ajouter des signaux à la file tant que le
# kill switch est actif. Réactivation manuelle obligatoire.
# ═══════════════════════════════════════════════════════════════

def set_kill_switch(session_string: str, active: bool, reason: Optional[str] = None) -> Dict[str, Any]:
    """Active ou désactive le kill switch pour l'utilisateur.
    Quand actif, push_signal() refuse tout nouveau signal.
    """
    with _file_lock:
        ks = _load_json(KILL_SWITCH_FILE)
        key = _user_key(session_string)
        if active:
            ks[key] = {
                "active": True,
                "activated_at": time.time(),
                "reason": reason or "Suspendu manuellement depuis l'application",
            }
        else:
            ks.pop(key, None)
        _save_json(KILL_SWITCH_FILE, ks)

    # Journaliser l'action
    log_action(
        session_string,
        "kill_switch_on" if active else "kill_switch_off",
        {"reason": reason} if reason else {},
    )
    return {"active": active}


def get_kill_switch(session_string: str) -> Dict[str, Any]:
    """Retourne l'état du kill switch pour l'utilisateur."""
    ks = _load_json(KILL_SWITCH_FILE)
    key = _user_key(session_string)
    entry = ks.get(key)
    if entry and entry.get("active"):
        return {
            "active": True,
            "activated_at": entry.get("activated_at"),
            "reason": entry.get("reason", ""),
        }
    return {"active": False, "activated_at": None, "reason": ""}



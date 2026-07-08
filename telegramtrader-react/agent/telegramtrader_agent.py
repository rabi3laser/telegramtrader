#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
═══════════════════════════════════════════════════════════════════
 AGENT UNIVERSEL TELEGRAMTRADER — NinjaTrader 8 (100% GRATUIT)
═══════════════════════════════════════════════════════════════════


Ce fichier est le SOURCE utilisé pour compiler TelegramTraderAgent.exe
(voir scripts/build_agent_exe.ps1 → PyInstaller --onefile --noconsole).

Contrairement à l'ancien script généré dynamiquement (un fichier .py par
utilisateur avec le token en clair dans le code), CET agent est UNIVERSEL :
le même .exe est distribué à tout le monde, aucun token n'est codé en dur.

Flux "3 clics" visé :
  1. L'utilisateur télécharge TelegramTraderAgent.exe (une seule fois)
  2. Il double-clique dessus → une icône apparaît dans la barre système
  3. Au premier lancement, une fenêtre lui demande son "code d'appairage"
     (6 chiffres affichés sur le site web, ex: "4829-15", façon WhatsApp Web)
  4. L'agent échange ce code contre un token définitif auprès du serveur,
     puis le mémorise dans %APPDATA%\TelegramTraderAgent\config.json —
     il ne sera plus JAMAIS redemandé (sauf suppression du fichier ou
     "Se déconnecter" depuis le menu de l'icône).
  5. L'agent tourne alors en tâche de fond (aucune fenêtre de console),
     visible uniquement via son icône dans la barre système, avec :
       - tooltip dynamique ("Connecté ✅" / "En attente de NinjaTrader...")
       - menu clic-droit : Voir le statut / Ouvrir les logs / Se déconnecter / Quitter
  6. Il peut s'ajouter automatiquement au démarrage de Windows.

Dépendances (uniquement pour la version "source" — l'exe compilé les
embarque toutes, l'utilisateur final n'a besoin de RIEN installer) :
    pip install pystray pillow
(json, os, time, threading, urllib, tkinter, winreg = bibliothèque standard)
"""
import json
import os
import sys
import time
import threading
import urllib.request
import urllib.error
import webbrowser
from pathlib import Path

# ── CONFIGURATION GÉNÉRALE (identique pour tous les utilisateurs) ──────
# En production, remplacez par l'URL publique de votre serveur (ex:
# https://api.telegramtrader.app/api). Peut aussi être surchargée par la
# variable d'environnement TELEGRAMTRADER_API_URL au moment du build.
API_BASE_URL = os.environ.get("TELEGRAMTRADER_API_URL", "http://localhost:8000/api")
APP_NAME = "TelegramTraderAgent"
POLL_INTERVAL_SEC = 2
HEARTBEAT_INTERVAL_SEC = 5
NT8_FRESHNESS_TIMEOUT_SEC = 30  # au-delà, on considère NinjaTrader "fermé"

# ── BACKOFF EXPONENTIEL (amélioration B) ────────────────────────────────
# Quand le backend est injoignable, on augmente progressivement l'intervalle
# d'attente pour ne pas saturer le réseau ni les logs avec des erreurs en
# rafale. On revient à POLL_INTERVAL_SEC dès que le serveur répond à nouveau.
BACKOFF_MIN_SEC = POLL_INTERVAL_SEC   # délai minimal (normal)
BACKOFF_MAX_SEC = 60                  # délai maximal (1 minute entre tentatives)
BACKOFF_FACTOR = 2                    # doublement à chaque échec consécutif

# ── FILE D'ATTENTE LOCALE PERSISTANTE (amélioration C) ──────────────────
# Si le backend est injoignable au moment où un signal arrive (cas rare mais
# possible : coupure réseau temporaire), l'agent stocke le signal localement
# dans ce fichier JSON et le rejoue dès que la connexion est rétablie.
# Cela évite de perdre un signal de trading pendant une micro-coupure.
OFFLINE_QUEUE_FILE_NAME = "offline_signal_queue.json"

# ── Emplacements locaux ─────────────────────────────────────────────────
APPDATA_DIR = Path(os.environ.get("APPDATA", str(Path.home()))) / APP_NAME
APPDATA_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_FILE = APPDATA_DIR / "config.json"
LOG_FILE = APPDATA_DIR / "agent.log"
OFFLINE_QUEUE_FILE = APPDATA_DIR / OFFLINE_QUEUE_FILE_NAME

DOCS_DIR = Path.home() / "Documents" / "NinjaTrader 8"
SIGNAL_FILE = DOCS_DIR / "telegram_signal.json"
PRICE_FILE = DOCS_DIR / "nt8_current_price.json"
STATUS_FILE = DOCS_DIR / "nt8_last_signal_status.json"
COMMAND_FILE = DOCS_DIR / "telegramtrader_addon_command.json"
ACCOUNTS_STATUS_FILE = DOCS_DIR / "nt8_accounts_status.json"


# Mode debug : TOUJOURS ACTIF par défaut (l'utilisateur a explicitement
# demandé un "mode debug" facilement accessible, sans configuration
# technique type variable d'environnement — impraticable pour un .exe
# --noconsole distribué au grand public). Journalise le contenu complet
# de chaque signal reçu/écrit ainsi que les réponses brutes du serveur,
# directement dans agent.log (consultable via le menu "Ouvrir les logs").
# Reste surchargeable via TELEGRAMTRADER_DEBUG=0 pour le désactiver.
DEBUG_MODE = os.environ.get("TELEGRAMTRADER_DEBUG", "1") != "0"



# ═══════════════════════════════════════════════════════════════════════
# JOURNALISATION (fichier de logs exportable pour le support)
# ═══════════════════════════════════════════════════════════════════════

def log(message: str) -> None:
    """Journalise un message dans le fichier de log ET dans la console si disponible.
    Le print() est protégé dans un try/except car en mode PyInstaller --noconsole
    (production), sys.stdout vaut None → tout print() non protégé lève
    AttributeError et crashe l'agent silencieusement dès le démarrage."""
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}"
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass
    try:
        # sys.stdout est None en mode --noconsole (PyInstaller windowed)
        # sys.stdout peut aussi ne pas supporter les emojis sur certains
        # codepages Windows (cp1252) → on encode/décode en utf-8 avec
        # remplacement des caractères non supportés pour éviter UnicodeEncodeError
        if sys.stdout is not None:
            safe_line = line.encode("utf-8", errors="replace").decode(
                sys.stdout.encoding or "utf-8", errors="replace"
            )
            print(safe_line)
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════
# CONFIGURATION PERSISTANTE (%APPDATA%\TelegramTraderAgent\config.json)
# ═══════════════════════════════════════════════════════════════════════

def load_config():
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_config(config: dict) -> None:
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def clear_config() -> None:
    if CONFIG_FILE.exists():
        CONFIG_FILE.unlink()


# ═══════════════════════════════════════════════════════════════════════
# APPELS RÉSEAU
# ═══════════════════════════════════════════════════════════════════════

def http_get_json(url: str):
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        log(f"Erreur GET {url}: {e}")
        return None


def http_post_json(url: str, payload: dict):
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"}, method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        log(f"Erreur POST {url}: HTTP {e.code}")
        return None
    except Exception as e:
        log(f"Erreur POST {url}: {e}")
        return None


def pair_with_code(code: str):
    """Échange un code d'appairage (saisi par l'utilisateur) contre un token
    définitif. Retourne le dict {token, account_name} ou None si invalide."""
    return http_post_json(f"{API_BASE_URL}/nt8-agent/pair", {"code": code})


# ═══════════════════════════════════════════════════════════════════════
# LECTURE / ÉCRITURE DES FICHIERS NINJATRADER 8
# ═══════════════════════════════════════════════════════════════════════

def write_signal_file(signal: dict) -> None:
    try:
        # ── MODE DEBUG : journalise le payload brut REÇU du serveur avant
        # toute transformation, afin de diagnostiquer un éventuel problème
        # de contenu (ex: champs manquants) dès la réception du signal.
        if DEBUG_MODE:
            log(f"🐞 [DEBUG] Signal brut reçu du serveur : {json.dumps(signal, ensure_ascii=False)}")

        DOCS_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
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
        }
        with open(SIGNAL_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f)
        log(f"✅ Signal écrit dans {SIGNAL_FILE.name} : {payload['direction']} @ {payload['entry']} "
            f"(SL={payload['sl']} TP={payload['tp']} type={payload['order_type'] or 'défaut stratégie'})")
        if DEBUG_MODE:
            log(f"🐞 [DEBUG] Fichier signal complet écrit : {json.dumps(payload, ensure_ascii=False)}")
            log(f"🐞 [DEBUG] Chemin complet : {SIGNAL_FILE}")
        # On attend un court instant puis on vérifie si NinjaTrader a bien
        # traité le signal (statut écrit par la stratégie NinjaScript), pour
        # remonter immédiatement un diagnostic clair dans les logs plutôt
        # que de laisser l'utilisateur deviner pourquoi rien ne s'est passé.
        threading.Thread(target=_check_signal_processed, daemon=True).start()
    except Exception as e:
        log(f"❌ Erreur écriture signal : {e}")


def _check_signal_processed() -> None:
    """Attend quelques secondes après l'écriture d'un signal, puis lit
    nt8_last_signal_status.json (écrit par l'Add-On NinjaScript) pour
    savoir si le signal a été EXÉCUTÉ ou REJETÉ (et pourquoi). Ce mécanisme
    permet de diagnostiquer, DIRECTEMENT dans les logs de l'agent, le cas
    signalé par l'utilisateur : "j'ai exécuté... mais sur ninja trader rien"."""
    time.sleep(6)
    status = read_status_file()
    if status is None:
        log("⚠️  Aucun retour de NinjaTrader après l'envoi du signal (6s). "
            "Vérifiez que NinjaTrader 8 est bien ouvert et que l'Add-On "
            "TelegramTraderAddOn est compilé (Tools → Edit NinjaScript → F5). "
            "Le moteur démarre automatiquement à l'ouverture de NinjaTrader "
            "(aucun graphique requis).")
        return
    if status.get("status") == "executed":
        log(f"🏆 Confirmé par NinjaTrader : ordre exécuté ({status.get('extra', '')})")
    elif status.get("status") == "rejected":
        reason = status.get('reason', 'inconnue')
        hint = ""
        if reason == "tp_manquant":
            hint = " → Le TP (Take Profit) est obligatoire. Saisissez un TP > 0 dans le formulaire."
        elif reason == "sl_manquant":
            hint = " → Le SL (Stop Loss) est obligatoire. Saisissez un SL > 0 dans le formulaire."
        elif reason == "entry_manquant":
            hint = " → Le prix d'entrée est 0 et NinjaTrader n'a pas pu lire le prix du marché. Vérifiez l'instrument configuré dans l'Add-On."
        elif reason == "signal_perime":
            hint = " → Le signal a plus de 5 minutes. Envoyez un nouveau signal."
        elif "tp_buy_invalide" in reason or "tp_sell_invalide" in reason:
            hint = " → Le TP est du mauvais côté de l'entrée (BUY: TP > entrée, SELL: TP < entrée)."
        elif "sl_buy_invalide" in reason or "sl_sell_invalide" in reason:
            hint = " → Le SL est du mauvais côté de l'entrée (BUY: SL < entrée, SELL: SL > entrée)."
        log(f"❌ Signal REJETÉ par NinjaTrader — raison : {reason}.{hint} "
            "Consultez aussi la fenêtre 'NinjaScript Output' dans NinjaTrader pour plus de détails.")


def read_status_file():
    try:
        if STATUS_FILE.exists():
            with open(STATUS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return None


def read_price_file():
    try:
        if PRICE_FILE.exists():
            with open(PRICE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return None


def write_command_file(command: dict) -> None:
    try:
        if DEBUG_MODE:
            log(f"🐞 [DEBUG] Commande reçue du serveur : {json.dumps(command, ensure_ascii=False)}")
        DOCS_DIR.mkdir(parents=True, exist_ok=True)
        with open(COMMAND_FILE, "w", encoding="utf-8") as f:
            json.dump(command, f)
        log(f"✅ Commande écrite dans {COMMAND_FILE.name} : {command.get('action')}")
    except Exception as e:
        log(f"❌ Erreur écriture commande : {e}")


def read_accounts_status_file():
    """Lit nt8_accounts_status.json (écrit par le C# Add-On) et enrichit le
    résultat avec la liste des instruments détectés depuis nt8_current_price.json.
    Cela évite de modifier le C# (qui nécessite une recompilation dans NinjaTrader).
    Le champ 'instruments' est une liste de noms d'instruments NT8 (ex: ["MGC", "MNQ"]).
    """
    data = None
    try:
        if ACCOUNTS_STATUS_FILE.exists():
            with open(ACCOUNTS_STATUS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
    except Exception:
        pass

    # Enrichissement : ajouter les instruments depuis le fichier de prix
    # (nt8_current_price.json contient le champ "instrument" = Instrument.FullName)
    # On construit une liste dédupliquée d'instruments connus.
    if data is not None and not data.get("instruments"):
        instruments = []
        try:
            price_data = read_price_file()
            if price_data and price_data.get("instrument"):
                instr = price_data["instrument"].strip()
                if instr and instr not in instruments:
                    instruments.append(instr)
        except Exception:
            pass
        if instruments:
            data["instruments"] = instruments

    return data



def is_nt8_active() -> bool:
    """NinjaTrader est considéré 'actif' si nt8_current_price.json a été
    modifié récemment (preuve que la stratégie tourne bien sur un graphique)."""
    try:
        if PRICE_FILE.exists():
            age = time.time() - PRICE_FILE.stat().st_mtime
            return age < NT8_FRESHNESS_TIMEOUT_SEC
    except Exception:
        pass
    return False


# ═══════════════════════════════════════════════════════════════════════
# DÉMARRAGE AUTOMATIQUE AVEC WINDOWS (registre HKCU\...\Run)
# ═══════════════════════════════════════════════════════════════════════

def enable_windows_startup() -> None:
    if sys.platform != "win32":
        return
    try:
        import winreg
        exe_path = sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__)
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_SET_VALUE,
        )
        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, f'"{exe_path}"')
        winreg.CloseKey(key)
        log("Ajouté au démarrage automatique de Windows.")
    except Exception as e:
        log(f"Impossible d'activer le démarrage automatique : {e}")


# ═══════════════════════════════════════════════════════════════════════
# ÉTAT PARTAGÉ (thread réseau ↔ icône systray)
# ═══════════════════════════════════════════════════════════════════════

class AgentState:
    def __init__(self):
        self.token = None
        self.account_name = None
        self.connected = False  # dernière communication serveur OK
        self.nt8_active = False  # NinjaTrader détecté comme ouvert
        self.last_error = None
        self.running = True
        # Backoff exponentiel : nombre d'échecs réseau consécutifs
        self.consecutive_failures = 0
        # File locale : nombre de signaux en attente de rejeu
        self.offline_queue_size = 0


state = AgentState()


# ═══════════════════════════════════════════════════════════════════════
# FILE D'ATTENTE LOCALE PERSISTANTE (amélioration C)
# Stocke les signaux reçus offline pour les rejouer au retour du backend.
# ═══════════════════════════════════════════════════════════════════════

def load_offline_queue() -> list:
    """Charge la file locale de signaux en attente (persistée sur disque)."""
    try:
        if OFFLINE_QUEUE_FILE.exists():
            with open(OFFLINE_QUEUE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
    except Exception as e:
        log(f"⚠️  Impossible de lire la file offline : {e}")
    return []


def save_offline_queue(queue: list) -> None:
    """Persiste la file locale sur disque (survit à un redémarrage de l'agent)."""
    try:
        with open(OFFLINE_QUEUE_FILE, "w", encoding="utf-8") as f:
            json.dump(queue, f, ensure_ascii=False, indent=2)
        state.offline_queue_size = len(queue)
    except Exception as e:
        log(f"⚠️  Impossible de sauvegarder la file offline : {e}")


def enqueue_signal_offline(signal: dict) -> None:
    """Ajoute un signal à la file locale quand le backend est injoignable."""
    queue = load_offline_queue()
    signal["_offline_queued_at"] = time.time()
    queue.append(signal)
    save_offline_queue(queue)
    log(f"📦 Signal mis en file offline ({len(queue)} en attente) — sera rejoué dès reconnexion.")


def replay_offline_queue() -> int:
    """Rejoue les signaux stockés localement dès que le backend est à nouveau
    joignable. Retourne le nombre de signaux rejoués avec succès."""
    queue = load_offline_queue()
    if not queue:
        return 0

    log(f"🔄 Rejeu de {len(queue)} signal(s) stocké(s) offline...")
    replayed = 0
    remaining = []

    for signal in queue:
        # On retire le champ interne avant d'écrire le fichier NT8
        signal.pop("_offline_queued_at", None)
        try:
            write_signal_file(signal)
            replayed += 1
            log(f"✅ Signal offline rejoué : {signal.get('type', '?')} @ {signal.get('entry_price', '?')}")
        except Exception as e:
            log(f"❌ Échec du rejeu d'un signal offline : {e} — signal conservé pour la prochaine tentative.")
            remaining.append(signal)

    save_offline_queue(remaining)
    if replayed:
        log(f"✅ {replayed} signal(s) offline rejoué(s) avec succès.")
    return replayed


# ═══════════════════════════════════════════════════════════════════════
# BACKOFF EXPONENTIEL (amélioration B)
# Calcule le délai d'attente en fonction du nombre d'échecs consécutifs.
# ═══════════════════════════════════════════════════════════════════════

def compute_backoff_delay() -> float:
    """Retourne le délai d'attente (en secondes) selon le nombre d'échecs
    consécutifs : BACKOFF_MIN_SEC × BACKOFF_FACTOR^n, plafonné à BACKOFF_MAX_SEC."""
    if state.consecutive_failures == 0:
        return BACKOFF_MIN_SEC
    delay = BACKOFF_MIN_SEC * (BACKOFF_FACTOR ** state.consecutive_failures)
    return min(delay, BACKOFF_MAX_SEC)


def on_network_success() -> None:
    """Appelé après chaque appel réseau réussi : réinitialise le compteur
    d'échecs et remet l'intervalle de polling à sa valeur normale."""
    if state.consecutive_failures > 0:
        log(f"✅ Connexion rétablie après {state.consecutive_failures} échec(s) — retour au polling normal.")
        state.consecutive_failures = 0
    state.connected = True


def on_network_failure(reason: str = "") -> None:
    """Appelé après chaque échec réseau : incrémente le compteur et calcule
    le prochain délai de backoff."""
    state.consecutive_failures += 1
    state.connected = False
    delay = compute_backoff_delay()
    log(f"⚠️  Serveur injoignable ({reason}) — échec #{state.consecutive_failures}, "
        f"prochaine tentative dans {delay:.0f}s.")


# ═══════════════════════════════════════════════════════════════════════
# BOUCLE PRINCIPALE (polling + heartbeat), tourne dans un thread séparé
# ═══════════════════════════════════════════════════════════════════════

def worker_loop():
    last_heartbeat = 0
    log("Boucle de polling démarrée.")

    # Vérifier s'il reste des signaux offline d'une session précédente
    pending = load_offline_queue()
    if pending:
        log(f"📦 {len(pending)} signal(s) offline trouvé(s) depuis la dernière session — "
            "ils seront rejoués dès que le serveur sera joignable.")
        state.offline_queue_size = len(pending)

    while state.running:
        try:
            if not state.token:
                time.sleep(1)
                continue

            # ── Calcul du délai de polling selon l'état de la connexion ──
            # En mode backoff, on attend plus longtemps entre les tentatives
            # pour ne pas saturer le réseau ni les logs.
            current_delay = compute_backoff_delay()

            # ── Poll des signaux ─────────────────────────────────────────
            result = http_get_json(f"{API_BASE_URL}/nt8-agent/poll?token={state.token}")

            if result is not None:
                # Connexion rétablie : rejouer d'abord les signaux offline
                # AVANT de traiter les nouveaux (respect de l'ordre chronologique)
                if state.consecutive_failures > 0:
                    on_network_success()
                    replay_offline_queue()
                else:
                    on_network_success()

                if result.get("signals"):
                    for signal in result["signals"]:
                        write_signal_file(signal)
            else:
                # Backend injoignable : on ne perd pas les signaux déjà reçus
                # (ils sont déjà dans la file offline s'ils y ont été mis)
                on_network_failure("poll")

            # ── Poll des commandes (seulement si connecté) ───────────────
            if state.connected:
                cmd_result = http_get_json(f"{API_BASE_URL}/nt8-agent/poll-commands?token={state.token}")
                if cmd_result and cmd_result.get("commands"):
                    for command in cmd_result["commands"]:
                        write_command_file(command)

            # ── Heartbeat (seulement si connecté) ────────────────────────
            now = time.time()
            if state.connected and now - last_heartbeat >= HEARTBEAT_INTERVAL_SEC:
                price_info = read_price_file()
                accounts_info = read_accounts_status_file()
                hb = http_post_json(
                    f"{API_BASE_URL}/nt8-agent/heartbeat",
                    {"token": state.token, "price_info": price_info, "accounts_info": accounts_info},
                )
                if hb is not None:
                    state.nt8_active = is_nt8_active()
                    last_heartbeat = now
                else:
                    on_network_failure("heartbeat")

            time.sleep(current_delay)

        except Exception as e:
            state.last_error = str(e)
            log(f"Erreur inattendue dans la boucle : {e}")
            on_network_failure(str(e))
            time.sleep(compute_backoff_delay())


# ═══════════════════════════════════════════════════════════════════════
# FENÊTRE DE SAISIE DU CODE D'APPAIRAGE (Tkinter — inclus en standard)
# ═══════════════════════════════════════════════════════════════════════

def ask_pairing_code(prefill_error: str = None) -> str:
    import tkinter as tk
    from tkinter import messagebox

    result = {"code": None}

    root = tk.Tk()
    root.title("TelegramTrader — Connexion de l'agent")
    root.geometry("420x220")
    root.resizable(False, False)

    tk.Label(
        root,
        text="Connexion de l'agent NinjaTrader 8",
        font=("Segoe UI", 12, "bold"),
        pady=10,
    ).pack()

    tk.Label(
        root,
        text=(
            "Sur le site TelegramTrader, allez dans\n"
            "Paramètres → Agent local → « Générer un code d'appairage »\n"
            "puis saisissez ce code ci-dessous :"
        ),
        justify="center",
    ).pack(pady=(0, 10))

    if prefill_error:
        tk.Label(root, text=prefill_error, fg="red").pack()

    entry = tk.Entry(root, font=("Segoe UI", 16), justify="center", width=12)
    entry.pack(pady=5)
    entry.focus()

    def submit():
        code = entry.get().strip()
        if not code:
            messagebox.showwarning("Code manquant", "Merci de saisir votre code d'appairage.")
            return
        result["code"] = code
        root.destroy()

    def open_site():
        webbrowser.open(API_BASE_URL.replace("/api", ""))

    btn_frame = tk.Frame(root)
    btn_frame.pack(pady=10)
    tk.Button(btn_frame, text="Ouvrir le site", command=open_site).pack(side="left", padx=5)
    tk.Button(btn_frame, text="Valider", command=submit, bg="#16a34a", fg="white").pack(side="left", padx=5)

    root.bind("<Return>", lambda e: submit())
    root.mainloop()
    return result["code"]


def run_pairing_flow():
    """Boucle jusqu'à obtenir un code valide, puis sauvegarde le token."""
    error = None
    while state.running and not state.token:
        code = ask_pairing_code(prefill_error=error)
        if not code:
            # Utilisateur a fermé la fenêtre → on quitte proprement
            state.running = False
            os._exit(0)
        pairing = pair_with_code(code)
        if pairing and pairing.get("token"):
            state.token = pairing["token"]
            state.account_name = pairing.get("account_name", "")
            save_config({"token": state.token, "account_name": state.account_name})
            log(f"Appairage réussi pour le compte : {state.account_name or '(sans nom)'}")
            return
        error = "❌ Code invalide ou expiré, réessayez."


# ═══════════════════════════════════════════════════════════════════════
# ICÔNE DE BARRE SYSTÈME (pystray)
# ═══════════════════════════════════════════════════════════════════════

def build_icon_image(color: str):
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (64, 64), "white")
    draw = ImageDraw.Draw(img)
    draw.ellipse((8, 8, 56, 56), fill=color)
    draw.text((22, 20), "T", fill="white")
    return img


def run_tray_icon():
    import pystray
    from pystray import MenuItem as Item

    def get_icon_image():
        if state.connected and state.nt8_active:
            return build_icon_image("#16a34a")  # vert : tout va bien
        if state.connected:
            return build_icon_image("#eab308")  # orange : connecté, NT8 fermé
        return build_icon_image("#dc2626")  # rouge : déconnecté

    def get_status_text():
        if state.connected and state.nt8_active:
            return "TelegramTrader — Connecté ✅ (NinjaTrader actif)"
        if state.connected:
            return "TelegramTrader — Connecté, en attente de NinjaTrader..."
        if state.consecutive_failures > 0:
            delay = compute_backoff_delay()
            return f"TelegramTrader — Reconnexion dans {delay:.0f}s (échec #{state.consecutive_failures})"
        return "TelegramTrader — Déconnecté du serveur"

    def on_show_status(icon, item):
        import tkinter as tk
        from tkinter import messagebox

        # ── MODE DEBUG : on inclut le résultat du DERNIER signal traité par
        # NinjaTrader (exécuté/rejeté + raison), lu depuis
        # nt8_last_signal_status.json, afin que l'utilisateur puisse
        # diagnostiquer directement depuis ce menu pourquoi un signal ne
        # s'est pas exécuté, sans avoir à ouvrir agent.log ni la fenêtre
        # "NinjaScript Output" de NinjaTrader.
        last_signal_txt = "Aucun signal traité récemment."
        status = read_status_file()
        if status:
            ts = status.get("timestamp", "?")
            if status.get("status") == "executed":
                last_signal_txt = (
                    f"✅ Dernier signal EXÉCUTÉ ({ts})\n"
                    f"Détails : {status.get('extra', '')}"
                )
            elif status.get("status") == "rejected":
                last_signal_txt = (
                    f"❌ Dernier signal REJETÉ ({ts})\n"
                    f"Raison : {status.get('reason', 'inconnue')}"
                )

        # Infos sur la file offline et le backoff
        offline_info = ""
        if state.offline_queue_size > 0:
            offline_info = f"\n\n📦 File offline : {state.offline_queue_size} signal(s) en attente de rejeu"
        backoff_info = ""
        if state.consecutive_failures > 0:
            backoff_info = (
                f"\n⏳ Backoff actif : {state.consecutive_failures} échec(s) consécutif(s), "
                f"prochaine tentative dans {compute_backoff_delay():.0f}s"
            )

        messagebox.showinfo(
            "Statut TelegramTrader Agent",
            get_status_text() +
            f"\n\nCompte : {state.account_name or '—'}" +
            f"\nDernière erreur : {state.last_error or 'aucune'}" +
            backoff_info +
            offline_info +
            f"\n\n— Dernier signal NinjaTrader —\n{last_signal_txt}" +
            f"\n\n🐞 Mode debug : {'ACTIVÉ' if DEBUG_MODE else 'désactivé'} "
            "(voir 'Ouvrir les logs' pour le détail complet)"
        )

    def on_open_logs(icon, item):
        try:
            os.startfile(str(LOG_FILE))
        except Exception:
            webbrowser.open(str(APPDATA_DIR))

    def on_disconnect(icon, item):
        clear_config()
        state.token = None
        state.connected = False
        icon.stop()
        os._exit(0)

    def on_quit(icon, item):
        state.running = False
        icon.stop()
        os._exit(0)

    icon = pystray.Icon(
        APP_NAME,
        build_icon_image("#dc2626"),
        "TelegramTrader Agent",
        menu=pystray.Menu(
            Item(lambda item: get_status_text(), on_show_status, enabled=False),
            pystray.Menu.SEPARATOR,
            Item("Voir le statut détaillé", on_show_status),
            Item("Ouvrir les logs", on_open_logs),
            pystray.Menu.SEPARATOR,
            Item("Se déconnecter (changer de compte)", on_disconnect),
            Item("Quitter", on_quit),
        ),
    )

    def refresh_loop(icon):
        while state.running:
            icon.icon = get_icon_image()
            icon.title = get_status_text()
            time.sleep(3)

    icon.run(setup=lambda icon: threading.Thread(target=refresh_loop, args=(icon,), daemon=True).start())


# ═══════════════════════════════════════════════════════════════════════
# POINT D'ENTRÉE
# ═══════════════════════════════════════════════════════════════════════

def main():
    log("═" * 60)
    log(f"Démarrage de {APP_NAME} — Serveur : {API_BASE_URL}")

    config = load_config()
    if config.get("token"):
        state.token = config["token"]
        state.account_name = config.get("account_name", "")
        log(f"Session existante restaurée pour : {state.account_name or '(sans nom)'}")
    else:
        run_pairing_flow()

    enable_windows_startup()

    threading.Thread(target=worker_loop, daemon=True).start()
    run_tray_icon()


if __name__ == "__main__":
    main()

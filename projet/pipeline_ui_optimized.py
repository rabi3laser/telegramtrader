"""
INTERFACE WEB OPTIMISÉE - PIPELINE MULTI-MARCHÉS
Interface Streamlit simplifiée pour utilisateurs normaux

Workflow:
0. Connexion Telegram
1. Accueil : Mes Canaux (déjà calibrés) OU Recherche nouveaux canaux
2. Recherche légère (sans OCR)
3. Sélection manuelle
4. Calibration (sur la machine de l'utilisateur via sa session Telegram)
5. Résultats + Sauvegarde dans calibration_history.json

Usage:
    streamlit run pipeline_ui_optimized.py
"""
import streamlit as st
import json
from pathlib import Path
from datetime import datetime
import pandas as pd
import asyncio
from telegram_search import search_telegram_channels, search_custom_market, get_joined_channels
from telegram_calibrator import calibrate_channels_batch, join_and_calibrate_single
from telegram_authenticator import show_auth_page
from price_reference import show_nt8_price_reference_section, load_price_references, calculate_real_winrate
from pathlib import Path

# ═══════════════════════════════════════════════════════════════
# CONFIGURATION DE LA PAGE
# ═══════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="Pipeline Trading",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        text-align: center;
        padding: 1.5rem;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-radius: 10px;
        margin-bottom: 2rem;
    }
    .channel-card {
        background-color: white;
        padding: 1rem;
        border-radius: 8px;
        border: 1px solid #e0e0e0;
        margin: 0.5rem 0;
    }
    .winrate-good { color: #28a745; font-weight: bold; font-size: 1.2rem; }
    .winrate-medium { color: #ffc107; font-weight: bold; font-size: 1.2rem; }
    .winrate-bad { color: #dc3545; font-weight: bold; font-size: 1.2rem; }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header">🚀 PIPELINE TRADING - INTERFACE SIMPLIFIÉE</div>', unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
# CONSTANTES
# ═══════════════════════════════════════════════════════════════

MARKETS = {
    "gold_mgc":   {"name": "Gold (MGC)",      "icon": "🥇"},
    "mnq_nasdaq": {"name": "Nasdaq (MNQ)",     "icon": "📊"},
    "mcl_crude":  {"name": "Crude Oil (MCL)",  "icon": "🛢️"},
    "mes_sp500":  {"name": "S&P 500 (MES)",    "icon": "📈"},
    "custom":     {"name": "Personnalisé",     "icon": "🔍"},
}

# Chemin du fichier de persistance (dans le répertoire du projet)
HISTORY_FILE = Path(__file__).parent / "calibration_history.json"

# ═══════════════════════════════════════════════════════════════
# FONCTIONS DE PERSISTANCE
# ═══════════════════════════════════════════════════════════════

def load_history() -> dict:
    """Charge l'historique de calibration depuis le fichier JSON."""
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("channels", {})
        except Exception:
            return {}
    return {}


def save_history(channels: dict):
    """Sauvegarde l'historique de calibration dans le fichier JSON."""
    try:
        data = {"channels": channels, "last_updated": datetime.now().isoformat()}
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        st.error(f"❌ Erreur sauvegarde: {e}")
        return False


def add_channels_to_history(calibration_results: dict):
    """Ajoute les résultats de calibration à l'historique (batch)."""
    history = load_history()
    now = datetime.now().isoformat()
    for status in ["activated", "short_test", "rejected"]:
        for ch in calibration_results.get(status, []):
            save_single_channel(ch, history, now)
    save_history(history)
    return history


def save_single_channel(ch: dict, history: dict = None, now: str = None):
    """Sauvegarde un seul canal dans l'historique (sauvegarde progressive)."""
    if history is None:
        history = load_history()
    if now is None:
        now = datetime.now().isoformat()
    username = ch.get("username", "")
    if not username:
        return history
    # Si une demande d'adhésion est en attente, statut spécial "pending_approval"
    computed_status = ch.get("status", "rejected")
    if ch.get("action_needed") == "wait_approval":
        computed_status = "pending_approval"

    history[username] = {
        "username": username,
        "title": ch.get("title", username),
        "market": ch.get("market", "custom"),
        "status": computed_status,
        "score": ch.get("score", 0),
        "winrate": ch.get("winrate", ch.get("score", 0)),
        "signals_count": ch.get("signals_count", 0),
        "metrics": ch.get("metrics", {}),
        "members": ch.get("members", 0),
        "description": ch.get("description", ""),
        "reason": ch.get("reason", ""),
        "action_needed": ch.get("action_needed", ""),
        "date_calibration": ch.get("date_calibration", now),
        "channel_id": ch.get("channel_id", ch.get("id", "")),
    }
    save_history(history)
    return history


def winrate_freshness(date_calibration_str: str) -> tuple:
    """Retourne (label, couleur) selon la fraîcheur du winrate."""
    if not date_calibration_str:
        return "❓ Jamais calibré", "gray"
    try:
        dt = datetime.fromisoformat(date_calibration_str)
        hours = (datetime.now() - dt).total_seconds() / 3600
        if hours < 6:
            return f"🟢 Frais ({int(hours)}h)", "green"
        elif hours < 24:
            return f"🟡 Récent ({int(hours)}h)", "orange"
        elif hours < 72:
            return f"🟠 Vieux ({int(hours/24)}j)", "orange"
        else:
            return f"🔴 Obsolète ({int(hours/24)}j) — Recalibrer", "red"
    except Exception:
        return "❓ Date inconnue", "gray"


def remove_channel_from_history(username: str):
    """Supprime un canal de l'historique."""
    history = load_history()
    if username in history:
        del history[username]
        save_history(history)
    return history

# ═══════════════════════════════════════════════════════════════
# INITIALISATION SESSION STATE
# ═══════════════════════════════════════════════════════════════

defaults = {
    "current_step": 0,
    "search_results": {},
    "selected_channels": {},
    "pro_mode": False,
    "calibration_results": None,
    "my_channels_loaded": False,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ═══════════════════════════════════════════════════════════════
# SIDEBAR - NAVIGATION
# ═══════════════════════════════════════════════════════════════

with st.sidebar:
    st.title("📋 Navigation")

    st.session_state.pro_mode = st.toggle("🔧 Mode Pro", value=st.session_state.pro_mode)
    if st.session_state.pro_mode:
        st.info("Mode Pro activé")

    st.divider()

    step_labels = {
        0: "🔑 Connexion",
        1: "🏠 Accueil",
        2: "🔍 Recherche",
        3: "✅ Sélection",
        4: "⚙️ Calibration",
        5: "🚀 Résultats",
    }
    for i, label in step_labels.items():
        if i == st.session_state.current_step:
            st.markdown(f"**➡️ {label}**")
        elif i < st.session_state.current_step:
            st.markdown(f"✅ {label}")
        else:
            st.markdown(f"⚪ {label}")

    st.divider()

    # Bouton déconnexion dans la sidebar (disponible partout sauf étape 0)
    if st.session_state.current_step > 0:
        if st.button("🔑 Déconnexion", use_container_width=True):
            from telegram_authenticator import _logout
            _logout()
            st.session_state.current_step = 0
            st.rerun()

    st.caption(f"🕐 {datetime.now().strftime('%H:%M:%S')}")
    st.caption("Version 3.0 - Mes Canaux + Persistance")

# ═══════════════════════════════════════════════════════════════
# ÉTAPE 0 : CONNEXION TELEGRAM
# ═══════════════════════════════════════════════════════════════

if st.session_state.current_step == 0:
    if show_auth_page():
        st.session_state.current_step = 1
        st.rerun()

# ═══════════════════════════════════════════════════════════════
# ÉTAPE 1 : ACCUEIL - MES CANAUX + OPTION RECHERCHE
# ═══════════════════════════════════════════════════════════════

elif st.session_state.current_step == 1:
    st.header("🏠 Accueil")

    # Charger l'historique
    history = load_history()

    # ── Section "Mes Canaux" ──────────────────────────────────
    st.subheader(f"📚 Mes Canaux ({len(history)} canal(aux) calibré(s))")

    if history:
        # Grouper par statut
        activated   = {u: c for u, c in history.items() if c["status"] == "activated"}
        short_test  = {u: c for u, c in history.items() if c["status"] == "short_test"}
        pending     = {u: c for u, c in history.items() if c["status"] == "pending_approval"}
        rejected    = {u: c for u, c in history.items() if c["status"] == "rejected"}

        # ── Canaux Activés ──
        if activated:
            st.markdown("### ✅ Canaux Activés")
            for username, ch in activated.items():
                market_info = MARKETS.get(ch.get("market", "custom"), MARKETS["custom"])
                with st.expander(
                    f"{market_info['icon']} {ch['title']}  —  Score: {ch.get('score', '?')}/100",
                    expanded=True
                ):
                    col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
                    with col1:
                        score = ch.get("score", 0)
                        color = "winrate-good" if score >= 70 else ("winrate-medium" if score >= 50 else "winrate-bad")
                        st.markdown(f'<span class="{color}">Score: {score}/100</span>', unsafe_allow_html=True)
                        st.caption("⚠️ Score texte — pas un vrai winrate")
                    with col2:
                        st.metric("Signaux texte", ch.get("signals_count", "?"))
                    with col3:
                        date_str = ch.get("date_calibration", "")[:10] if ch.get("date_calibration") else "?"
                        freshness, _ = winrate_freshness(ch.get("date_calibration", ""))
                        st.caption(f"@{username}")
                        st.caption(f"Calibré le: {date_str}")
                        st.caption(freshness)
                    with col4:
                        if st.button("🗑️", key=f"del_{username}", help="Supprimer"):
                            remove_channel_from_history(username)
                            st.rerun()

                    # Métriques détaillées
                    metrics = ch.get("metrics", {})
                    if metrics:
                        with st.expander("📊 Métriques détaillées"):
                            m1, m2, m3, m4 = st.columns(4)
                            m1.metric("Messages analysés", metrics.get("total_messages", "?"))
                            m2.metric("Signaux détectés", metrics.get("total_signals", "?"))
                            m3.metric("Signaux/jour", metrics.get("signals_per_day", "?"))
                            m4.metric("Qualité moy.", f"{metrics.get('avg_quality', '?')}/10")

                    # Bouton recalibrer
                    if st.button("🔄 Recalibrer ce canal", key=f"recal_{username}"):
                        st.session_state.selected_channels = {
                            ch.get("market", "custom"): [ch]
                        }
                        st.session_state.calibration_results = None
                        st.session_state.current_step = 4
                        st.rerun()

        # ── Canaux en Test ──
        if short_test:
            st.markdown("### ⏳ Canaux en Test Court")
            for username, ch in short_test.items():
                market_info = MARKETS.get(ch.get("market", "custom"), MARKETS["custom"])
                col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
                with col1:
                    st.write(f"{market_info['icon']} **{ch['title']}**")
                    st.caption(f"@{username}")
                with col2:
                    st.metric("Score", f"{ch.get('score', '?')}/100")
                with col3:
                    date_str = ch.get("date_calibration", "")[:10] if ch.get("date_calibration") else "?"
                    st.caption(f"Calibré le: {date_str}")
                with col4:
                    if st.button("🗑️", key=f"del_{username}", help="Supprimer"):
                        remove_channel_from_history(username)
                        st.rerun()

        # ── Canaux en attente d'approbation ──
        if pending:
            st.markdown("### 📨 En Attente d'Approbation")
            st.caption("Demande d'adhésion envoyée à l'admin du canal — cliquez sur 'Vérifier' périodiquement.")
            for username, ch in pending.items():
                market_info = MARKETS.get(ch.get("market", "custom"), MARKETS["custom"])
                col1, col2, col3, col4 = st.columns([3, 3, 1, 1])
                with col1:
                    st.write(f"{market_info['icon']} **{ch['title']}**")
                    st.caption(f"@{username}")
                with col2:
                    date_str = ch.get("date_calibration", "")
                    try:
                        dt = datetime.fromisoformat(date_str)
                        elapsed = (datetime.now() - dt).total_seconds() / 3600
                        st.caption(f"📨 Demande envoyée il y a {int(elapsed)}h")
                    except Exception:
                        st.caption("📨 Demande d'adhésion en attente")
                with col3:
                    if st.button("🔍 Vérifier", key=f"check_{username}", help="Vérifier si l'admin a accepté"):
                        with st.spinner(f"Vérification de {ch['title']}..."):
                            try:
                                result = asyncio.run(join_and_calibrate_single(ch))
                                save_single_channel(result)
                                if result.get('status') not in ('rejected',):
                                    st.success(f"🎉 Accepté ! Calibré — Score: {result.get('score', 0)}/100")
                                elif result.get('action_needed') == 'wait_approval':
                                    st.info("⏳ Toujours en attente d'approbation de l'admin")
                                else:
                                    st.warning(f"⚠️ {result.get('reason', 'Statut inchangé')}")
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Erreur: {e}")
                with col4:
                    if st.button("🗑️", key=f"del_{username}", help="Abandonner"):
                        remove_channel_from_history(username)
                        st.rerun()
            st.divider()

        # ── Canaux Rejetés ──
        if rejected:
            with st.expander(f"❌ Canaux Rejetés ({len(rejected)})", expanded=False):
                for username, ch in rejected.items():
                    market_info = MARKETS.get(ch.get("market", "custom"), MARKETS["custom"])
                    reason = ch.get("reason", "")
                    needs_join = any(kw in reason for kw in ["🔒", "📨", "privé", "PRIVÉ", "rejoign", "adhésion", "Rejoign"])
                    col1, col2, col3, col4, col5 = st.columns([3, 2, 3, 1, 1])
                    with col1:
                        st.write(f"{market_info['icon']} **{ch['title']}**")
                        st.caption(f"@{username}")
                    with col2:
                        st.metric("Score", f"{ch.get('score', '?')}/100")
                    with col3:
                        metrics = ch.get("metrics", {})
                        if reason:
                            st.caption(f"❌ {reason[:80]}")
                        if metrics:
                            st.caption(f"📊 {metrics.get('total_signals', 0)} signaux | qualité: {metrics.get('avg_quality', 0)}/10")
                    with col4:
                        if needs_join:
                            if st.button("🔄", key=f"join_{username}", help="Rejoindre & Recalibrer"):
                                with st.spinner(f"Tentative de rejoindre {ch['title']}..."):
                                    try:
                                        result = asyncio.run(join_and_calibrate_single(ch))
                                        save_single_channel(result)
                                        if result.get('status') != 'rejected':
                                            st.success(f"✅ Rejoint et calibré ! Score: {result.get('score', 0)}/100")
                                        elif result.get('action_needed') == 'wait_approval':
                                            st.info("📨 Demande envoyée — voir section 'En Attente d'Approbation'")
                                        else:
                                            st.warning(f"⚠️ {result.get('reason', 'Toujours impossible')}")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"❌ Erreur: {e}")
                    with col5:
                        if st.button("🗑️", key=f"del_{username}", help="Supprimer"):
                            remove_channel_from_history(username)
                            st.rerun()

        st.divider()

        # Export / Import JSON
        col_exp, col_imp = st.columns(2)
        with col_exp:
            json_str = json.dumps({"channels": history}, ensure_ascii=False, indent=2)
            st.download_button(
                "📥 Exporter mes canaux (JSON)",
                json_str,
                "mes_canaux.json",
                "application/json",
                use_container_width=True
            )
        with col_imp:
            uploaded = st.file_uploader("📤 Importer canaux (JSON)", type="json", key="import_json")
            if uploaded:
                try:
                    imported = json.load(uploaded)
                    imported_channels = imported.get("channels", {})
                    merged = {**history, **imported_channels}
                    save_history(merged)
                    st.success(f"✅ {len(imported_channels)} canaux importés!")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Erreur import: {e}")

    else:
        st.info("📭 Aucun canal calibré pour l'instant. Lancez une recherche pour en trouver !")

    st.divider()

    # ── Section "Mes Abonnements Telegram" ───────────────────
    st.subheader("📡 Mes Abonnements Telegram")
    st.caption("Canaux Telegram auxquels vous êtes déjà abonné — calibrez-les directement.")

    col_load, col_info = st.columns([2, 3])
    with col_load:
        if st.button("📡 CHARGER MES ABONNEMENTS", use_container_width=True):
            with st.spinner("Chargement de vos canaux Telegram..."):
                try:
                    joined = asyncio.run(get_joined_channels())
                    st.session_state.joined_channels = joined
                    st.success(f"✅ {len(joined)} canaux trouvés dans vos abonnements")
                except Exception as e:
                    st.error(f"❌ Erreur: {str(e)}")
    with col_info:
        st.info("💡 Ces canaux sont déjà dans votre Telegram — vous pouvez les calibrer sans les rejoindre.")

    # Afficher les abonnements chargés
    if st.session_state.get("joined_channels"):
        joined = st.session_state.joined_channels
        history = load_history()

        st.write(f"**{len(joined)} canaux** — Cochez ceux à calibrer:")
        selected_joined = []
        for idx, ch in enumerate(joined):
            already = ch["username"] in history
            col1, col2, col3 = st.columns([1, 4, 2])
            with col1:
                sel = st.checkbox("✓", key=f"joined_{idx}", label_visibility="collapsed", disabled=already)
                if sel and not already:
                    selected_joined.append(ch)
            with col2:
                st.write(f"**{ch['title']}**")
                st.caption(f"@{ch['username']}")
                if already:
                    saved = history[ch["username"]]
                    status_icon = {"activated": "✅", "short_test": "⏳", "rejected": "❌"}.get(saved.get("status", ""), "❓")
                    st.caption(f"📌 Déjà calibré {status_icon} — Score: {saved.get('score', '?')}/100")
            with col3:
                st.metric("Membres", f"{ch.get('members', 0):,}" if ch.get('members') else "?")

        if selected_joined:
            st.success(f"✅ {len(selected_joined)} canal(aux) sélectionné(s)")
            if st.button("⚙️ CALIBRER MES ABONNEMENTS SÉLECTIONNÉS", type="primary", use_container_width=True):
                # Assigner le marché "custom" par défaut
                for ch in selected_joined:
                    ch["market"] = "custom"
                st.session_state.selected_channels = {"custom": selected_joined}
                st.session_state.calibration_results = None
                st.session_state.current_step = 4
                st.rerun()

    st.divider()

    # ── Section Repères de Prix NT8 ───────────────────────────
    with st.expander("📸 Repères de Prix NinjaTrader (pour calcul Winrate réel)", expanded=False):

        # ── Téléchargement de l'indicateur NT8 ───────────────
        st.subheader("🔧 Indicateur NinjaTrader 8 - CalibrationPanel")
        st.caption("Installez cet indicateur sur NT8 pour afficher un panneau OHLC complet sur vos charts.")

        indicator_file = Path(__file__).parent / "CalibrationPanel.cs"
        guide_file = Path(__file__).parent / "GUIDE_CALIBRATION_PANEL.md"

        col_dl1, col_dl2 = st.columns(2)
        with col_dl1:
            if indicator_file.exists():
                with open(indicator_file, "r", encoding="utf-8") as f:
                    cs_content = f.read()
                st.download_button(
                    "📥 Télécharger CalibrationPanel.cs",
                    cs_content,
                    "CalibrationPanel.cs",
                    "text/plain",
                    use_container_width=True,
                    help="Copiez ce fichier dans Documents/NinjaTrader 8/bin/Custom/Indicators/"
                )
            else:
                st.warning("⚠️ Fichier CalibrationPanel.cs non trouvé")

        with col_dl2:
            if guide_file.exists():
                with open(guide_file, "r", encoding="utf-8") as f:
                    guide_content = f.read()
                st.download_button(
                    "📖 Télécharger le Guide d'installation",
                    guide_content,
                    "GUIDE_CALIBRATION_PANEL.md",
                    "text/markdown",
                    use_container_width=True,
                    help="Guide complet d'installation et d'utilisation"
                )

        with st.expander("📋 Instructions rapides d'installation", expanded=False):
            st.markdown("""
**1. Téléchargez** `CalibrationPanel.cs` ci-dessus

**2. Copiez** le fichier dans :
```
C:\\Users\\[Votre Nom]\\Documents\\NinjaTrader 8\\bin\\Custom\\Indicators\\
```

**3. Compilez** dans NinjaTrader :
- Menu : **Tools → Edit NinjaScript → Compile** (ou `F5`)

**4. Ajoutez** sur un chart :
- Clic droit sur le chart → **Indicators → CalibrationPanel → Add**

**5. Capturez** et uploadez ci-dessous pour le winrate réel 📸
""")

        st.divider()
        show_nt8_price_reference_section()

        # Afficher le winrate réel si des références existent
        price_refs = load_price_references()
        if price_refs and history:
            st.divider()
            st.write("**📊 Winrate Réel calculé depuis vos références NT8**")
            for username, ch in {**{u: c for u, c in history.items() if c["status"] == "activated"},
                                  **{u: c for u, c in history.items() if c["status"] == "short_test"}}.items():
                market = ch.get("market", "custom")
                signals = ch.get("metrics", {}).get("signals_sample", [])
                if not signals:
                    signals = [{"entry_price": None, "tp_price": None, "sl_price": None}] * ch.get("signals_count", 0)
                wr_result = calculate_real_winrate(signals, price_refs, market)
                if wr_result.get("winrate") is not None:
                    wr = wr_result["winrate"]
                    color = "🟢" if wr >= 60 else ("🟡" if wr >= 50 else "🔴")
                    st.write(f"{color} **{ch['title']}** : Winrate réel = **{wr}%** "
                             f"({wr_result['trades_won']}/{wr_result['trades_won']+wr_result['trades_lost']} trades)")

    st.divider()

    # ── Bouton Recherche Nouveaux Canaux ──────────────────────
    st.subheader("🔍 Rechercher de Nouveaux Canaux")
    st.caption("Trouvez de nouveaux canaux Telegram et calibrez-les pour les ajouter à votre liste.")

    if st.button("🔍 LANCER UNE NOUVELLE RECHERCHE", type="primary", use_container_width=True):
        st.session_state.search_results = {}
        st.session_state.selected_channels = {}
        st.session_state.calibration_results = None
        st.session_state.current_step = 2
        st.rerun()

# ═══════════════════════════════════════════════════════════════
# ÉTAPE 2 : RECHERCHE DE NOUVEAUX CANAUX
# ═══════════════════════════════════════════════════════════════

elif st.session_state.current_step == 2:
    st.header("🔍 Étape 2: Recherche de Nouveaux Canaux")

    # Bouton retour
    if st.button("⬅️ Retour à l'accueil"):
        st.session_state.current_step = 1
        st.rerun()

    st.info("💡 Recherche rapide sans OCR - Seulement les informations de base")

    # Mode de recherche
    search_mode = st.radio(
        "Mode de recherche",
        ["Marchés prédéfinis", "Recherche personnalisée"],
        horizontal=True
    )

    if search_mode == "Marchés prédéfinis":
        col1, col2 = st.columns([2, 1])
        with col1:
            selected_market = st.selectbox(
                "Choisissez un marché",
                options=[k for k in MARKETS.keys() if k != "custom"],
                format_func=lambda x: f"{MARKETS[x]['icon']} {MARKETS[x]['name']}"
            )
        with col2:
            max_results = st.number_input("Nombre de résultats", 5, 50, 20, 5)
        custom_keywords = None
    else:
        st.info("🔍 Recherchez n'importe quel marché avec vos propres mots-clés")
        col1, col2 = st.columns([2, 1])
        with col1:
            custom_keywords = st.text_area(
                "Mots-clés de recherche (un par ligne)",
                value="bitcoin\nBTC\ncrypto signals\nbitcoin trading",
                height=150,
            )
        with col2:
            max_results = st.number_input("Nombre de résultats", 5, 50, 20, 5)
        selected_market = "custom"

    # Paramètres Pro
    if st.session_state.pro_mode:
        with st.expander("🔧 Paramètres Avancés de Recherche"):
            col1, col2 = st.columns(2)
            with col1:
                min_members = st.number_input("Membres minimum", 100, 10000, 1000, 100)
                max_members = st.number_input("Membres maximum", 10000, 1000000, 50000, 5000)

    # Bouton de recherche
    if st.button("🔍 LANCER LA RECHERCHE", type="primary", use_container_width=True):
        with st.spinner("🔍 Recherche en cours sur Telegram..."):
            try:
                if search_mode == "Recherche personnalisée" and custom_keywords:
                    keywords_list = [k.strip() for k in custom_keywords.split('\n') if k.strip()]
                    results = asyncio.run(search_custom_market(keywords_list, max_results))
                else:
                    results = asyncio.run(search_telegram_channels(selected_market, max_results))

                if results:
                    st.session_state.search_results[selected_market] = results
                    st.success(f"✅ {len(results)} canaux trouvés!")
                else:
                    st.warning("⚠️ Aucun canal trouvé. Essayez d'autres mots-clés.")
            except Exception as e:
                st.error(f"❌ Erreur lors de la recherche: {str(e)}")

    # Affichage des résultats
    if selected_market in st.session_state.search_results:
        st.divider()
        st.subheader("📊 Résultats de la Recherche")

        results = st.session_state.search_results[selected_market]
        history = load_history()

        # Séparer les canaux publics (rejoignables directement) des privés
        public_channels  = [c for c in results if c.get("is_public", True)]
        private_channels = [c for c in results if not c.get("is_public", True)]

        # ── Canaux Publics ──────────────────────────────────────
        st.write(f"### 🌐 Canaux Publics ({len(public_channels)}) — sélectionnables directement")
        if public_channels:
            for idx, channel in enumerate(public_channels):
                already_calibrated = channel["username"] in history
                col1, col2, col3, col4 = st.columns([1, 4, 2, 2])

                with col1:
                    selected = st.checkbox(
                        "✓",
                        key=f"select_pub_{selected_market}_{idx}",
                        label_visibility="collapsed",
                        disabled=already_calibrated
                    )
                    if selected and not already_calibrated:
                        if selected_market not in st.session_state.selected_channels:
                            st.session_state.selected_channels[selected_market] = []
                        if channel not in st.session_state.selected_channels[selected_market]:
                            st.session_state.selected_channels[selected_market].append(channel)

                with col2:
                    verified_badge = "✅" if channel.get("is_verified") else ""
                    st.write(f"**{channel['title']}** {verified_badge} `{channel.get('channel_type', '🌐 Public')}`")
                    st.caption(f"@{channel['username']}")
                    desc = channel.get('description', '') or 'Pas de description'
                    st.caption(f"📝 {desc}")
                    if already_calibrated:
                        saved = history[channel["username"]]
                        st.caption(f"📌 Déjà calibré — Score: {saved.get('score', '?')}/100")

                with col3:
                    st.metric("Membres", f"{channel['members']:,}")

                with col4:
                    activity_color = {
                        "Très actif": "🟢", "Actif": "🟡", "Modéré": "🟠", "Faible": "🔴"
                    }.get(channel.get('recent_activity', 'Inconnu'), "⚪")
                    st.write(f"{activity_color} {channel.get('recent_activity', 'Inconnu')}")
                st.divider()
        else:
            st.caption("Aucun canal public trouvé pour cette recherche.")

        # ── Canaux Privés / Restreints ───────────────────────────
        if private_channels:
            with st.expander(f"🔒 Canaux Privés/Restreints ({len(private_channels)}) — nécessitent une demande d'adhésion", expanded=False):
                st.caption("Ces canaux n'ont pas d'username public. Envoyez une demande d'adhésion, "
                           "elle sera suivie dans 'Mes Canaux → En Attente d'Approbation'.")
                for idx, channel in enumerate(private_channels):
                    already_calibrated = channel["username"] in history
                    already_pending = history.get(channel["username"], {}).get("status") == "pending_approval"
                    col1, col2, col3, col4 = st.columns([4, 2, 2, 2])
                    with col1:
                        verified_badge = "✅" if channel.get("is_verified") else ""
                        st.write(f"**{channel['title']}** {verified_badge} `🔒 Privé/Restreint`")
                        st.caption(f"ID: {channel['username']}")
                        desc = channel.get('description', '') or 'Pas de description'
                        st.caption(f"📝 {desc}")
                    with col2:
                        st.metric("Membres", f"{channel['members']:,}")
                    with col3:
                        activity_color = {
                            "Très actif": "🟢", "Actif": "🟡", "Modéré": "🟠", "Faible": "🔴"
                        }.get(channel.get('recent_activity', 'Inconnu'), "⚪")
                        st.write(f"{activity_color} {channel.get('recent_activity', 'Inconnu')}")
                    with col4:
                        if already_calibrated:
                            st.caption("📌 Déjà traité")
                        elif already_pending:
                            st.caption("📨 Demande déjà envoyée")
                        else:
                            if st.button("📨 Demander", key=f"reqjoin_{selected_market}_{idx}"):
                                channel["market"] = selected_market
                                with st.spinner(f"Envoi de la demande pour {channel['title']}..."):
                                    try:
                                        result = asyncio.run(join_and_calibrate_single(channel))
                                        save_single_channel(result)
                                        if result.get('status') != 'rejected':
                                            st.success(f"✅ Rejoint et calibré ! Score: {result.get('score', 0)}/100")
                                        elif result.get('action_needed') == 'wait_approval':
                                            st.info("📨 Demande envoyée — suivi dans 'Mes Canaux'")
                                        else:
                                            st.warning(f"⚠️ {result.get('reason', 'Impossible')}")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"❌ Erreur: {e}")
                    st.divider()

        # Bouton passer à la sélection
        st.divider()
        total_selected = sum(len(ch) for ch in st.session_state.selected_channels.values())

        if total_selected > 0:
            st.success(f"✅ {total_selected} canal(aux) sélectionné(s)")
            if st.button("➡️ PASSER À LA SÉLECTION", type="primary", use_container_width=True):
                st.session_state.current_step = 3
                st.rerun()
        else:
            st.warning("⚠️ Sélectionnez au moins un canal public non encore calibré pour continuer")

# ═══════════════════════════════════════════════════════════════
# ÉTAPE 3 : SÉLECTION MANUELLE
# ═══════════════════════════════════════════════════════════════

elif st.session_state.current_step == 3:
    st.header("✅ Étape 3: Validation de la Sélection")

    # Bouton retour
    if st.button("⬅️ Retour à la recherche"):
        st.session_state.current_step = 2
        st.rerun()

    total_selected = sum(len(ch) for ch in st.session_state.selected_channels.values())

    if total_selected == 0:
        st.warning("⚠️ Aucun canal sélectionné")
    else:
        st.success(f"✅ {total_selected} canal(aux) sélectionné(s) pour calibration")

        for market, channels in st.session_state.selected_channels.items():
            if channels:
                market_info = MARKETS.get(market, MARKETS["custom"])
                with st.expander(
                    f"{market_info['icon']} {market_info['name']} - {len(channels)} canal(aux)",
                    expanded=True
                ):
                    for channel in channels:
                        col1, col2, col3 = st.columns([3, 2, 1])
                        with col1:
                            verified_badge = "✅" if channel.get("is_verified") else ""
                            st.write(f"**{channel['title']}** {verified_badge}")
                            st.caption(f"@{channel['username']}")
                        with col2:
                            st.metric("Membres", f"{channel['members']:,}")
                        with col3:
                            if st.button("🗑️", key=f"remove_{market}_{channel['username']}"):
                                st.session_state.selected_channels[market].remove(channel)
                                st.rerun()

        st.divider()
        estimated_time = total_selected * 10
        st.info(f"⏱️ Temps estimé pour la calibration: ~{estimated_time} minutes")
        st.warning("⚠️ La calibration utilise votre session Telegram personnelle et s'exécute sur ce serveur.")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("⬅️ Retour à la recherche", use_container_width=True):
                st.session_state.current_step = 2
                st.rerun()
        with col2:
            if st.button("➡️ LANCER LA CALIBRATION", type="primary", use_container_width=True):
                st.session_state.current_step = 4
                st.rerun()

# ═══════════════════════════════════════════════════════════════
# ÉTAPE 4 : CALIBRATION
# ═══════════════════════════════════════════════════════════════

elif st.session_state.current_step == 4:
    st.header("⚙️ Étape 4: Calibration des Canaux")

    # Bouton retour
    if st.button("⬅️ Retour à la sélection"):
        st.session_state.calibration_results = None
        st.session_state.current_step = 3
        st.rerun()

    st.info("🔬 Analyse des messages Telegram - Utilise votre session personnelle")

    # Paramètres de calibration (Mode Pro)
    if st.session_state.pro_mode:
        with st.expander("🔧 Paramètres de Calibration Avancés"):
            col1, col2 = st.columns(2)
            with col1:
                min_messages = st.number_input("Messages minimum", 50, 500, 100, 10)
                target_messages = st.number_input("Messages cible", 100, 500, 200, 10)
            with col2:
                min_signals = st.slider("Signaux minimum", 5, 50, 15, 1)
                min_winrate = st.slider("Winrate minimum (%)", 40, 70, 50, 5)
    else:
        min_messages = 100
        target_messages = 200
        min_signals = 15
        min_winrate = 50

    # Si calibration déjà effectuée dans cette session
    if st.session_state.calibration_results is not None:
        results = st.session_state.calibration_results
        st.success("🎉 Calibration terminée!")

        col1, col2, col3 = st.columns(3)
        col1.metric("✅ Activés", len(results["activated"]))
        col2.metric("⏳ En Test", len(results["short_test"]))
        col3.metric("❌ Rejetés", len(results["rejected"]))

        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            if st.button("⬅️ Recalibrer (retour sélection)", use_container_width=True):
                st.session_state.calibration_results = None
                st.session_state.current_step = 3
                st.rerun()
        with col2:
            if st.button("➡️ VOIR LES RÉSULTATS DÉTAILLÉS", type="primary", use_container_width=True):
                st.session_state.current_step = 5
                st.rerun()

    else:
        # Préparer la liste des canaux
        all_channels = []
        for market, channels in st.session_state.selected_channels.items():
            for channel in channels:
                channel["market"] = market
                all_channels.append(channel)

        # Vérifier lesquels sont déjà calibrés
        history = load_history()
        already_done = {u for u in history}
        to_calibrate = [ch for ch in all_channels if ch.get("username") not in already_done]
        already_calibrated_count = len(all_channels) - len(to_calibrate)

        if already_calibrated_count > 0:
            st.info(f"⏭️ {already_calibrated_count} canal(aux) déjà calibré(s) — seront ignorés")

        if not to_calibrate:
            st.success("✅ Tous les canaux sont déjà calibrés ! Consultez 'Mes Canaux' dans l'accueil.")
            if st.button("🏠 Retour à l'accueil", use_container_width=True):
                st.session_state.current_step = 1
                st.rerun()
        else:
            st.info(f"📋 {len(to_calibrate)} canal(aux) à calibrer — sauvegarde progressive activée")

            # Bouton de lancement
            if st.button("🚀 DÉMARRER LA CALIBRATION", type="primary", use_container_width=True):
                progress_bar = st.progress(0)
                status_text = st.empty()
                log_area = st.empty()
                done_count = [0]  # Compteur mutable pour le callback

                config = {"max_messages": target_messages, "min_messages": min_messages}

                # Callback de sauvegarde progressive
                def on_channel_done(channel_result):
                    save_single_channel(channel_result)
                    done_count[0] += 1
                    pct = done_count[0] / len(to_calibrate)
                    progress_bar.progress(pct)
                    status_icon = {"activated": "✅", "short_test": "⏳", "rejected": "❌"}.get(
                        channel_result.get("status", ""), "❓"
                    )
                    log_area.info(
                        f"{status_icon} [{done_count[0]}/{len(to_calibrate)}] "
                        f"{channel_result.get('title', '?')} — "
                        f"Score: {channel_result.get('score', 0)}/100 — Sauvegardé ✅"
                    )

                status_text.text(f"🔄 Calibration de {len(to_calibrate)} canal(aux) en cours...")

                try:
                    results = asyncio.run(calibrate_channels_batch(
                        to_calibrate,
                        config,
                        on_channel_done=on_channel_done,
                        skip_usernames=already_done
                    ))
                    progress_bar.progress(1.0)
                    status_text.text("✅ Calibration terminée!")

                    st.session_state.calibration_results = results
                    st.success(
                        f"🎉 Terminé: {len(results['activated'])} activés, "
                        f"{len(results['short_test'])} en test, "
                        f"{len(results['rejected'])} rejetés — Tout sauvegardé ✅"
                    )
                    st.rerun()

                except Exception as e:
                    st.error(f"❌ Erreur lors de la calibration: {str(e)}")
                    st.info("💡 Les canaux déjà traités ont été sauvegardés. Vous pouvez reprendre.")

# ═══════════════════════════════════════════════════════════════
# ÉTAPE 5 : RÉSULTATS ET TRADING
# ═══════════════════════════════════════════════════════════════

elif st.session_state.current_step == 5:
    st.header("🚀 Étape 5: Résultats et Trading")

    # Bouton retour
    col_back, col_home = st.columns([1, 1])
    with col_back:
        if st.button("⬅️ Retour à la calibration"):
            st.session_state.current_step = 4
            st.rerun()
    with col_home:
        if st.button("🏠 Retour à l'accueil"):
            st.session_state.current_step = 1
            st.rerun()

    if st.session_state.calibration_results is None:
        st.warning("⚠️ Aucun résultat de calibration disponible")
    else:
        results = st.session_state.calibration_results

        # Résumé global
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("✅ Activés", len(results["activated"]), delta="Prêts")
        col2.metric("⏳ Test Court", len(results["short_test"]), delta="En cours")
        col3.metric("❌ Rejetés", len(results["rejected"]))
        col4.metric("📊 Total", sum(len(v) for v in results.values()))

        st.divider()

        # ── Canaux Activés ──
        if results["activated"]:
            st.subheader("✅ Canaux Activés - Prêts pour le Trading")
            for channel in results["activated"]:
                market_info = MARKETS.get(channel.get("market", "custom"), MARKETS["custom"])
                with st.expander(
                    f"{market_info['icon']} {channel['title']}  —  Score: {channel.get('score', '?')}/100",
                    expanded=True
                ):
                    st.info("ℹ️ Score basé sur l'analyse textuelle des messages (BUY/SELL/TP/SL). Le vrai winrate nécessite OCR + suivi des prix (TP/SL atteints).")
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Score qualité", f"{channel.get('score', '?')}/100")
                    col2.metric("Signaux texte", channel.get("signals_count", "?"))
                    col3.metric("Membres", f"{channel.get('members', 0):,}")
                    col4.metric("Signaux/jour", channel.get("metrics", {}).get("signals_per_day", "?"))

                    metrics = channel.get("metrics", {})
                    if metrics:
                        m1, m2, m3, m4 = st.columns(4)
                        m1.metric("Messages", metrics.get("total_messages", "?"))
                        m2.metric("Signaux/jour", metrics.get("signals_per_day", "?"))
                        m3.metric("Qualité moy.", f"{metrics.get('avg_quality', '?')}/10")
                        m4.metric("Dernier signal", f"{metrics.get('hours_since_last_signal', '?')}h")

                    st.caption(f"@{channel['username']} — {channel.get('description', '')[:80]}")

        # ── Canaux en Test ──
        if results["short_test"]:
            st.subheader("⏳ Canaux en Test Court")
            for channel in results["short_test"]:
                market_info = MARKETS.get(channel.get("market", "custom"), MARKETS["custom"])
                col1, col2, col3 = st.columns([3, 2, 2])
                with col1:
                    st.write(f"{market_info['icon']} **{channel['title']}**")
                    st.caption(f"@{channel['username']}")
                with col2:
                    st.metric("Score", f"{channel.get('score', '?')}/100")
                with col3:
                    metrics = channel.get("metrics", {})
                    if metrics:
                        st.caption(f"📊 {metrics.get('total_signals', 0)} signaux | qualité: {metrics.get('avg_quality', 0)}/10")

        # ── Canaux Rejetés ──
        if results["rejected"]:
            with st.expander(f"❌ Canaux Rejetés ({len(results['rejected'])})", expanded=True):
                for channel in results["rejected"]:
                    market_info = MARKETS.get(channel.get("market", "custom"), MARKETS["custom"])
                    reason = channel.get("reason", "Critères non atteints")
                    needs_join = any(kw in reason for kw in ["🔒", "📨", "privé", "PRIVÉ", "rejoign", "adhésion", "Rejoign"])
                    col1, col2, col3, col4 = st.columns([3, 2, 3, 1])
                    with col1:
                        st.write(f"{market_info['icon']} **{channel['title']}**")
                        st.caption(f"@{channel['username']}")
                    with col2:
                        st.metric("Score", f"{channel.get('score', 0)}/100")
                    with col3:
                        metrics = channel.get("metrics", {})
                        st.caption(f"❌ {reason}")
                        if metrics:
                            st.caption(
                                f"📊 {metrics.get('total_signals', 0)} signaux | "
                                f"{metrics.get('total_messages', 0)} messages | "
                                f"qualité: {metrics.get('avg_quality', 0)}/10"
                            )
                    with col4:
                        if needs_join:
                            if st.button("🔄 Rejoindre", key=f"join_r5_{channel['username']}"):
                                with st.spinner(f"Tentative de rejoindre {channel['title']}..."):
                                    try:
                                        result = asyncio.run(join_and_calibrate_single(channel))
                                        save_single_channel(result)
                                        if result.get('status') != 'rejected':
                                            st.success(f"✅ Rejoint et calibré ! Score: {result.get('score', 0)}/100")
                                        else:
                                            st.warning(f"⚠️ {result.get('reason', 'Toujours impossible')}")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"❌ Erreur: {e}")
                    st.divider()

        st.divider()

        # ── Actions ──
        st.subheader("🎯 Actions")
        col1, col2, col3 = st.columns(3)

        with col1:
            # Export CSV
            all_rows = []
            for status, channels in results.items():
                for ch in channels:
                    market_info = MARKETS.get(ch.get("market", "custom"), MARKETS["custom"])
                    metrics = ch.get("metrics", {})
                    all_rows.append({
                        "Statut": status,
                        "Marché": market_info["name"],
                        "Canal": ch["title"],
                        "Username": ch["username"],
                        "Score": ch.get("score", "N/A"),
                        "Winrate": ch.get("winrate", "N/A"),
                        "Signaux": ch.get("signals_count", "N/A"),
                        "Signaux/jour": metrics.get("signals_per_day", "N/A"),
                        "Qualité": metrics.get("avg_quality", "N/A"),
                        "Membres": ch.get("members", "N/A"),
                        "Raison rejet": ch.get("reason", ""),
                    })
            df = pd.DataFrame(all_rows)
            csv = df.to_csv(index=False, encoding="utf-8")
            st.download_button(
                "📥 Télécharger Rapport CSV",
                csv,
                "calibration_results.csv",
                "text/csv",
                use_container_width=True
            )

        with col2:
            if st.button("🔄 Nouvelle Recherche", use_container_width=True):
                st.session_state.search_results = {}
                st.session_state.selected_channels = {}
                st.session_state.calibration_results = None
                st.session_state.current_step = 2
                st.rerun()

        with col3:
            if st.button("🚀 Lancer Trading", type="primary", use_container_width=True):
                activated_usernames = [ch["username"] for ch in results.get("activated", [])]
                if activated_usernames:
                    st.success(f"✅ {len(activated_usernames)} canaux prêts pour le trading")
                    st.code("\n".join(activated_usernames))
                    st.info("💡 Utilisez ces canaux dans phase4_synthesizer.py")
                else:
                    st.warning("⚠️ Aucun canal activé dans cette calibration")

# ═══════════════════════════════════════════════════════════════
# FOOTER
# ═══════════════════════════════════════════════════════════════

st.divider()
st.caption("🚀 Pipeline Trading v3.0 - Mes Canaux + Persistance | 30/06/2026")
st.caption("💡 Workflow: Connexion → Accueil → Recherche → Sélection → Calibration → Résultats")
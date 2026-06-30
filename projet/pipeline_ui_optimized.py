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
from telegram_calibrator import calibrate_channels_batch
from telegram_authenticator import show_auth_page

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
    """Ajoute les résultats de calibration à l'historique."""
    history = load_history()
    now = datetime.now().isoformat()
    for status in ["activated", "short_test", "rejected"]:
        for ch in calibration_results.get(status, []):
            username = ch.get("username", "")
            if not username:
                continue
            market = ch.get("market", "custom")
            history[username] = {
                "username": username,
                "title": ch.get("title", username),
                "market": market,
                "status": status,
                "score": ch.get("score", 0),
                "winrate": ch.get("winrate", ch.get("score", 0)),
                "signals_count": ch.get("signals_count", 0),
                "metrics": ch.get("metrics", {}),
                "members": ch.get("members", 0),
                "description": ch.get("description", ""),
                "reason": ch.get("reason", ""),
                "date_calibration": now,
            }
    save_history(history)
    return history


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
                        winrate = ch.get("winrate")
                        if winrate is not None:
                            color = "winrate-good" if winrate >= 70 else ("winrate-medium" if winrate >= 50 else "winrate-bad")
                            st.markdown(f'<span class="{color}">Winrate: {winrate}%</span>', unsafe_allow_html=True)
                        else:
                            st.caption("Winrate: non calculé")
                    with col2:
                        st.metric("Signaux", ch.get("signals_count", "?"))
                    with col3:
                        date_str = ch.get("date_calibration", "")[:10] if ch.get("date_calibration") else "?"
                        st.caption(f"@{username}")
                        st.caption(f"Calibré le: {date_str}")
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

        # ── Canaux Rejetés ──
        if rejected:
            with st.expander(f"❌ Canaux Rejetés ({len(rejected)})", expanded=False):
                for username, ch in rejected.items():
                    market_info = MARKETS.get(ch.get("market", "custom"), MARKETS["custom"])
                    col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
                    with col1:
                        st.write(f"{market_info['icon']} **{ch['title']}**")
                        st.caption(f"@{username}")
                    with col2:
                        st.metric("Score", f"{ch.get('score', '?')}/100")
                    with col3:
                        reason = ch.get("reason", "")
                        metrics = ch.get("metrics", {})
                        if reason:
                            st.caption(f"❌ {reason[:60]}")
                        if metrics:
                            st.caption(f"📊 {metrics.get('total_signals', 0)} signaux | qualité: {metrics.get('avg_quality', 0)}/10")
                    with col4:
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

        st.write(f"**{len(results)} canaux trouvés** - Cochez ceux que vous voulez calibrer:")

        for idx, channel in enumerate(results):
            already_calibrated = channel["username"] in history
            col1, col2, col3, col4, col5 = st.columns([1, 3, 2, 2, 2])

            with col1:
                selected = st.checkbox(
                    "✓",
                    key=f"select_{selected_market}_{idx}",
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
                st.write(f"**{channel['title']}** {verified_badge}")
                st.caption(f"@{channel['username']}")
                if already_calibrated:
                    saved = history[channel["username"]]
                    st.caption(f"📌 Déjà calibré — Score: {saved.get('score', '?')}/100")

            with col3:
                st.metric("Membres", f"{channel['members']:,}")

            with col4:
                activity_color = {
                    "Très actif": "🟢", "Actif": "🟡", "Modéré": "🟠"
                }.get(channel.get('recent_activity', 'Inconnu'), "⚪")
                st.write(f"{activity_color} {channel.get('recent_activity', 'Inconnu')}")

            with col5:
                desc = channel.get('description', '') or ''
                st.caption(desc[:50] + ("..." if len(desc) > 50 else ""))

        # Bouton passer à la sélection
        st.divider()
        total_selected = sum(len(ch) for ch in st.session_state.selected_channels.values())

        if total_selected > 0:
            st.success(f"✅ {total_selected} canal(aux) sélectionné(s)")
            if st.button("➡️ PASSER À LA SÉLECTION", type="primary", use_container_width=True):
                st.session_state.current_step = 3
                st.rerun()
        else:
            st.warning("⚠️ Sélectionnez au moins un canal non encore calibré pour continuer")

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
        # Bouton de lancement
        if st.button("🚀 DÉMARRER LA CALIBRATION", type="primary", use_container_width=True):
            progress_bar = st.progress(0)
            status_text = st.empty()

            all_channels = []
            for market, channels in st.session_state.selected_channels.items():
                for channel in channels:
                    channel["market"] = market
                    all_channels.append(channel)

            total_channels = len(all_channels)
            config = {"max_messages": target_messages, "min_messages": min_messages}

            status_text.text(f"🔄 Calibration de {total_channels} canal(aux) en cours...")

            try:
                results = asyncio.run(calibrate_channels_batch(all_channels, config))
                progress_bar.progress(1.0)
                status_text.text("✅ Calibration terminée!")

                # Enrichir les résultats avec winrate
                for status in ["activated", "short_test", "rejected"]:
                    for channel in results[status]:
                        metrics = channel.get("metrics", {})
                        channel["winrate"] = int(channel.get("score", 0))
                        channel["signals_count"] = metrics.get("total_signals", 0)

                # Sauvegarder dans l'historique
                add_channels_to_history(results)

                st.session_state.calibration_results = results
                st.success(
                    f"🎉 Terminé: {len(results['activated'])} activés, "
                    f"{len(results['short_test'])} en test, "
                    f"{len(results['rejected'])} rejetés — Sauvegardé dans l'historique ✅"
                )
                st.rerun()

            except Exception as e:
                st.error(f"❌ Erreur lors de la calibration: {str(e)}")
                st.info("💡 Vérifiez votre connexion Telegram et réessayez")

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
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Winrate", f"{channel.get('winrate', '?')}%")
                    col2.metric("Signaux", channel.get("signals_count", "?"))
                    col3.metric("Membres", f"{channel.get('members', 0):,}")
                    col4.metric("Score", f"{channel.get('score', '?')}/100")

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
                    col1, col2, col3 = st.columns([3, 2, 3])
                    with col1:
                        st.write(f"{market_info['icon']} **{channel['title']}**")
                        st.caption(f"@{channel['username']}")
                    with col2:
                        st.metric("Score", f"{channel.get('score', 0)}/100")
                    with col3:
                        reason = channel.get("reason", "Critères non atteints")
                        metrics = channel.get("metrics", {})
                        st.caption(f"❌ {reason}")
                        if metrics:
                            st.caption(
                                f"📊 {metrics.get('total_signals', 0)} signaux | "
                                f"{metrics.get('total_messages', 0)} messages | "
                                f"qualité: {metrics.get('avg_quality', 0)}/10"
                            )
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
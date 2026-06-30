"""
INTERFACE WEB OPTIMISÉE - PIPELINE MULTI-MARCHÉS
Interface Streamlit simplifiée pour utilisateurs normaux

Workflow:
1. Recherche légère (sans OCR) - affichage des résultats
2. Sélection manuelle des canaux par l'utilisateur
3. Calibration avec OCR uniquement sur les canaux sélectionnés
4. Mode Pro pour paramètres avancés

Usage:
    streamlit run pipeline_ui_optimized.py
"""
import streamlit as st
import json
from pathlib import Path
from datetime import datetime
import pandas as pd
import plotly.express as px
import asyncio
from telegram_search import search_telegram_channels, search_custom_market
from telegram_calibrator import calibrate_channels_batch, join_channel
from telegram_authenticator import show_auth_page, get_telegram_client
from telethon import TelegramClient
from telethon.sessions import StringSession

# Configuration de la page
st.set_page_config(
    page_title="Pipeline Trading",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Styles CSS
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
    .step-card {
        background-color: #f0f2f6;
        padding: 1.5rem;
        border-radius: 10px;
        border-left: 4px solid #667eea;
        margin: 1rem 0;
    }
    .channel-card {
        background-color: white;
        padding: 1rem;
        border-radius: 8px;
        border: 1px solid #e0e0e0;
        margin: 0.5rem 0;
    }
</style>
""", unsafe_allow_html=True)

# Titre principal
st.markdown('<div class="main-header">🚀 PIPELINE TRADING - INTERFACE SIMPLIFIÉE</div>', unsafe_allow_html=True)

# Marchés disponibles
MARKETS = {
    "gold_mgc": {"name": "Gold (MGC)", "icon": "🥇"},
    "mnq_nasdaq": {"name": "Nasdaq (MNQ)", "icon": "📊"},
    "mcl_crude": {"name": "Crude Oil (MCL)", "icon": "🛢️"},
    "mes_sp500": {"name": "S&P 500 (MES)", "icon": "📈"}
}

# Initialisation session_state
if 'current_step' not in st.session_state:
    st.session_state.current_step = 0  # Commencer par l'authentification
if 'search_results' not in st.session_state:
    st.session_state.search_results = {}
if 'selected_channels' not in st.session_state:
    st.session_state.selected_channels = {}
if 'pro_mode' not in st.session_state:
    st.session_state.pro_mode = False

# Sidebar - Navigation et Mode Pro
with st.sidebar:
    st.title("📋 Navigation")
    
    # Toggle Mode Pro
    st.session_state.pro_mode = st.toggle("🔧 Mode Pro", value=st.session_state.pro_mode)
    
    if st.session_state.pro_mode:
        st.info("Mode Pro activé - Paramètres avancés disponibles")
    
    st.divider()
    
    # Indicateur d'étape
    steps = ["🔑 Connexion", "🔍 Recherche", "✅ Sélection", "⚙️ Calibration", "🚀 Trading"]
    for i, step in enumerate(steps, 0):
        if i == st.session_state.current_step:
            st.markdown(f"**➡️ {step}**")
        elif i < st.session_state.current_step:
            st.markdown(f"✅ {step}")
        else:
            st.markdown(f"⚪ {step}")
    
    st.divider()
    st.caption(f"🕐 {datetime.now().strftime('%H:%M:%S')}")
    st.caption("Version 2.0 - Optimisée")

# ═══════════════════════════════════════════════════════════════
# ÉTAPE 0: AUTHENTIFICATION TELEGRAM (UNIVERSELLE)
# ═══════════════════════════════════════════════════════════════

if st.session_state.current_step == 0:
    # Utiliser la page d'authentification du module
    # show_auth_page() retourne True si l'utilisateur est connecté (tg_logged_in)
    if show_auth_page():
        st.session_state.current_step = 1
        st.rerun()

# ═══════════════════════════════════════════════════════════════
# ÉTAPE 1: RECHERCHE LÉGÈRE (SANS OCR)
# ═══════════════════════════════════════════════════════════════

elif st.session_state.current_step == 1:
    st.header("🔍 Étape 1: Recherche de Canaux")
    
    # Bouton retour à l'authentification
    if st.button("🔑 Se déconnecter / Changer de compte", use_container_width=False):
        from telegram_authenticator import _logout
        _logout()
    
    st.info("💡 Recherche rapide sans OCR - Seulement les informations de base")
    
    # Mode de recherche
    search_mode = st.radio(
        "Mode de recherche",
        ["Marchés prédéfinis", "Recherche personnalisée"],
        horizontal=True
    )
    
    if search_mode == "Marchés prédéfinis":
        # Sélection du marché
        col1, col2 = st.columns([2, 1])
        
        with col1:
            selected_market = st.selectbox(
                "Choisissez un marché",
                options=list(MARKETS.keys()),
                format_func=lambda x: f"{MARKETS[x]['icon']} {MARKETS[x]['name']}"
            )
        
        with col2:
            max_results = st.number_input("Nombre de résultats", 5, 50, 20, 5)
        
        custom_keywords = None
    else:
        # Recherche personnalisée
        st.info("🔍 Recherchez n'importe quel marché avec vos propres mots-clés")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            custom_keywords = st.text_area(
                "Mots-clés de recherche (un par ligne)",
                value="bitcoin\nBTC\ncrypto signals\nbitcoin trading",
                height=150,
                help="Entrez les mots-clés pour votre recherche personnalisée"
            )
        
        with col2:
            max_results = st.number_input("Nombre de résultats", 5, 50, 20, 5)
        
        selected_market = "custom"
    
    # Paramètres Pro
    if st.session_state.pro_mode:
        with st.expander("🔧 Paramètres Avancés de Recherche"):
            col1, col2 = st.columns(2)
            with col1:
                min_members = st.number_input("Membres minimum", 500, 10000, 1000, 500)
                max_members = st.number_input("Membres maximum", 10000, 100000, 50000, 5000)
            with col2:
                search_keywords = st.text_area(
                    "Mots-clés personnalisés (un par ligne)",
                    value="gold signals\ntrading gold\ngold forex"
                )
    else:
        min_members = 1000
        max_members = 50000
        search_keywords = None
    
    # Bouton de recherche
    if st.button("🔍 LANCER LA RECHERCHE", type="primary", use_container_width=True):
        with st.spinner("🔍 Recherche en cours sur Telegram..."):
            try:
                # Recherche réelle via Telegram API
                if search_mode == "Recherche personnalisée" and custom_keywords:
                    # Recherche personnalisée
                    keywords_list = [k.strip() for k in custom_keywords.split('\n') if k.strip()]
                    results = asyncio.run(search_custom_market(keywords_list, max_results))
                else:
                    # Recherche prédéfinie
                    results = asyncio.run(search_telegram_channels(selected_market, max_results))
                
                if results:
                    st.session_state.search_results[selected_market] = results
                    st.success(f"✅ {len(results)} canaux trouvés!")
                else:
                    st.warning("⚠️ Aucun canal trouvé. Essayez d'autres mots-clés.")
                    
            except Exception as e:
                st.error(f"❌ Erreur lors de la recherche: {str(e)}")
                st.info("💡 Vérifiez que votre StringSession est configurée dans les Secrets Streamlit")
    
    # Affichage des résultats
    if selected_market in st.session_state.search_results:
        st.divider()
        st.subheader("📊 Résultats de la Recherche")
        
        results = st.session_state.search_results[selected_market]
        
        # Tableau des résultats
        df_results = pd.DataFrame(results)
        
        # Affichage avec sélection
        st.write(f"**{len(results)} canaux trouvés** - Cochez ceux que vous voulez calibrer:")
        
        for idx, channel in enumerate(results):
            col1, col2, col3, col4, col5 = st.columns([1, 3, 2, 2, 2])
            
            with col1:
                selected = st.checkbox(
                    "✓",
                    key=f"select_{selected_market}_{idx}",
                    label_visibility="collapsed"
                )
                
                if selected:
                    if selected_market not in st.session_state.selected_channels:
                        st.session_state.selected_channels[selected_market] = []
                    if channel not in st.session_state.selected_channels[selected_market]:
                        st.session_state.selected_channels[selected_market].append(channel)
            
            with col2:
                verified_badge = "✅" if channel.get("is_verified") else ""
                st.write(f"**{channel['title']}** {verified_badge}")
                st.caption(f"@{channel['username']}")
            
            with col3:
                st.metric("Membres", f"{channel['members']:,}")
            
            with col4:
                activity_color = {
                    "Très actif": "🟢",
                    "Actif": "🟡",
                    "Modéré": "🟠"
                }.get(channel.get('recent_activity', 'Inconnu'), "⚪")
                st.write(f"{activity_color} {channel.get('recent_activity', 'Inconnu')}")
            
            with col5:
                st.caption(channel.get('description', '')[:50] + "...")
        
        # Bouton pour passer à l'étape suivante
        st.divider()
        total_selected = sum(len(channels) for channels in st.session_state.selected_channels.values())
        
        if total_selected > 0:
            st.success(f"✅ {total_selected} canal(aux) sélectionné(s)")
            if st.button("➡️ PASSER À LA SÉLECTION", type="primary", use_container_width=True):
                st.session_state.current_step = 2
                st.rerun()
        else:
            st.warning("⚠️ Sélectionnez au moins un canal pour continuer")

# ═══════════════════════════════════════════════════════════════
# ÉTAPE 2: SÉLECTION MANUELLE
# ═══════════════════════════════════════════════════════════════

elif st.session_state.current_step == 2:
    st.header("✅ Étape 2: Validation de la Sélection")
    
    total_selected = sum(len(channels) for channels in st.session_state.selected_channels.values())
    
    if total_selected == 0:
        st.warning("⚠️ Aucun canal sélectionné")
        if st.button("⬅️ Retour à la recherche"):
            st.session_state.current_step = 1
            st.rerun()
    else:
        st.success(f"✅ {total_selected} canal(aux) sélectionné(s) pour calibration")
        
        # Affichage par marché
        for market, channels in st.session_state.selected_channels.items():
            if channels:
                with st.expander(f"{MARKETS[market]['icon']} {MARKETS[market]['name']} - {len(channels)} canal(aux)", expanded=True):
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
        
        # Estimation du temps
        estimated_time = total_selected * 10  # 10 min par canal
        st.info(f"⏱️ Temps estimé pour la calibration: ~{estimated_time} minutes")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("⬅️ Retour à la recherche", use_container_width=True):
                st.session_state.current_step = 1
                st.rerun()
        
        with col2:
            if st.button("➡️ LANCER LA CALIBRATION", type="primary", use_container_width=True):
                st.session_state.current_step = 3
                st.rerun()

# ═══════════════════════════════════════════════════════════════
# ÉTAPE 3: CALIBRATION (AVEC OCR SUR CANAUX SÉLECTIONNÉS)
# ═══════════════════════════════════════════════════════════════

elif st.session_state.current_step == 3:
    st.header("⚙️ Étape 3: Calibration des Canaux")
    
    st.info("🔬 OCR et analyse uniquement sur les canaux sélectionnés - Optimisation des ressources")
    
    # Paramètres de calibration (Mode Pro)
    if st.session_state.pro_mode:
        with st.expander("🔧 Paramètres de Calibration Avancés"):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.subheader("📥 Collecte")
                min_messages = st.number_input("Messages minimum", 50, 500, 100, 10)
                target_messages = st.number_input("Messages cible", 100, 500, 200, 10)
            
            with col2:
                st.subheader("🎯 Critères")
                min_signals = st.slider("Signaux minimum", 10, 50, 20, 1)
                min_winrate = st.slider("Winrate minimum (%)", 40, 70, 50, 5)
            
            with col3:
                st.subheader("🔧 OCR")
                ocr_batch_size = st.number_input("Batch size", 5, 30, 10, 5)
                ocr_timeout = st.number_input("Timeout (s)", 15, 60, 30, 5)
    else:
        # Valeurs par défaut
        min_messages = 100
        target_messages = 200
        min_signals = 20
        min_winrate = 50
        ocr_batch_size = 10
        ocr_timeout = 30
    
    # Vérifier si calibration déjà effectuée
    if 'calibration_results' in st.session_state:
        # Afficher le résumé des résultats
        results = st.session_state.calibration_results
        
        st.success("🎉 Calibration terminée avec succès!")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("✅ Canaux Activés", len(results["activated"]))
        with col2:
            st.metric("⏳ En Test Court", len(results["short_test"]))
        with col3:
            st.metric("❌ Rejetés", len(results["rejected"]))
        
        st.divider()
        
        # Boutons d'action
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("⬅️ Retour à la sélection", use_container_width=True):
                # Effacer les résultats pour permettre une nouvelle calibration
                del st.session_state.calibration_results
                st.session_state.current_step = 2
                st.rerun()
        
        with col2:
            if st.button("➡️ VOIR LES RÉSULTATS DÉTAILLÉS", type="primary", use_container_width=True):
                st.session_state.current_step = 4
                st.rerun()
    
    else:
        # Bouton de lancement de calibration
        if st.button("🚀 DÉMARRER LA CALIBRATION", type="primary", use_container_width=True):
            progress_bar = st.progress(0)
            status_text = st.empty()
            log_area = st.empty()
            
            # Préparer la liste de tous les canaux à calibrer
            all_channels = []
            for market, channels in st.session_state.selected_channels.items():
                for channel in channels:
                    channel['market'] = market  # Ajouter le marché au canal
                    all_channels.append(channel)
            
            total_channels = len(all_channels)
            
            # Configuration de calibration
            config = {
                'max_messages': target_messages,
                'min_messages': min_messages
            }
            
            # VRAIE CALIBRATION - Pas de simulation !
            status_text.text(f"🔄 Démarrage de la calibration RÉELLE de {total_channels} canal(aux)...")
            
            try:
                # Lancer la calibration réelle
                results = asyncio.run(calibrate_channels_batch(all_channels, config))
                
                progress_bar.progress(1.0)
                status_text.text("✅ Calibration terminée!")
                
                # Ajouter les métriques réelles aux résultats
                for status in ['activated', 'short_test', 'rejected']:
                    for channel in results[status]:
                        # Extraire les métriques de calibration
                        metrics = channel.get('metrics', {})
                        # Utiliser le score de calibration (0-100) comme indicateur de qualité
                        channel['winrate'] = int(channel.get('score', 0))
                        channel['signals_count'] = metrics.get('total_signals', 0)
                        
                        # Debug: vérifier cohérence statut/score
                        score = channel.get('score', 0)
                        if status == 'activated' and score < 70:
                            print(f"⚠️ INCOHÉRENCE: {channel['title']} - statut=activated mais score={score} < 70")
                        elif status == 'short_test' and score < 50:
                            print(f"⚠️ INCOHÉRENCE: {channel['title']} - statut=short_test mais score={score} < 50")
                
                # Sauvegarder les résultats
                st.session_state.calibration_results = results
                st.success(f"🎉 Calibration réelle terminée: {len(results['activated'])} activés, {len(results['short_test'])} en test, {len(results['rejected'])} rejetés")
                st.rerun()
                
            except Exception as e:
                st.error(f"❌ Erreur lors de la calibration: {str(e)}")
                st.info("💡 Vérifiez vos credentials Telegram et réessayez")
        
        # Bouton retour
        if st.button("⬅️ Retour à la sélection"):
            st.session_state.current_step = 2
            st.rerun()

# ═══════════════════════════════════════════════════════════════
# ÉTAPE 4: RÉSULTATS ET TRADING
# ═══════════════════════════════════════════════════════════════

elif st.session_state.current_step == 4:
    st.header("🚀 Étape 4: Résultats et Trading")
    
    if 'calibration_results' not in st.session_state:
        st.warning("⚠️ Aucun résultat de calibration disponible")
        if st.button("⬅️ Retour"):
            st.session_state.current_step = 1
            st.rerun()
    else:
        results = st.session_state.calibration_results
        
        # Résumé global
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("✅ Activés", len(results["activated"]), delta="Prêts")
        with col2:
            st.metric("⏳ Test Court", len(results["short_test"]), delta="En cours")
        with col3:
            st.metric("❌ Rejetés", len(results["rejected"]))
        with col4:
            total = sum(len(v) for v in results.values())
            st.metric("📊 Total", total)
        
        st.divider()
        
        # Canaux activés
        if results["activated"]:
            st.subheader("✅ Canaux Activés - Prêts pour le Trading")
            
            for channel in results["activated"]:
                with st.expander(f"{MARKETS[channel['market']]['icon']} {channel['title']}", expanded=True):
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.metric("Winrate", f"{channel['winrate']}%")
                    with col2:
                        st.metric("Signaux", channel['signals_count'])
                    with col3:
                        st.metric("Membres", f"{channel['members']:,}")
                    
                    st.caption(f"@{channel['username']} - {channel.get('description', '')}")
        
        # Canaux en test
        if results["short_test"]:
            st.subheader("⏳ Canaux en Test Court")
            
            for channel in results["short_test"]:
                st.info(f"{MARKETS[channel['market']]['icon']} {channel['title']} - En observation")
        
        # Canaux rejetés
        if results["rejected"]:
            with st.expander(f"❌ Canaux Rejetés ({len(results['rejected'])})"):
                for channel in results["rejected"]:
                    st.caption(f"{MARKETS[channel['market']]['icon']} {channel['title']} - Critères non atteints")
        
        st.divider()
        
        # Actions
        st.subheader("🎯 Prochaines Étapes")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("📥 Télécharger Rapport", use_container_width=True):
                # Créer CSV
                all_results = []
                for status, channels in results.items():
                    for ch in channels:
                        all_results.append({
                            "Statut": status,
                            "Marché": MARKETS[ch['market']]['name'],
                            "Canal": ch['title'],
                            "Username": ch['username'],
                            "Winrate": ch.get('winrate', 'N/A'),
                            "Signaux": ch.get('signals_count', 'N/A'),
                            "Membres": ch['members']
                        })
                
                df = pd.DataFrame(all_results)
                csv = df.to_csv(index=False, encoding='utf-8')
                st.download_button(
                    "💾 Télécharger CSV",
                    csv,
                    "calibration_results.csv",
                    "text/csv"
                )
                
                # Afficher aussi un aperçu
                st.write("**Aperçu des résultats:**")
                st.dataframe(df, use_container_width=True)
        
        with col2:
            if st.button("🔄 Nouvelle Recherche", use_container_width=True):
                # Réinitialiser
                st.session_state.current_step = 1
                st.session_state.search_results = {}
                st.session_state.selected_channels = {}
                st.rerun()
        
        with col3:
            if st.button("🚀 Lancer Trading", type="primary", use_container_width=True):
                st.success("✅ Canaux prêts pour phase4_synthesizer.py")
                st.info("💡 Utilisez les canaux activés dans votre stratégie de trading")

# Footer
st.divider()
st.caption("🚀 Pipeline Trading v2.0 - Interface Optimisée | Créé le 28/06/2026")
st.caption("💡 Workflow: Recherche → Sélection → Calibration → Trading")

#!/usr/bin/env python3
"""
MODULE D'AUTHENTIFICATION TELEGRAM POUR STREAMLIT
VERSION UNIVERSELLE - Compatible SaaS multi-utilisateurs
Important: Chaque utilisateur saisit ses propres credentials Telegram
- Aucun stockage de session dans le code
"""
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
import streamlit as st


# Titre de l'application
APP_TITLE = "Pipeline Telegram Trader - SaaS Mode"


def init_auth_state():
    """Initialise les variables de session si elles n'existent pas"""
    if 'telegram_api_id' not in st.session_state:
        st.session_state.telegram_api_id = ""
    if 'telegram_api_hash' not in st.session_state:
        st.session_state.telegram_api_hash = ""
    if 'telegram_session' not in st.session_state:
        st.session_state.telegram_session = ""
    if 'telegram_logged_in' not in st.session_state:
        st.session_state.telegram_logged_in = False
    

def show_auth_page() -> bool:
    """
    Affiche la page d'authentification pour la connexion Telegram
    Retourne True si l'utilisateur est connecte, False sinon
    """
    
    init_auth_state()
    st.markdown("---")
    
    # Titre de la page
    st.write(APP_TITLE, unsafe_allow_html=True)
    st.subheader("Etape 1: Connexion Telegram")
    
    # Message d'introduction
    with st.container():
        st.write("""
        ## Informations importantes:
        
        1. **Ces credentials sont VOTRES** - Ils ne sont JAMAIS stockes sur nos serveurs
        2. **La session est stockee UNIQUEMENT dans votre navigateur**
        3. **Maintenant la configuration** - Vous devez saisir vos identifiants API Telegram
        
        **C'est parti, a vous d'agir !**
        """)
    
    # Connexion
    col_c1, col_c2 = st.columns(2)
    
    with col_c1:
        st.subheader("Credentials Telegram")
        api_id = st.text_input("API ID", value=st.session_state.get('telegram_api_id', ''), placeholder="Ex: 882423941", type="password")     
        api_hash = st.text_input("API Hash", value=st.session_state.get('telegram_api_hash', ''), placeholder="Ex: 8d2a7c06a5484a2d359a4c7fc250b6a", type="password")
    
    with col_c2:
        st.subheader("Session Telegram")
        session_string = st.text_area("String Session (optionnel)", height=150, value=st.session_state.get('telegram_session', ''), help="Copiez-colliez votre session actuelle si vous en avez une")
    
    # Bouton de connexion
    button_col1, button_col2 = st.columns(2)
    
    with button_col1:
        if st.button("Option 1: Generer une session", type="primary", use_container=True):
            generate_session()
    
    with button_col2:
        if st.button("Option 2: Utiliser ma session existante", type="secondary", use_container=True):
            use_existing_session()
    
    # Bouton de validation
    st.markdown("---")
    
    if st.button("Valider la connexion", type="primary"):
        validate_and_connect()
    
    # Afficher le statut
    if st.session_state.get('telegram_logged_in', False):
        st.success("Connexion etablie !")
        return True
    
    return False


def generate_session():
    """
    Genere une nouvelle session Telegram (version simplifiee sans await direct)
    """
    try:
        from telethon import TelegramClient
        from telethon.sessions import StringSession
        
        # Verifier les credentials
        api_id = st.session_state.get('telegram_api_id')
        api_hash = st.session_state.get('telegram_api_hash')
        
        if not api_id or not api_hash:
            st.error("Veuillez saisir vos identifiants API")
            return
        
        # Afficher la generation en cours
        st.info("Generation en cours... Veuillez patienter.")
        
        # Saisir le code de confirmation
        code = st.text_input("Code de confirmation", type="password", help="Saisissez le code recu dans Telegram")
        
        if st.button("Verifier", type="primary"):
            try:
                # Creer une fonction async pour generer
                async def _generate():
                    client = TelegramClient(StringSession(), int(api_id), api_hash)
                    async with client:
                        await client.send_code(request='self')
                        if code:
                            await client.sign_in(code)
                            session_string = client.session.save()
                            return session_string
                        return None
                
                # Executer la fonction async
                result = asyncio.run(_generate())
                
                if result:
                    st.session_state.telegram_session = result
                    st.session_state.telegram_api_id = str(api_id)
                    st.session_state.telegram_api_hash = api_hash
                    st.success("Session generee avec succes !")
                    st.rerun()
                else:
                    st.error("Code non fourni ou invalide")
                    
            except Exception as e:
                st.error(f"Erreur: {str(e)}")
                
    except Exception as e:
        st.error(f"Erreur: {str(e)}")
        
    except ImportError:
        st.error("Erreur: Librairie telethon non installee. Run: pip install telethon")


def use_existing_session():
    """
    Utilise une session existante (copier-coller)
    """
    session_string = st.text_area("String Session (copier-coller depuis l'appli)", height=150, help="Copiez-colliez votre session simplement separee par des lignes")
    
    if st.button("Utiliser ma session", type="primary"):
        if not session_string.strip():
            st.error("Veuillez entrer une session valide")
            return
        
        # Valider la session
        try:
            from telethon import TelegramClient
            from telethon.sessions import StringSession
            
            # Fonction async pour valider
            async def _validate():
                client = TelegramClient(StringSession(session_string.strip()))
                async with client:
                    me = await client.get_me()
                    return me
            
            # Executer la validation
            me = asyncio.run(_validate())
            
            # Stocker les infos
            st.session_state.telegram_session = session_string.strip()
            st.session_state.telegram_api_id = str(me.id)
            st.session_state.telegram_api_hash = "# Demande auto-generee #"
            st.session_state.telegram_logged_in = True
            
            st.success(f"Session valide ! Bonjour @{me.first_name} {me.last_name} !")
            
        except Exception as e:
            st.error(f"Erreur: Session invalide - {str(e)}")


def validate_and_connect():
    """
    Valide les identifiants et connecte l'utilisateur
    """
    try:
        # Verifier les credentials
        api_id = st.session_state.get('telegram_api_id')
        api_hash = st.session_state.get('telegram_api_hash')
        session_string = st.session_state.get('telegram_session')
        
        if not api_id or not api_hash:
            st.warning("Veuillez saisir vos identifiants API")
            return
        
        # Connexion avec Telegram
        st.info("Connexion en cours...")
        
        from telethon import TelegramClient
        from telethon.sessions import StringSession
        
        # Fonction async pour connecter
        async def _connect():
            client = TelegramClient(StringSession(session_string), int(api_id), api_hash)
            async with client:
                me = await client.get_me()
                return me
        
        # Executer la connexion
        me = asyncio.run(_connect())
        
        # Stocker les infos
        st.session_state.telegram_logged_in = True
        
        # Afficher le resultat
        st.success(f"Connecte ! Bonjour @{me.first_name} {me.last_name} !")
        
    except Exception as e:
        st.error(f"Erreur de connexion: {str(e)}")
        
    except ImportError:
        st.error("Erreur: Librairie non disponible")


def get_telegram_client() -> TelegramClient:
    """
    Obtient un client Telegram connecte avec la session de l'utilisateur
    Utilise ce fonction dans les autres modules de l'application
    """
    if 'telegram_session' not in st.session_state or not st.session_state.telegram_session:
        raise ValueError("Veuillez d'abord vous connecter a Telegram (Etape 10)")
    
    if 'telegram_api_id' not in st.session_state or 'telegram_api_hash' not in st.session_state:
        raise ValueError("Session invalide - Veuillez vous reconnecter")
    
    # Recuperer les credentials
    api_id = int(st.session_state.telegram_api_id)
    api_hash = st.session_state.telegram_api_hash
    session_string = st.session_state.telegram_session
    
    return TelegramClient(StringSession(session_string), api_id, api_hash)
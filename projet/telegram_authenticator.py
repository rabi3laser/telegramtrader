#!/usr/bin/env python3
"""
MODULE D'AUTHENTIFICATION TELEGRAM POUR STREAMLIT
Version SaaS simple : l'utilisateur entre juste son numero + code SMS
Les credentials API sont geres par l'application (st.secrets)
"""
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError, PhoneCodeExpiredError, PhoneCodeInvalidError
import streamlit as st


def _get_app_credentials():
    """
    Recupere les credentials API de l'application (pas de l'utilisateur).
    Configures dans les secrets Streamlit Cloud.
    """
    try:
        api_id = int(st.secrets["telegram"]["api_id"])
        api_hash = st.secrets["telegram"]["api_hash"]
        return api_id, api_hash
    except (KeyError, AttributeError):
        # Fallback pour le developpement local
        api_id = int(st.secrets.get("TELEGRAM_API_ID", 0))
        api_hash = st.secrets.get("TELEGRAM_API_HASH", "")
        if not api_id or not api_hash:
            st.error("Configuration manquante: contactez l'administrateur")
            st.stop()
        return api_id, api_hash


def init_auth_state():
    defaults = {
        'tg_logged_in': False,
        'tg_phone': '',
        'tg_session': '',
        'tg_phone_hash': '',
        'tg_awaiting_code': False,
        'tg_user_name': '',
        'tg_user_id': None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def show_auth_page() -> bool:
    """
    Page de connexion Telegram simple.
    L'utilisateur entre son numero de telephone et le code recu.
    Retourne True si connecte, False sinon.
    """
    init_auth_state()

    # Deja connecte
    if st.session_state.tg_logged_in:
        name = st.session_state.get('tg_user_name', 'Utilisateur')
        st.success(f"Connecte en tant que {name}")
        col1, col2 = st.columns([3, 1])
        with col2:
            if st.button("Deconnexion", use_container_width=True):
                _logout()
        return True

    # Logo et titre
    st.markdown("<h2>Connexion a Telegram</h2>", unsafe_allow_html=True)

    # -------------------------------------------------------
    # ETAPE 1 : Entrer le numero de telephone
    # -------------------------------------------------------
    if not st.session_state.tg_awaiting_code:
        st.write("Entrez votre numero de telephone Telegram pour recevoir un code de verification.")

        phone = st.text_input(
            "Numero de telephone",
            value=st.session_state.tg_phone,
            placeholder="+33612345678",
            help="Format international: +33 pour la France, +1 pour les US..."
        )

        if st.button("Recevoir le code", type="primary", use_container_width=True):
            if not phone.strip():
                st.error("Veuillez saisir votre numero de telephone")
            else:
                _send_code(phone.strip())

    # -------------------------------------------------------
    # ETAPE 2 : Entrer le code recu
    # -------------------------------------------------------
    else:
        phone = st.session_state.tg_phone
        st.info(f"Un code a ete envoye sur Telegram au numero **{phone}**")
        st.write("Ouvrez Telegram sur votre telephone et entrez le code recu :")

        code = st.text_input(
            "Code de verification",
            placeholder="12345",
            max_chars=6,
            help="Le code envoyé par Telegram (5 chiffres)"
        )

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Confirmer", type="primary", use_container_width=True):
                if not code.strip():
                    st.error("Veuillez entrer le code recu")
                else:
                    _verify_code(code.strip())
        with col2:
            if st.button("Changer de numero", use_container_width=True):
                st.session_state.tg_awaiting_code = False
                st.session_state.tg_phone_hash = ''
                st.rerun()

    return False


def _send_code(phone: str):
    """Envoie un code de verification sur Telegram."""
    api_id, api_hash = _get_app_credentials()

    with st.spinner("Envoi du code en cours..."):
        try:
            async def _do_send():
                client = TelegramClient(StringSession(), api_id, api_hash)
                await client.connect()
                result = await client.send_code_request(phone)
                session_str = client.session.save()
                await client.disconnect()
                return result.phone_code_hash, session_str

            phone_code_hash, session_str = asyncio.run(_do_send())
            st.session_state.tg_phone = phone
            st.session_state.tg_phone_hash = phone_code_hash
            st.session_state.tg_session = session_str
            st.session_state.tg_awaiting_code = True
            st.rerun()

        except Exception as e:
            msg = str(e)
            if 'PHONE_NUMBER_INVALID' in msg:
                st.error("Numero de telephone invalide. Utilisez le format international (+33612345678)")
            elif 'FLOOD' in msg:
                st.error("Trop de tentatives. Attendez quelques minutes avant de reessayer.")
            else:
                st.error(f"Erreur lors de l'envoi du code: {msg}")


def _verify_code(code: str):
    """Verifie le code recu et connecte l'utilisateur."""
    api_id, api_hash = _get_app_credentials()
    session_str = st.session_state.tg_session
    phone = st.session_state.tg_phone
    phone_code_hash = st.session_state.tg_phone_hash

    with st.spinner("Verification en cours..."):
        try:
            async def _do_verify():
                client = TelegramClient(StringSession(session_str), api_id, api_hash)
                await client.connect()
                try:
                    await client.sign_in(
                        phone=phone,
                        code=code,
                        phone_code_hash=phone_code_hash
                    )
                except SessionPasswordNeededError:
                    await client.disconnect()
                    raise ValueError("2FA_REQUIRED")
                me = await client.get_me()
                new_session = client.session.save()
                await client.disconnect()
                return me, new_session

            me, new_session = asyncio.run(_do_verify())

            first = me.first_name or ''
            last = me.last_name or ''
            name = f"{first} {last}".strip() or str(me.id)

            st.session_state.tg_session = new_session
            st.session_state.tg_logged_in = True
            st.session_state.tg_user_name = name
            st.session_state.tg_user_id = me.id
            st.session_state.tg_awaiting_code = False
            st.success(f"Bienvenue {name} !")
            st.rerun()

        except ValueError as e:
            if '2FA_REQUIRED' in str(e):
                st.warning("Votre compte a la verification en 2 etapes activee.")
                _handle_2fa()
            else:
                st.error(str(e))
        except PhoneCodeInvalidError:
            st.error("Code incorrect. Verifiez le code sur Telegram et reessayez.")
        except PhoneCodeExpiredError:
            st.error("Code expire. Cliquez sur Changer de numero pour recommencer.")
            st.session_state.tg_awaiting_code = False
        except Exception as e:
            st.error(f"Erreur: {str(e)}")


def _handle_2fa():
    """Gestion de la verification en 2 etapes (mot de passe Telegram)."""
    api_id, api_hash = _get_app_credentials()
    session_str = st.session_state.tg_session

    password = st.text_input(
        "Mot de passe Telegram (verification en 2 etapes)",
        type="password",
        help="Le mot de passe que vous avez defini dans Telegram > Parametres > Confidentialite > Verification en 2 etapes"
    )
    if st.button("Confirmer le mot de passe", type="primary"):
        with st.spinner("Verification..."):
            try:
                async def _do_2fa():
                    client = TelegramClient(StringSession(session_str), api_id, api_hash)
                    await client.connect()
                    await client.sign_in(password=password)
                    me = await client.get_me()
                    new_session = client.session.save()
                    await client.disconnect()
                    return me, new_session

                me, new_session = asyncio.run(_do_2fa())
                first = me.first_name or ''
                last = me.last_name or ''
                name = f"{first} {last}".strip() or str(me.id)
                st.session_state.tg_session = new_session
                st.session_state.tg_logged_in = True
                st.session_state.tg_user_name = name
                st.session_state.tg_user_id = me.id
                st.session_state.tg_awaiting_code = False
                st.success(f"Bienvenue {name} !")
                st.rerun()
            except Exception as e:
                st.error(f"Mot de passe incorrect: {str(e)}")


def _logout():
    """Deconnecte l'utilisateur."""
    keys = ['tg_logged_in', 'tg_phone', 'tg_session', 'tg_phone_hash',
            'tg_awaiting_code', 'tg_user_name', 'tg_user_id']
    for key in keys:
        if key in st.session_state:
            del st.session_state[key]
    st.rerun()


def get_telegram_client() -> TelegramClient:
    """
    Retourne un TelegramClient configure pour l'utilisateur connecte.
    Utiliser avec 'async with client:' dans les autres modules.
    """
    if not st.session_state.get('tg_session'):
        raise ValueError("Non connecte - veuillez vous connecter")

    api_id, api_hash = _get_app_credentials()
    return TelegramClient(
        StringSession(st.session_state.tg_session),
        api_id,
        api_hash
    )
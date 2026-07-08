"""
Dépendances FastAPI communes aux routers.

Remplace st.session_state.tg_session de l'app Streamlit : le frontend envoie
la session Telethon de l'utilisateur dans le header "Authorization: Bearer {session_string}"
(voir frontend/src/services/api.ts), on l'extrait ici pour les endpoints qui en ont besoin.

Pour les WebSockets (qui ne supportent pas les headers Authorization dans les
navigateurs), le session_string est passé encodé en base64 via le query param
?token=<base64url(session_string)>. La fonction _decode_session_string() gère
ce décodage et est utilisée par ws_connector.py.
"""
import base64
from fastapi import Header, HTTPException
from typing import Optional


async def get_session_string(authorization: Optional[str] = Header(None)) -> str:
    """
    Extrait la session_string Telethon depuis le header Authorization.
    Lève une 401 si absent.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Non authentifié - session Telegram manquante")

    if authorization.lower().startswith("bearer "):
        session_string = authorization[7:].strip()
    else:
        session_string = authorization.strip()

    if not session_string:
        raise HTTPException(status_code=401, detail="Non authentifié - session Telegram manquante")

    return session_string


async def get_optional_session_string(authorization: Optional[str] = Header(None)) -> Optional[str]:
    """Comme get_session_string mais retourne None au lieu de lever une erreur."""
    if not authorization:
        return None
    if authorization.lower().startswith("bearer "):
        session_string = authorization[7:].strip()
    else:
        session_string = authorization.strip()
    return session_string or None


def _decode_session_string(token: str) -> Optional[str]:
    """
    Décode un session_string encodé en base64url (utilisé pour les WebSockets
    qui ne supportent pas les headers Authorization dans les navigateurs).

    Le frontend encode le session_string avec btoa(session_string) avant de
    le passer en query param ?token=... dans l'URL WebSocket.

    Retourne None si le token est invalide ou vide.
    """
    if not token:
        return None
    try:
        # Ajouter le padding base64 si nécessaire
        padded = token + "=" * (4 - len(token) % 4) if len(token) % 4 else token
        decoded = base64.b64decode(padded).decode("utf-8")
        return decoded.strip() or None
    except Exception:
        # Si le décodage échoue, on suppose que c'est le session_string brut
        # (compatibilité avec les clients qui ne font pas l'encodage base64)
        return token.strip() or None

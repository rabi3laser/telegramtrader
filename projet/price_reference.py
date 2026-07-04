"""
MODULE DE RÉFÉRENCE DE PRIX - CAPTURES NINJATRADER
OCR automatique du CalibrationPanel v2

Workflow:
1. Utilisateur uploade une capture du CalibrationPanel NT8
2. OCR Tesseract extrait le texte structuré
3. Regex parse automatiquement toutes les valeurs
4. Sauvegarde dans price_references.json
5. Calcul winrate réel : signaux vs HIGH MAX / LOW MIN de session
"""
import json
import re
import io
from pathlib import Path
from datetime import datetime
from typing import Optional
import streamlit as st

# Chemin du fichier de références de prix
PRICE_REF_FILE = Path(__file__).parent / "price_references.json"

# Mapping des marchés NT8 → identifiants internes
MARKET_PATTERNS = {
    "gold_mgc": {
        "keywords": ["mgc", "gc", "gold", "xau"],
        "name": "Gold (MGC)", "icon": "🥇",
    },
    "mnq_nasdaq": {
        "keywords": ["mnq", "nq", "nasdaq"],
        "name": "Nasdaq (MNQ)", "icon": "📊",
    },
    "mcl_crude": {
        "keywords": ["mcl", "cl", "crude", "oil", "wti"],
        "name": "Crude Oil (MCL)", "icon": "🛢️",
    },
    "mes_sp500": {
        "keywords": ["mes", "es", "sp500", "s&p"],
        "name": "S&P 500 (MES)", "icon": "📈",
    },
}


# ═══════════════════════════════════════════════════════════════
# OCR TESSERACT - EXTRACTION TEXTE
# ═══════════════════════════════════════════════════════════════

def preprocess_image(image_bytes: bytes):
    """
    Prétraitement de l'image pour améliorer l'OCR :
    - Conversion en niveaux de gris
    - Augmentation du contraste
    - Binarisation (fond noir → fond blanc pour Tesseract)
    """
    try:
        from PIL import Image, ImageEnhance, ImageFilter, ImageOps
        import numpy as np

        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")

        # Agrandir l'image pour meilleure précision OCR
        w, h = img.size
        if w < 600:
            scale = 600 / w
            img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

        # Convertir en niveaux de gris
        gray = img.convert("L")

        # Inverser si fond sombre (texte clair sur fond noir = cas NT8)
        arr = list(gray.getdata())
        avg = sum(arr) / len(arr)
        if avg < 128:
            gray = ImageOps.invert(gray)

        # Augmenter le contraste
        enhancer = ImageEnhance.Contrast(gray)
        gray = enhancer.enhance(2.5)

        # Légère netteté
        gray = gray.filter(ImageFilter.SHARPEN)

        return gray
    except Exception as e:
        return None


def ocr_tesseract(image_bytes: bytes) -> Optional[str]:
    """
    Extrait le texte de l'image via Tesseract OCR.
    Retourne None si Tesseract n'est pas disponible.
    """
    try:
        import pytesseract
        from PIL import Image
        import shutil

        # Configurer le chemin Tesseract selon l'OS
        # Streamlit Cloud (Linux/Ubuntu) : /usr/bin/tesseract
        # Windows local : C:/Program Files/Tesseract-OCR/tesseract.exe
        if pytesseract.pytesseract.tesseract_cmd == "tesseract":
            # Chercher automatiquement le binaire
            for candidate in [
                "/usr/bin/tesseract",
                "/usr/local/bin/tesseract",
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            ]:
                if shutil.which(candidate) or (candidate and __import__("os").path.isfile(candidate)):
                    pytesseract.pytesseract.tesseract_cmd = candidate
                    break

        img = preprocess_image(image_bytes)
        if img is None:
            img = Image.open(io.BytesIO(image_bytes)).convert("L")

        # Config Tesseract optimisée pour texte monospace structuré
        config = "--psm 6 --oem 3"

        text = pytesseract.image_to_string(img, config=config, lang="eng")
        return text if text.strip() else None
    except Exception:
        return None


def ocr_ollama(image_bytes: bytes) -> Optional[str]:
    """
    Extrait le texte via Ollama (llava model) - fallback si Tesseract absent.
    """
    try:
        import requests
        import base64

        img_b64 = base64.b64encode(image_bytes).decode("utf-8")
        payload = {
            "model": "llava",
            "prompt": (
                "Read ALL text from this NinjaTrader CalibrationPanel screenshot. "
                "Return ONLY the raw text exactly as displayed, line by line. "
                "Pay special attention to numbers: OPEN, HIGH, LOW, LAST, HIGH MAX, LOW MIN, ATR, VOLUME."
            ),
            "images": [img_b64],
            "stream": False,
        }
        resp = requests.post("http://localhost:11434/api/generate", json=payload, timeout=30)
        if resp.status_code == 200:
            return resp.json().get("response", "")
        return None
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════
# PARSER SPÉCIALISÉ CALIBRATION PANEL v2
# ═══════════════════════════════════════════════════════════════

def _parse_number(s: str) -> Optional[float]:
    """Convertit une chaîne de nombre (avec virgule ou point) en float."""
    if not s:
        return None
    # Remplacer virgule par point (format européen NT8)
    s = s.strip().replace(" ", "").replace(",", ".")
    try:
        return float(s)
    except Exception:
        return None


def parse_calibration_panel(ocr_text: str) -> dict:
    """
    Parse le texte OCR du CalibrationPanel v2 avec des regex précises.
    
    Format attendu (CalibrationPanel v2) :
        INSTRUMENT : MGC AUG26
        TIMEFRAME  : 15 minutes
        DATE       : 30/06/2026   05:00:00
        OPEN  : 3972,60
        HIGH  : 3983,70
        LOW   : 3972,30
        LAST  : 3978,00  (+5,20 / +0,13%)
        BARRE #    : 85
        OPEN SES.  : 4030,80
        HIGH MAX   : 4037,30
        LOW MIN    : 3955,30
        RANGE      : 82,00 pts
        VARIATION  : -52,80 pts (-1,31%)
        ATR(14)    : 12,66
        VOLUME     : 3 122
        TICK SIZE  : 0,10
        SERVER     : 04:55:57
    """
    result = {}
    text = ocr_text

    # ── Instrument ────────────────────────────────────────────
    m = re.search(r"INSTRUMENT\s*[:\|]\s*(.+)", text, re.IGNORECASE)
    if m:
        result["instrument_raw"] = m.group(1).strip()
        instr_lower = result["instrument_raw"].lower()
        for market_id, info in MARKET_PATTERNS.items():
            if any(kw in instr_lower for kw in info["keywords"]):
                result["market"] = market_id
                break

    # ── Timeframe ─────────────────────────────────────────────
    m = re.search(r"TIMEFRAME\s*[:\|]\s*(.+)", text, re.IGNORECASE)
    if m:
        tf_raw = m.group(1).strip()
        result["timeframe_raw"] = tf_raw
        # Extraire le nombre de minutes
        mn = re.search(r"(\d+)", tf_raw)
        if mn:
            result["timeframe"] = mn.group(1)

    # ── Date et Heure ─────────────────────────────────────────
    m = re.search(r"DATE\s*[:\|]\s*(\d{2}/\d{2}/\d{4})\s+(\d{2}:\d{2}:\d{2}(?:\.\d{1,3})?)", text, re.IGNORECASE)
    if m:
        result["date_str"] = m.group(1)
        result["time_str"] = m.group(2)

    # ── BARRE COURANTE : OHLC ─────────────────────────────────
    # OPEN (barre courante - pas OPEN SES.)
    m = re.search(r"^\s*OPEN\s*[:\|]\s*([\d\s,\.]+)", text, re.IGNORECASE | re.MULTILINE)
    if m:
        result["open"] = _parse_number(m.group(1))

    m = re.search(r"^\s*HIGH\s*[:\|]\s*([\d\s,\.]+)", text, re.IGNORECASE | re.MULTILINE)
    if m:
        result["high"] = _parse_number(m.group(1))

    m = re.search(r"^\s*LOW\s*[:\|]\s*([\d\s,\.]+)", text, re.IGNORECASE | re.MULTILINE)
    if m:
        result["low"] = _parse_number(m.group(1))

    m = re.search(r"LAST\s*[:\|]\s*([\d\s,\.]+)", text, re.IGNORECASE)
    if m:
        result["close"] = _parse_number(m.group(1))
        result["price"] = result["close"]

    # ── SESSION : Données cumulatives ─────────────────────────
    m = re.search(r"BARRE\s*#\s*[:\|]\s*(\d+)", text, re.IGNORECASE)
    if m:
        result["session_bar_count"] = int(m.group(1))

    m = re.search(r"OPEN\s+SES[\.S]*\s*[:\|]\s*([\d\s,\.]+)", text, re.IGNORECASE)
    if m:
        result["session_open"] = _parse_number(m.group(1))

    # HIGH MAX = le plus important pour le calcul winrate
    m = re.search(r"HIGH\s+MAX\s*[:\|]\s*([\d\s,\.]+)", text, re.IGNORECASE)
    if m:
        result["session_high"] = _parse_number(m.group(1))

    # LOW MIN = le plus important pour le calcul winrate
    m = re.search(r"LOW\s+MIN\s*[:\|]\s*([\d\s,\.]+)", text, re.IGNORECASE)
    if m:
        result["session_low"] = _parse_number(m.group(1))

    m = re.search(r"RANGE\s*[:\|]\s*([\d\s,\.]+)", text, re.IGNORECASE)
    if m:
        result["session_range"] = _parse_number(m.group(1))

    # ── ATR ───────────────────────────────────────────────────
    m = re.search(r"ATR\s*\(\s*\d+\s*\)\s*[:\|]\s*([\d\s,\.]+)", text, re.IGNORECASE)
    if m:
        result["atr"] = _parse_number(m.group(1))

    # ── Volume ────────────────────────────────────────────────
    m = re.search(r"VOLUME\s*[:\|]\s*([\d\s,\.]+)", text, re.IGNORECASE)
    if m:
        vol_str = m.group(1).strip().replace(" ", "").replace(",", "")
        try:
            result["volume"] = int(vol_str)
        except Exception:
            pass

    # ── Tick Size ─────────────────────────────────────────────
    m = re.search(r"TICK\s+SIZE\s*[:\|]\s*([\d\s,\.]+)", text, re.IGNORECASE)
    if m:
        result["tick_size"] = _parse_number(m.group(1))

    # ── Heure serveur ─────────────────────────────────────────
    m = re.search(r"SERVER\s*[:\|]\s*(\d{2}:\d{2}:\d{2})", text, re.IGNORECASE)
    if m:
        result["server_time"] = m.group(1)

    return result


# ═══════════════════════════════════════════════════════════════
# PERSISTANCE
# ═══════════════════════════════════════════════════════════════

def load_price_references() -> list:
    if PRICE_REF_FILE.exists():
        try:
            with open(PRICE_REF_FILE, "r", encoding="utf-8") as f:
                return json.load(f).get("references", [])
        except Exception:
            return []
    return []


def save_price_reference(ref: dict) -> bool:
    refs = load_price_references()
    ref["id"] = f"{ref.get('market', 'unknown')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    ref["date_added"] = datetime.now().isoformat()
    refs.append(ref)
    try:
        with open(PRICE_REF_FILE, "w", encoding="utf-8") as f:
            json.dump({"references": refs, "last_updated": datetime.now().isoformat()}, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        st.error(f"❌ Erreur sauvegarde: {e}")
        return False


def delete_price_reference(ref_id: str) -> bool:
    refs = [r for r in load_price_references() if r.get("id") != ref_id]
    try:
        with open(PRICE_REF_FILE, "w", encoding="utf-8") as f:
            json.dump({"references": refs, "last_updated": datetime.now().isoformat()}, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


# ═══════════════════════════════════════════════════════════════
# CALCUL WINRATE RÉEL
# ═══════════════════════════════════════════════════════════════

def _ref_datetime(ref: dict):
    """
    Reconstruit un datetime UTC-naive comparable à partir d'une référence NT8
    (date_str format dd/mm/yyyy + time_str format HH:MM:SS).
    Retourne None si la référence n'a pas de date/heure exploitable.
    """
    date_str = ref.get("date_str")
    time_str = ref.get("time_str")
    if not time_str:
        return None
    # Si pas de date_str, utiliser date_added (ISO) ou aujourd'hui
    if not date_str:
        date_added = ref.get("date_added")
        if date_added:
            try:
                return datetime.fromisoformat(date_added).replace(tzinfo=None)
            except Exception:
                pass
        # Fallback: aujourd'hui + time_str
        try:
            today = datetime.now().strftime("%d/%m/%Y")
            return datetime.strptime(f"{today} {time_str}", "%d/%m/%Y %H:%M:%S")
        except Exception:
            return None
    try:
        fmt = "%d/%m/%Y %H:%M:%S.%f" if "." in time_str else "%d/%m/%Y %H:%M:%S"
        return datetime.strptime(f"{date_str} {time_str}", fmt)
    except Exception:
        return None


def _parse_sig_date(sig_date):
    """Convertit sig_date (datetime ou string ISO) en datetime naive comparable."""
    if sig_date is None:
        return None
    # Si c'est déjà un datetime
    if hasattr(sig_date, "year"):
        return sig_date.replace(tzinfo=None) if getattr(sig_date, "tzinfo", None) else sig_date
    # Si c'est une string ISO
    if isinstance(sig_date, str):
        try:
            return datetime.fromisoformat(sig_date).replace(tzinfo=None)
        except Exception:
            return None
    return None


def calculate_real_winrate(signals: list, price_refs: list, market: str, max_time_diff_hours: float = 6.0) -> dict:
    """
    Calcule le vrai winrate en comparant chaque signal Telegram (heure d'émission
    + entry/TP/SL) à la référence de prix NT8 la plus proche EN TEMPS (pas en prix).

    Le prix et l'heure exacts proviennent de l'indicateur CalibrationPanel NT8,
    capturés par l'utilisateur (capture d'écran → OCR → date_str/time_str/session_high/
    session_low). C'est la source de vérité pour le broker réel de l'utilisateur.

    Args:
        signals: signaux extraits par signal_detector.py (clés: type, entry_price,
                 target_price, stop_loss, date)
        price_refs: références NT8 chargées via load_price_references()
        market: identifiant marché interne (gold_mgc, mnq_nasdaq, ...)
        max_time_diff_hours: écart maximum toléré entre l'heure du signal et
                 l'heure de la référence NT8 pour la considérer exploitable
    """
    if not signals or not price_refs:
        return {"winrate": None, "reason": "Pas assez de données"}

    market_refs = [r for r in price_refs if r.get("market") == market]
    if not market_refs:
        return {"winrate": None, "reason": f"Aucune référence NT8 pour {market}"}

    # Pré-calculer les datetimes des références, ignorer celles sans date/heure exploitable
    dated_refs = []
    for r in market_refs:
        dt = _ref_datetime(r)
        if dt is not None:
            dated_refs.append((dt, r))

    trades_won = trades_lost = trades_unknown = 0

    for signal in signals:
        entry = signal.get("entry_price")
        tp    = signal.get("target_price")
        sl    = signal.get("stop_loss")
        direction = (signal.get("type") or "").upper()
        sig_date = signal.get("date")

        if not entry or not tp or not sl or not direction:
            trades_unknown += 1
            continue

        # ── Sélection de la référence par PROXIMITÉ TEMPORELLE (temps réel
        # d'émission du signal), et non par proximité de prix. C'est la
        # correction demandée : l'heure du signal doit matcher l'heure de
        # capture NT8, pas juste "un prix qui ressemble".
        closest_ref = None
        sig_dt = _parse_sig_date(sig_date)
        if sig_dt is not None and dated_refs:
            best_diff = None
            for ref_dt, ref in dated_refs:
                diff_hours = abs((sig_dt - ref_dt).total_seconds()) / 3600
                if diff_hours <= max_time_diff_hours and (best_diff is None or diff_hours < best_diff):
                    best_diff = diff_hours
                    closest_ref = ref

        if not closest_ref:
            # Aucune référence temporellement assez proche du signal → indéterminé
            # (on n'utilise plus le fallback par prix, qui produisait des faux
            # positifs en comparant à des captures d'écran sans rapport temporel)
            trades_unknown += 1
            continue

        # Utiliser SESSION HIGH MAX / LOW MIN si disponibles, sinon HIGH/LOW barre
        ref_high = closest_ref.get("session_high") or closest_ref.get("high") or (closest_ref.get("close") or closest_ref.get("price"))
        ref_low  = closest_ref.get("session_low")  or closest_ref.get("low")  or (closest_ref.get("close") or closest_ref.get("price"))

        if not ref_high or not ref_low:
            trades_unknown += 1
            continue

        if direction == "BUY":
            if ref_high >= tp:   trades_won  += 1
            elif ref_low <= sl:  trades_lost += 1
            else:                trades_unknown += 1
        elif direction == "SELL":
            if ref_low <= tp:    trades_won  += 1
            elif ref_high >= sl: trades_lost += 1
            else:                trades_unknown += 1
        else:
            trades_unknown += 1

    total = trades_won + trades_lost
    if total == 0:
        return {"winrate": None, "trades_won": 0, "trades_lost": 0,
                "trades_unknown": trades_unknown, "total_signals": len(signals),
                "reason": "Aucune référence NT8 assez proche en temps des signaux "
                          f"(tolérance: {max_time_diff_hours}h) — capturez plus de références"}

    return {
        "winrate": round((trades_won / total) * 100, 1),
        "trades_won": trades_won, "trades_lost": trades_lost,
        "trades_unknown": trades_unknown, "total_signals": len(signals),
        "reason": f"{trades_won}/{total} trades gagnants (matching temporel ±{max_time_diff_hours}h)"
    }


# ═══════════════════════════════════════════════════════════════


def calculate_slippage(signals: list, price_refs: list, market: str, max_time_diff_hours: float = 168.0) -> dict:
    if not signals or not price_refs:
        return {'slippage_moyen': None, 'reason': 'Pas assez de donnees'}
    market_refs = [r for r in price_refs if r.get('market') == market]
    if not market_refs:
        return {'slippage_moyen': None, 'reason': f'Aucune reference NT8 pour {market}'}
    dated_refs = []
    for r in market_refs:
        dt = _ref_datetime(r)
        if dt is not None:
            dated_refs.append((dt, r))
    if not dated_refs:
        return {'slippage_moyen': None, 'reason': 'References NT8 sans date/heure exploitable'}
    slippages = []
    details = []
    for signal in signals:
        entry = signal.get('entry_price')
        sig_date = signal.get('date')
        if not entry or not sig_date:
            continue
        sig_dt = _parse_sig_date(sig_date)
        closest_ref = None
        best_diff = None
        for ref_dt, ref in dated_refs:
            diff_hours = abs((sig_dt - ref_dt).total_seconds()) / 3600
            if diff_hours <= max_time_diff_hours and (best_diff is None or diff_hours < best_diff):
                best_diff = diff_hours
                closest_ref = ref
        if not closest_ref:
            continue
        ref_price = closest_ref.get('last') or closest_ref.get('close') or closest_ref.get('price')
        if not ref_price:
            continue
        try:
            entry_float = float(str(entry).replace(',', ''))
            ref_float = float(str(ref_price).replace(',', ''))
            slip = abs(entry_float - ref_float)
            slippages.append(slip)
            details.append({'signal_entry': entry_float, 'nt8_price': ref_float, 'slippage': round(slip, 2), 'time_diff_hours': round(best_diff, 1), 'direction': signal.get('type', '?')})
        except (ValueError, TypeError):
            continue
    if not slippages:
        return {'slippage_moyen': None, 'reason': 'Aucun signal avec entry_price matche a une reference NT8'}
    slippages.sort()
    n = len(slippages)
    slippage_moyen = sum(slippages) / n
    slippage_median = slippages[n // 2] if n % 2 == 1 else (slippages[n // 2 - 1] + slippages[n // 2]) / 2
    return {'slippage_moyen': round(slippage_moyen, 2), 'slippage_median': round(slippage_median, 2), 'slippage_min': round(slippages[0], 2), 'slippage_max': round(slippages[-1], 2), 'nb_comparaisons': n, 'details': details[:10], 'reason': f'Slippage calcule sur {n} signaux'}


# INTERFACE STREAMLIT
# ═══════════════════════════════════════════════════════════════

def show_nt8_price_reference_section():
    """
    Section Streamlit : upload capture NT8 → OCR automatique → sauvegarde.
    """
    st.subheader("📸 Repères de Prix NinjaTrader")
    st.caption("Uploadez une capture du CalibrationPanel NT8 — OCR automatique extrait toutes les valeurs.")

    refs = load_price_references()

    # ── Références existantes ──────────────────────────────────
    if refs:
        st.write(f"**{len(refs)} référence(s) enregistrée(s)**")
        for ref in refs:
            minfo = MARKET_PATTERNS.get(ref.get("market", ""), {})
            icon  = minfo.get("icon", "📊")
            col1, col2, col3, col4 = st.columns([2, 2, 3, 1])
            with col1:
                st.write(f"{icon} **{minfo.get('name', ref.get('market', '?'))}**")
                st.caption(ref.get("time_str", ref.get("date_added", "")[:16]))
            with col2:
                close = ref.get("close") or ref.get("price")
                if close:
                    st.metric("Last", f"{close:,.2f}")
            with col3:
                sh = ref.get("session_high")
                sl = ref.get("session_low")
                if sh and sl:
                    st.caption(f"🔺 HIGH MAX: **{sh:,.2f}**  |  🔻 LOW MIN: **{sl:,.2f}**")
                    st.caption(f"Range session: {sh - sl:,.2f} pts")
                bc = ref.get("session_bar_count")
                if bc:
                    st.caption(f"Barre #{bc} depuis ouverture")
            with col4:
                if st.button("🗑️", key=f"del_ref_{ref.get('id', '')}"):
                    delete_price_reference(ref.get("id", ""))
                    st.rerun()
        st.divider()

    # ── Upload nouvelle capture ────────────────────────────────
    st.write("**➕ Ajouter une référence depuis capture NT8**")

    uploaded_file = st.file_uploader(
        "📸 Capture CalibrationPanel (PNG, JPG)",
        type=["png", "jpg", "jpeg", "bmp"],
        key="nt8_screenshot_upload"
    )

    if uploaded_file:
        image_bytes = uploaded_file.read()
        st.image(image_bytes, caption="Capture NT8 uploadée", use_container_width=True)

        # ── OCR automatique ────────────────────────────────────
        ocr_text = None
        ocr_method = None

        col_ocr1, col_ocr2 = st.columns(2)
        with col_ocr1:
            with st.spinner("🔍 OCR Tesseract en cours..."):
                ocr_text = ocr_tesseract(image_bytes)
                if ocr_text:
                    ocr_method = "Tesseract"

        if not ocr_text:
            with col_ocr2:
                with st.spinner("🔍 Tentative Ollama (llava)..."):
                    ocr_text = ocr_ollama(image_bytes)
                    if ocr_text:
                        ocr_method = "Ollama"

        # ── Parsing du texte OCR ───────────────────────────────
        parsed = {}
        if ocr_text:
            st.success(f"✅ OCR réussi via **{ocr_method}**")
            with st.expander("📄 Texte brut extrait", expanded=False):
                st.code(ocr_text)
            parsed = parse_calibration_panel(ocr_text)
        else:
            st.warning("⚠️ OCR non disponible — saisie manuelle")

        # ── Formulaire de vérification / correction ────────────
        st.write("**Vérifiez les valeurs extraites (corrigez si nécessaire) :**")

        # Marché
        market_options = {v["name"]: k for k, v in MARKET_PATTERNS.items()}
        default_market = parsed.get("market", "gold_mgc")
        default_market_name = next((v["name"] for k, v in MARKET_PATTERNS.items() if k == default_market), list(market_options.keys())[0])
        selected_market_name = st.selectbox("Marché", list(market_options.keys()),
                                            index=list(market_options.keys()).index(default_market_name),
                                            key="nt8_market_sel")
        selected_market = market_options[selected_market_name]

        col1, col2 = st.columns(2)
        with col1:
            date_val = st.text_input("📅 Date (dd/mm/yyyy)", value=parsed.get("date_str", datetime.now().strftime("%d/%m/%Y")), key="nt8_date")
            time_val = st.text_input("⏰ Heure barre (HH:MM:SS)", value=parsed.get("time_str", ""), key="nt8_time")
            open_val = st.number_input("OPEN (barre)", value=float(parsed.get("open") or 0.0), format="%.2f", key="nt8_open")
            high_val = st.number_input("HIGH (barre)", value=float(parsed.get("high") or 0.0), format="%.2f", key="nt8_high")
            low_val  = st.number_input("LOW (barre)",  value=float(parsed.get("low")  or 0.0), format="%.2f", key="nt8_low")
            last_val = st.number_input("LAST (barre)", value=float(parsed.get("close") or 0.0), format="%.2f", key="nt8_last")

        with col2:
            bar_count  = st.number_input("BARRE # (depuis ouverture)", value=int(parsed.get("session_bar_count") or 0), min_value=0, key="nt8_barcount")
            sess_open  = st.number_input("OPEN SESSION", value=float(parsed.get("session_open") or 0.0), format="%.2f", key="nt8_sessopen")
            sess_high  = st.number_input("🔺 HIGH MAX SESSION ← clé pour winrate", value=float(parsed.get("session_high") or 0.0), format="%.2f", key="nt8_sesshigh")
            sess_low   = st.number_input("🔻 LOW MIN SESSION ← clé pour winrate",  value=float(parsed.get("session_low")  or 0.0), format="%.2f", key="nt8_sesslow")
            atr_val    = st.number_input("ATR", value=float(parsed.get("atr") or 0.0), format="%.2f", key="nt8_atr")
            tf_val     = st.text_input("Timeframe", value=parsed.get("timeframe_raw", parsed.get("timeframe", "15")), key="nt8_tf")

        if st.button("💾 SAUVEGARDER CETTE RÉFÉRENCE", type="primary", use_container_width=True):
            if last_val <= 0:
                st.error("❌ Le prix LAST doit être > 0")
            else:
                ref = {
                    "market":             selected_market,
                    "timeframe":          tf_val,
                    "date_str":           date_val,
                    "time_str":           time_val,
                    "open":               open_val  if open_val  > 0 else None,
                    "high":               high_val  if high_val  > 0 else None,
                    "low":                low_val   if low_val   > 0 else None,
                    "close":              last_val,
                    "price":              last_val,
                    "session_open":       sess_open if sess_open > 0 else None,
                    "session_high":       sess_high if sess_high > 0 else None,
                    "session_low":        sess_low  if sess_low  > 0 else None,
                    "session_bar_count":  int(bar_count),
                    "atr":                atr_val   if atr_val   > 0 else None,
                    "ocr_method":         ocr_method or "manual",
                    "source":             "ninja_trader_calibration_panel_v2",
                }
                if save_price_reference(ref):
                    st.success(f"✅ Référence sauvegardée : {selected_market_name} @ {last_val:.2f} | HIGH MAX: {sess_high:.2f} | LOW MIN: {sess_low:.2f}")
                    st.rerun()

    return refs
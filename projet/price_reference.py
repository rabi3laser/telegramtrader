"""
MODULE DE RÉFÉRENCE DE PRIX - CAPTURES NINJATRADER
Extrait les prix depuis des captures d'écran NinjaTrader
pour calculer le vrai winrate des signaux Telegram.

Workflow:
1. Utilisateur uploade une capture NT8 (chart)
2. OCR extrait : heure, OHLC, timeframe, marché
3. Sauvegarde dans price_references.json
4. Comparaison avec signaux Telegram → Winrate réel

Méthodes OCR supportées:
- Ollama (local, gratuit) - si disponible
- Saisie manuelle assistée (fallback universel)
"""
import json
import re
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List
import streamlit as st

# Chemin du fichier de références de prix
PRICE_REF_FILE = Path(__file__).parent / "price_references.json"

# Mapping des marchés NT8 → identifiants internes
MARKET_PATTERNS = {
    "gold_mgc": {
        "keywords": ["gold", "mgc", "gc", "xau", "xauusd", "comex gold", "micro gold"],
        "name": "Gold (MGC)",
        "icon": "🥇",
        "tick_size": 0.10,
        "typical_range": (1500, 3500),
    },
    "mnq_nasdaq": {
        "keywords": ["nasdaq", "mnq", "nq", "qqq", "tech", "micro nasdaq"],
        "name": "Nasdaq (MNQ)",
        "icon": "📊",
        "tick_size": 0.25,
        "typical_range": (10000, 25000),
    },
    "mcl_crude": {
        "keywords": ["crude", "oil", "mcl", "cl", "wti", "brent", "petroleum"],
        "name": "Crude Oil (MCL)",
        "icon": "🛢️",
        "tick_size": 0.01,
        "typical_range": (30, 150),
    },
    "mes_sp500": {
        "keywords": ["sp500", "s&p", "spx", "mes", "es", "spy", "s&p 500"],
        "name": "S&P 500 (MES)",
        "icon": "📈",
        "tick_size": 0.25,
        "typical_range": (3000, 7000),
    },
}

# Patterns regex pour extraire les prix depuis le texte OCR d'un chart NT8
PRICE_PATTERNS = [
    # NT8 Data Box: "Last 2345.60" ou "Close 2345.60"
    r"(?:last|close|price|prix)\s*:?\s*(\d{1,6}\.?\d{0,4})",
    # NT8 OHLC: "O: 2340.10  H: 2350.50  L: 2338.20  C: 2345.60"
    r"(?:open|o)\s*:?\s*(\d{1,6}\.?\d{0,4})",
    r"(?:high|h)\s*:?\s*(\d{1,6}\.?\d{0,4})",
    r"(?:low|l)\s*:?\s*(\d{1,6}\.?\d{0,4})",
    r"(?:close|c)\s*:?\s*(\d{1,6}\.?\d{0,4})",
    # Prix standalone (nombre avec décimale dans la plage typique)
    r"\b(\d{3,6}\.\d{1,4})\b",
]

TIME_PATTERNS = [
    # Format HH:MM:SS ou HH:MM
    r"(\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AP]M)?)",
    # Format avec date: 2026-06-30 14:30:00
    r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}(?::\d{2})?)",
    # Format date US: 06/30/2026 14:30
    r"(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}(?::\d{2})?)",
]

TIMEFRAME_PATTERNS = [
    r"\b(\d+)\s*(?:min|m|minute)\b",
    r"\b(\d+)\s*(?:h|hour|heure)\b",
    r"\b(daily|day|1d|d1)\b",
    r"\b(weekly|week|1w)\b",
]


# ═══════════════════════════════════════════════════════════════
# FONCTIONS DE PERSISTANCE
# ═══════════════════════════════════════════════════════════════

def load_price_references() -> list:
    """Charge les références de prix depuis le fichier JSON."""
    if PRICE_REF_FILE.exists():
        try:
            with open(PRICE_REF_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("references", [])
        except Exception:
            return []
    return []


def save_price_reference(ref: dict) -> bool:
    """Sauvegarde une référence de prix."""
    refs = load_price_references()
    ref["id"] = f"{ref.get('market', 'unknown')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    ref["date_added"] = datetime.now().isoformat()
    refs.append(ref)
    try:
        with open(PRICE_REF_FILE, "w", encoding="utf-8") as f:
            json.dump({"references": refs, "last_updated": datetime.now().isoformat()}, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        st.error(f"❌ Erreur sauvegarde référence: {e}")
        return False


def delete_price_reference(ref_id: str) -> bool:
    """Supprime une référence de prix par son ID."""
    refs = load_price_references()
    refs = [r for r in refs if r.get("id") != ref_id]
    try:
        with open(PRICE_REF_FILE, "w", encoding="utf-8") as f:
            json.dump({"references": refs, "last_updated": datetime.now().isoformat()}, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


# ═══════════════════════════════════════════════════════════════
# EXTRACTION OCR
# ═══════════════════════════════════════════════════════════════

def try_ollama_ocr(image_bytes: bytes) -> Optional[str]:
    """
    Essaie d'extraire le texte via Ollama (llava model).
    Retourne None si Ollama n'est pas disponible.
    """
    try:
        import requests
        import base64

        img_b64 = base64.b64encode(image_bytes).decode("utf-8")
        payload = {
            "model": "llava",
            "prompt": (
                "Extract ALL text visible in this NinjaTrader chart screenshot. "
                "Focus on: price values (OHLC), time/date, instrument name, timeframe. "
                "Return raw text only, no explanation."
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


def parse_ocr_text(ocr_text: str, market_hint: str = None) -> dict:
    """
    Parse le texte OCR pour extraire les informations de prix.
    
    Returns:
        dict avec les champs extraits (peut être incomplet)
    """
    text_lower = ocr_text.lower()
    result = {}

    # 1. Détecter le marché
    if market_hint:
        result["market"] = market_hint
    else:
        for market_id, info in MARKET_PATTERNS.items():
            if any(kw in text_lower for kw in info["keywords"]):
                result["market"] = market_id
                break

    # 2. Extraire les prix OHLC
    # Chercher pattern "O: X H: X L: X C: X"
    ohlc_match = re.search(
        r"o\s*:?\s*(\d+\.?\d*)\s+h\s*:?\s*(\d+\.?\d*)\s+l\s*:?\s*(\d+\.?\d*)\s+c\s*:?\s*(\d+\.?\d*)",
        text_lower
    )
    if ohlc_match:
        result["open"] = float(ohlc_match.group(1))
        result["high"] = float(ohlc_match.group(2))
        result["low"] = float(ohlc_match.group(3))
        result["close"] = float(ohlc_match.group(4))
    else:
        # Chercher prix individuels
        for label, pattern in [
            ("open", r"(?:open|o)\s*:?\s*(\d{1,6}\.?\d{0,4})"),
            ("high", r"(?:high|h)\s*:?\s*(\d{1,6}\.?\d{0,4})"),
            ("low", r"(?:low|l)\s*:?\s*(\d{1,6}\.?\d{0,4})"),
            ("close", r"(?:close|last|c)\s*:?\s*(\d{1,6}\.?\d{0,4})"),
        ]:
            m = re.search(pattern, text_lower)
            if m:
                result[label] = float(m.group(1))

    # 3. Extraire l'heure
    for pattern in TIME_PATTERNS:
        m = re.search(pattern, ocr_text, re.IGNORECASE)
        if m:
            result["time_str"] = m.group(1)
            break

    # 4. Extraire le timeframe
    for pattern in TIMEFRAME_PATTERNS:
        m = re.search(pattern, text_lower)
        if m:
            result["timeframe"] = m.group(1)
            break

    return result


# ═══════════════════════════════════════════════════════════════
# CALCUL DU VRAI WINRATE
# ═══════════════════════════════════════════════════════════════

def calculate_real_winrate(signals: list, price_refs: list, market: str) -> dict:
    """
    Calcule le vrai winrate en comparant les signaux avec les références de prix NT8.
    
    Args:
        signals: Liste de signaux détectés (avec entry, tp, sl, date)
        price_refs: Liste de références de prix NT8
        market: Marché concerné
        
    Returns:
        dict avec winrate, trades_won, trades_lost, trades_unknown
    """
    if not signals or not price_refs:
        return {"winrate": None, "reason": "Pas assez de données"}

    # Filtrer les références pour ce marché
    market_refs = [r for r in price_refs if r.get("market") == market]
    if not market_refs:
        return {"winrate": None, "reason": f"Aucune référence NT8 pour {market}"}

    trades_won = 0
    trades_lost = 0
    trades_unknown = 0

    for signal in signals:
        entry = signal.get("entry_price")
        tp = signal.get("tp_price")
        sl = signal.get("sl_price")
        direction = signal.get("direction", "").upper()  # BUY ou SELL
        signal_time = signal.get("date")

        if not entry or not tp or not sl:
            trades_unknown += 1
            continue

        # Trouver la référence de prix la plus proche dans le temps
        closest_ref = None
        min_diff = float("inf")
        for ref in market_refs:
            ref_close = ref.get("close") or ref.get("price")
            if not ref_close:
                continue
            # Utiliser le close comme prix de référence
            diff = abs(ref_close - entry)
            if diff < min_diff:
                min_diff = diff
                closest_ref = ref

        if not closest_ref:
            trades_unknown += 1
            continue

        ref_price = closest_ref.get("close") or closest_ref.get("price")
        ref_high = closest_ref.get("high", ref_price)
        ref_low = closest_ref.get("low", ref_price)

        # Vérifier si TP ou SL a été atteint
        if direction == "BUY":
            # Pour un BUY : TP atteint si high >= tp, SL atteint si low <= sl
            if ref_high >= tp:
                trades_won += 1
            elif ref_low <= sl:
                trades_lost += 1
            else:
                trades_unknown += 1
        elif direction == "SELL":
            # Pour un SELL : TP atteint si low <= tp, SL atteint si high >= sl
            if ref_low <= tp:
                trades_won += 1
            elif ref_high >= sl:
                trades_lost += 1
            else:
                trades_unknown += 1
        else:
            trades_unknown += 1

    total_decided = trades_won + trades_lost
    if total_decided == 0:
        return {
            "winrate": None,
            "trades_won": 0,
            "trades_lost": 0,
            "trades_unknown": trades_unknown,
            "reason": "Impossible de déterminer TP/SL depuis les références"
        }

    winrate = round((trades_won / total_decided) * 100, 1)
    return {
        "winrate": winrate,
        "trades_won": trades_won,
        "trades_lost": trades_lost,
        "trades_unknown": trades_unknown,
        "total_signals": len(signals),
        "reason": f"{trades_won}/{total_decided} trades gagnants"
    }


# ═══════════════════════════════════════════════════════════════
# INTERFACE STREAMLIT - SECTION UPLOAD NT8
# ═══════════════════════════════════════════════════════════════

def show_nt8_price_reference_section():
    """
    Affiche la section d'upload de captures NT8 dans Streamlit.
    Retourne la liste des références de prix sauvegardées.
    """
    st.subheader("📸 Repères de Prix NinjaTrader")
    st.caption("Uploadez des captures d'écran de vos charts NT8 pour calibrer le winrate réel.")

    refs = load_price_references()

    # ── Références existantes ──
    if refs:
        st.write(f"**{len(refs)} référence(s) de prix enregistrée(s)**")
        for ref in refs:
            market_info = MARKET_PATTERNS.get(ref.get("market", ""), {})
            icon = market_info.get("icon", "📊")
            col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
            with col1:
                st.write(f"{icon} **{market_info.get('name', ref.get('market', '?'))}**")
                st.caption(ref.get("time_str", ref.get("date_added", "")[:16]))
            with col2:
                close = ref.get("close") or ref.get("price")
                if close:
                    st.metric("Prix Close", f"{close:,.2f}")
            with col3:
                high = ref.get("high")
                low = ref.get("low")
                if high and low:
                    st.caption(f"H: {high:,.2f} | L: {low:,.2f}")
                tf = ref.get("timeframe")
                if tf:
                    st.caption(f"Timeframe: {tf}min")
            with col4:
                if st.button("🗑️", key=f"del_ref_{ref.get('id', '')}"):
                    delete_price_reference(ref.get("id", ""))
                    st.rerun()
        st.divider()

    # ── Upload nouvelle capture ──
    st.write("**➕ Ajouter une nouvelle référence de prix**")

    col_market, col_tf = st.columns(2)
    with col_market:
        market_options = {v["name"]: k for k, v in MARKET_PATTERNS.items()}
        selected_market_name = st.selectbox(
            "Marché de la capture",
            options=list(market_options.keys()),
            key="nt8_market_select"
        )
        selected_market = market_options[selected_market_name]
    with col_tf:
        timeframe = st.selectbox(
            "Timeframe du chart",
            options=["1", "3", "5", "15", "30", "60", "240", "D"],
            index=3,  # 15min par défaut
            key="nt8_timeframe_select"
        )

    uploaded_file = st.file_uploader(
        "📸 Capture d'écran NinjaTrader (PNG, JPG)",
        type=["png", "jpg", "jpeg", "bmp"],
        key="nt8_screenshot_upload"
    )

    if uploaded_file:
        image_bytes = uploaded_file.read()

        # Afficher l'image
        st.image(image_bytes, caption="Capture NT8 uploadée", use_container_width=True)

        # Essayer OCR Ollama
        ocr_text = None
        with st.spinner("🔍 Tentative d'extraction automatique (Ollama)..."):
            ocr_text = try_ollama_ocr(image_bytes)

        if ocr_text:
            st.success("✅ OCR Ollama réussi!")
            parsed = parse_ocr_text(ocr_text, selected_market)
            st.caption(f"Texte extrait: {ocr_text[:200]}...")
        else:
            st.info("ℹ️ OCR automatique non disponible — Saisie manuelle")
            parsed = {"market": selected_market}

        # Formulaire de saisie/correction manuelle
        st.write("**Vérifiez et complétez les valeurs extraites :**")

        col1, col2 = st.columns(2)
        with col1:
            time_str = st.text_input(
                "⏰ Heure de la capture (HH:MM ou HH:MM:SS)",
                value=parsed.get("time_str", datetime.now().strftime("%H:%M")),
                key="nt8_time_input"
            )
            price_open = st.number_input(
                "📊 Open",
                value=float(parsed.get("open", 0.0)),
                format="%.2f",
                key="nt8_open_input"
            )
            price_high = st.number_input(
                "📈 High",
                value=float(parsed.get("high", 0.0)),
                format="%.2f",
                key="nt8_high_input"
            )
        with col2:
            date_str = st.date_input(
                "📅 Date de la capture",
                value=datetime.now().date(),
                key="nt8_date_input"
            )
            price_low = st.number_input(
                "📉 Low",
                value=float(parsed.get("low", 0.0)),
                format="%.2f",
                key="nt8_low_input"
            )
            price_close = st.number_input(
                "💰 Close / Last (prix principal)",
                value=float(parsed.get("close", 0.0)),
                format="%.2f",
                key="nt8_close_input"
            )

        notes = st.text_input("📝 Notes (optionnel)", key="nt8_notes_input")

        if st.button("💾 SAUVEGARDER CETTE RÉFÉRENCE", type="primary", use_container_width=True):
            if price_close <= 0:
                st.error("❌ Le prix Close doit être > 0")
            else:
                # Construire la référence
                try:
                    dt_str = f"{date_str}T{time_str}:00" if ":" in time_str else f"{date_str}T{time_str}:00:00"
                except Exception:
                    dt_str = datetime.now().isoformat()

                ref = {
                    "market": selected_market,
                    "timeframe": timeframe,
                    "time_str": time_str,
                    "date_str": str(date_str),
                    "datetime": dt_str,
                    "open": price_open if price_open > 0 else None,
                    "high": price_high if price_high > 0 else None,
                    "low": price_low if price_low > 0 else None,
                    "close": price_close,
                    "price": price_close,  # alias
                    "notes": notes,
                    "ocr_used": ocr_text is not None,
                    "source": "ninja_trader_screenshot",
                }

                if save_price_reference(ref):
                    st.success(f"✅ Référence sauvegardée: {selected_market_name} @ {price_close:.2f} ({time_str})")
                    st.rerun()

    return refs
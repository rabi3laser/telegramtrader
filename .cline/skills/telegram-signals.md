# Skill: Telegram Signals Analysis

## Structure des données
- **Signal**: `{type: "BUY"|"SELL", entry_price: float, target_price: float, stop_loss: float, date: datetime|ISO string}`
- **Référence NT8**: `{market: "gold_mgc"|"mnq_nasdaq"|..., date_str: "dd/mm/yyyy", time_str: "HH:MM:SS[.fff]", session_high: float, session_low: float, close: float}`
- **Calibration**: `{score: 0-100, status: "activated"|"short_test"|"rejected", metrics: {total_signals, signals_per_day, avg_quality, hours_since_last_signal}}`

## Score (0-100)
- Nombre signaux: 30pts (≥30=30, ≥20=25, ≥15=20, ≥10=15, ≥5=10)
- Fréquence: 25pts (≥3/j=25, ≥2=20, ≥1.5=15, ≥1=10)
- Qualité: 20pts (avg_quality/10 * 20)
- Récence: 15pts (≤6h=15, ≤12h=12, ≤24h=8, ≤48h=4)
- Diversité marchés: 5pts (min(markets*2, 5))
- Membres: 5pts (≥5000=5, ≥2000=4, ≥1000=3)

## Statuts
- `activated`: score ≥ 70, signals ≥ 15, quality ≥ 6
- `short_test`: score ≥ 50, signals ≥ 8, quality ≥ 4
- `rejected`: en dessous

## Matching temporel winrate
- Tolérance: ±168h (7 jours)
- BUY: HIGH MAX ≥ TP → gagnant, LOW MIN ≤ SL → perdant
- SELL: LOW MIN ≤ TP → gagnant, HIGH MAX ≥ SL → perdant

## Slippage
- slippage = |entry_price_signal - prix_réel_NT8|
- Moyenne/médiane/min/max par canal

## Fallbacks datetime
- `_ref_datetime`: date_str+time_str → date_added → today+time_str
- `_parse_sig_date`: datetime object → string ISO → None
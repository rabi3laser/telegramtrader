// ============================================================
// CALIBRATION PANEL - INDICATEUR NINJATRADER 8
// VERSION 2.0 - Avec compteur de session et OHLC cumulatif
// ============================================================
// Affiche les données de la barre courante ET les données
// cumulatives depuis l'ouverture de session.
// L'utilisateur n'a qu'à lire et saisir dans Streamlit.
//
// INSTALLATION:
// 1. Copier dans: Documents\NinjaTrader 8\bin\Custom\Indicators\
// 2. NinjaTrader → Tools → Edit NinjaScript → Compile (F5)
// 3. Chart → Clic droit → Indicators → CalibrationPanel → Add
// ============================================================

#region Using declarations
using System;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Windows.Media;
using NinjaTrader.Cbi;
using NinjaTrader.Gui;
using NinjaTrader.Gui.Chart;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.DrawingTools;
#endregion

namespace NinjaTrader.NinjaScript.Indicators
{
    public class CalibrationPanel : Indicator
    {
        // ── Variables de session ──────────────────────────────
        private int    _barCount    = 0;
        private double _sessHigh    = double.MinValue;
        private double _sessLow     = double.MaxValue;
        private double _sessOpen    = 0;
        private string _sessStart   = "";

        // Conversion position : 0=TopLeft, 1=TopRight, 2=BottomLeft, 3=BottomRight
        private TextPosition GetTextPosition()
        {
            switch (PanelPosition)
            {
                case 1:  return TextPosition.TopRight;
                case 2:  return TextPosition.BottomLeft;
                case 3:  return TextPosition.BottomRight;
                default: return TextPosition.TopLeft;
            }
        }

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description               = "Panneau OHLC + Session pour calibration Streamlit";
                Name                      = "CalibrationPanel";
                Calculate                 = Calculate.OnEachTick;
                IsOverlay                 = true;
                DisplayInDataBox          = false;
                DrawOnPricePanel          = true;
                PaintPriceMarkers         = false;
                IsSuspendedWhileInactive  = false;

                PanelPosition = 0;
                FontSize      = 12;
                ATRPeriod     = 14;
                ShowATR       = true;
                ShowVolume    = true;
            }
        }

        protected override void OnBarUpdate()
        {
            if (CurrentBar < 2)
                return;

            // ── Mise à jour des données de session ────────────
            if (Bars.IsFirstBarOfSession)
            {
                // Nouvelle session : réinitialiser les compteurs
                _barCount  = 1;
                _sessHigh  = High[0];
                _sessLow   = Low[0];
                _sessOpen  = Open[0];
                _sessStart = Time[0].ToString("HH:mm");
            }
            else
            {
                _barCount++;
                if (High[0] > _sessHigh) _sessHigh = High[0];
                if (Low[0]  < _sessLow)  _sessLow  = Low[0];
            }

            try
            {
                // ── Données barre courante ────────────────────
                double last    = Close[0];
                double open    = Open[0];
                double high    = High[0];
                double low     = Low[0];
                double prev    = Close[1];
                long   vol     = (long)Volume[0];
                double chg     = last - prev;
                double chgPct  = prev != 0 ? (chg / prev) * 100.0 : 0.0;
                string chgSign = chg >= 0 ? "+" : "";

                // ── Données session ───────────────────────────
                double sessRange   = _sessHigh - _sessLow;
                double sessChange  = last - _sessOpen;
                double sessChgPct  = _sessOpen != 0 ? (sessChange / _sessOpen) * 100.0 : 0.0;
                string sessChgSign = sessChange >= 0 ? "+" : "";

                // ── ATR ───────────────────────────────────────
                string atrStr = "";
                if (ShowATR && CurrentBar >= ATRPeriod)
                {
                    try
                    {
                        double atr = ATR(ATRPeriod)[0];
                        atrStr = string.Format("  ATR({0})    : {1:F2}\n", ATRPeriod, atr);
                    }
                    catch { }
                }

                // ── Volume ────────────────────────────────────
                string volStr = ShowVolume
                    ? string.Format("  VOLUME     : {0:N0}\n", vol)
                    : "";

                // ── Heure / Date (avec millisecondes pour précision broker) ──
                string barTime = Time[0].ToString("HH:mm:ss.fff");
                string barDate = Time[0].ToString("dd/MM/yyyy");
                string srvTime = DateTime.Now.ToString("HH:mm:ss.fff");

                // ── Instrument / Timeframe ────────────────────
                string instr = Instrument.FullName;
                string tf    = BarsPeriod.ToString();
                double tick  = Instrument.MasterInstrument.TickSize;

                // ── Construction du texte ─────────────────────
                string line = "  " + new string('-', 34) + "\n";

                string text =
                    "  === CALIBRATION PANEL v2 ===\n" +
                    line +
                    string.Format("  INSTRUMENT : {0}\n", instr) +
                    string.Format("  TIMEFRAME  : {0}\n", tf) +
                    string.Format("  DATE       : {0}   {1}\n", barDate, barTime) +
                    line +
                    "  -- BARRE COURANTE --\n" +
                    string.Format("  OPEN  : {0:F2}\n", open) +
                    string.Format("  HIGH  : {0:F2}\n", high) +
                    string.Format("  LOW   : {0:F2}\n", low) +
                    string.Format("  LAST  : {0:F2}  ({1}{2:F2} / {1}{3:F2}%)\n",
                        last, chgSign, chg, chgPct) +
                    line +
                    string.Format("  -- DEPUIS OUVERTURE SESSION ({0}) --\n", _sessStart) +
                    string.Format("  BARRE #    : {0}\n", _barCount) +
                    string.Format("  OPEN SES.  : {0:F2}\n", _sessOpen) +
                    string.Format("  HIGH MAX   : {0:F2}  << SAISIR DANS STREAMLIT\n", _sessHigh) +
                    string.Format("  LOW MIN    : {0:F2}  << SAISIR DANS STREAMLIT\n", _sessLow) +
                    string.Format("  RANGE      : {0:F2} pts\n", sessRange) +
                    string.Format("  VARIATION  : {0}{1:F2} pts ({0}{2:F2}%)\n",
                        sessChgSign, sessChange, sessChgPct) +
                    line +
                    atrStr +
                    volStr +
                    string.Format("  TICK SIZE  : {0:F2}\n", tick) +
                    line +
                    string.Format("  SERVER     : {0}\n", srvTime) +
                    "  ==============================";

                // ── Affichage ─────────────────────────────────
                Draw.TextFixed(
                    this,
                    "CalibrationPanel_Text",
                    text,
                    GetTextPosition(),
                    Brushes.Cyan,
                    null,
                    Brushes.Transparent,
                    Brushes.Black,
                    220
                );
            }
            catch (Exception ex)
            {
                Draw.TextFixed(
                    this,
                    "CalibrationPanel_Text",
                    "CalibrationPanel ERROR:\n" + ex.Message,
                    TextPosition.TopLeft,
                    Brushes.Red,
                    null,
                    Brushes.Transparent,
                    Brushes.Black,
                    200
                );
            }
        }

        // ── Propriétés configurables ──────────────────────────

        [NinjaScriptProperty]
        [Range(0, 3)]
        [Display(Name = "Position (0=TopLeft 1=TopRight 2=BotLeft 3=BotRight)", Order = 1, GroupName = "Panneau")]
        public int PanelPosition { get; set; }

        [NinjaScriptProperty]
        [Range(8, 24)]
        [Display(Name = "Taille de police", Order = 2, GroupName = "Panneau")]
        public int FontSize { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Afficher ATR", Order = 3, GroupName = "Métriques")]
        public bool ShowATR { get; set; }

        [NinjaScriptProperty]
        [Range(1, 100)]
        [Display(Name = "Période ATR", Order = 4, GroupName = "Métriques")]
        public int ATRPeriod { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Afficher Volume", Order = 5, GroupName = "Métriques")]
        public bool ShowVolume { get; set; }
    }
}
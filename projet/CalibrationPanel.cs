// ============================================================
// CALIBRATION PANEL - INDICATEUR NINJATRADER 8
// VERSION UNIVERSELLE - Compatible toutes versions NT8
// ============================================================
// Utilise Draw.TextFixed() - méthode standard NT8
// Aucune dépendance DirectX/SharpDX
//
// INSTALLATION:
// 1. Copier ce fichier dans:
//    C:\Users\[Votre Nom]\Documents\NinjaTrader 8\bin\Custom\Indicators\
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
        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description               = "Panneau OHLC pour calibration Streamlit - Compatible toutes versions NT8";
                Name                      = "CalibrationPanel";
                Calculate                 = Calculate.OnEachTick;
                IsOverlay                 = true;
                DisplayInDataBox          = false;
                DrawOnPricePanel          = true;
                PaintPriceMarkers         = false;
                IsSuspendedWhileInactive  = false;

                // Paramètres par défaut
                PanelPosition = TextPosition.TopLeft;
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

            try
            {
                // ── Données de la barre courante ──────────────
                double last    = Close[0];
                double open    = Open[0];
                double high    = High[0];
                double low     = Low[0];
                double prev    = Close[1];
                long   vol     = (long)Volume[0];
                double chg     = last - prev;
                double chgPct  = prev != 0 ? (chg / prev) * 100.0 : 0.0;
                string chgSign = chg >= 0 ? "+" : "";

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

                // ── Heure / Date ──────────────────────────────
                string barTime = Time[0].ToString("HH:mm:ss");
                string barDate = Time[0].ToString("dd/MM/yyyy");
                string srvTime = DateTime.Now.ToString("HH:mm:ss");

                // ── Instrument / Timeframe ────────────────────
                string instr = Instrument.FullName;
                string tf    = BarsPeriod.ToString();

                // ── Tick size ─────────────────────────────────
                double tick = Instrument.MasterInstrument.TickSize;

                // ── Construction du texte ─────────────────────
                string line = "  " + new string('-', 34) + "\n";

                string text =
                    "  === CALIBRATION PANEL ===\n" +
                    line +
                    string.Format("  INSTRUMENT : {0}\n", instr) +
                    string.Format("  TIMEFRAME  : {0}\n", tf) +
                    line +
                    string.Format("  DATE       : {0}\n", barDate) +
                    string.Format("  BAR TIME   : {0}\n", barTime) +
                    line +
                    string.Format("  OPEN       : {0:F2}\n", open) +
                    string.Format("  HIGH       : {0:F2}\n", high) +
                    string.Format("  LOW        : {0:F2}\n", low) +
                    string.Format("  LAST       : {0:F2}  ({1}{2:F2} / {1}{3:F2}%)\n",
                        last, chgSign, chg, chgPct) +
                    line +
                    atrStr +
                    volStr +
                    string.Format("  TICK SIZE  : {0:F2}\n", tick) +
                    line +
                    string.Format("  SERVER     : {0}\n", srvTime) +
                    "  ==========================";

                // ── Affichage avec Draw.TextFixed ─────────────
                Draw.TextFixed(
                    this,
                    "CalibrationPanel_Text",
                    text,
                    PanelPosition,
                    Brushes.Cyan,
                    new SimpleFont("Courier New", FontSize),
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
                    new SimpleFont("Courier New", 11),
                    Brushes.Transparent,
                    Brushes.Black,
                    200
                );
            }
        }

        // ── Propriétés configurables ──────────────────────────

        [NinjaScriptProperty]
        [Display(Name = "Position du panneau", Order = 1, GroupName = "Panneau")]
        public TextPosition PanelPosition { get; set; }

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
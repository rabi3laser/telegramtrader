// ============================================================
// CALIBRATION PANEL - INDICATEUR NINJATRADER 8
// ============================================================
// Affiche un panneau d'information complet sur le chart
// pour faciliter la capture d'écran et l'OCR par Streamlit.
//
// INSTALLATION:
// 1. Copier ce fichier dans:
//    C:\Users\[Votre Nom]\Documents\NinjaTrader 8\bin\Custom\Indicators\
// 2. Dans NinjaTrader: Tools → Edit NinjaScript → Compile
// 3. Sur un chart: Indicators → CalibrationPanel → Add
//
// UTILISATION:
// 1. Ajouter l'indicateur sur le chart du marché à calibrer
// 2. Faire une capture d'écran (Win + Shift + S ou PrintScreen)
// 3. Uploader dans Streamlit → Section "Repères de Prix NT8"
// ============================================================

#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Windows.Media;
using NinjaTrader.Cbi;
using NinjaTrader.Gui;
using NinjaTrader.Gui.Chart;
using NinjaTrader.Gui.SuperDom;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;
using NinjaTrader.Core.FloatingPoint;
using NinjaTrader.NinjaScript.DrawingTools;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using SharpDX;
using SharpDX.Direct2D1;
using SharpDX.DirectWrite;
#endregion

namespace NinjaTrader.NinjaScript.Indicators
{
    public class CalibrationPanel : Indicator
    {
        // ── Paramètres configurables ──────────────────────────
        private int panelX = 10;
        private int panelY = 10;
        private int fontSize = 14;
        private bool showATR = true;
        private bool showVolume = true;
        private bool showSpread = true;
        private int atrPeriod = 14;

        // ── Ressources DirectX ────────────────────────────────
        private SharpDX.Direct2D1.Brush bgBrush;
        private SharpDX.Direct2D1.Brush borderBrush;
        private SharpDX.Direct2D1.Brush titleBrush;
        private SharpDX.Direct2D1.Brush priceBrush;
        private SharpDX.Direct2D1.Brush labelBrush;
        private SharpDX.Direct2D1.Brush upBrush;
        private SharpDX.Direct2D1.Brush downBrush;
        private SharpDX.Direct2D1.Brush separatorBrush;

        private SharpDX.DirectWrite.TextFormat titleFormat;
        private SharpDX.DirectWrite.TextFormat priceFormat;
        private SharpDX.DirectWrite.TextFormat labelFormat;
        private SharpDX.DirectWrite.TextFormat smallFormat;

        private SharpDX.DirectWrite.Factory dwFactory;

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = "Panneau de calibration pour Streamlit - Affiche OHLCV, ATR, Heure";
                Name = "CalibrationPanel";
                Calculate = Calculate.OnEachTick;
                IsOverlay = true;
                DisplayInDataBox = false;
                DrawOnPricePanel = true;
                PaintPriceMarkers = false;
                ScaleJustification = NinjaTrader.Gui.Chart.ScaleJustification.Right;
                IsSuspendedWhileInactive = false;

                // Paramètres par défaut
                PanelX = 10;
                PanelY = 10;
                FontSize = 14;
                ShowATR = true;
                ShowVolume = true;
                ShowSpread = true;
                ATRPeriod = 14;
                BackgroundOpacity = 200;
            }
            else if (State == State.Configure)
            {
                if (ShowATR)
                    AddDataSeries(BarsPeriodType.Tick, 1);
            }
            else if (State == State.Terminated)
            {
                DisposeResources();
            }
        }

        protected override void OnBarUpdate()
        {
            // Forcer le redessin à chaque tick
        }

        protected override void OnRender(ChartControl chartControl, ChartScale chartScale)
        {
            if (RenderTarget == null || Bars == null || CurrentBar < 1)
                return;

            try
            {
                InitResources();
                DrawPanel(chartControl, chartScale);
            }
            catch (Exception ex)
            {
                // Silencieux pour ne pas bloquer le chart
            }
        }

        private void InitResources()
        {
            if (dwFactory == null)
                dwFactory = new SharpDX.DirectWrite.Factory();

            // Couleurs du panneau
            var bgColor = new SharpDX.Color4(0.05f, 0.05f, 0.10f, BackgroundOpacity / 255f);
            var borderColor = new SharpDX.Color4(0.3f, 0.6f, 1.0f, 1.0f);
            var titleColor = new SharpDX.Color4(0.3f, 0.8f, 1.0f, 1.0f);
            var priceColor = new SharpDX.Color4(1.0f, 1.0f, 1.0f, 1.0f);
            var labelColor = new SharpDX.Color4(0.7f, 0.7f, 0.7f, 1.0f);
            var upColor = new SharpDX.Color4(0.0f, 0.9f, 0.4f, 1.0f);
            var downColor = new SharpDX.Color4(1.0f, 0.3f, 0.3f, 1.0f);
            var sepColor = new SharpDX.Color4(0.3f, 0.3f, 0.4f, 1.0f);

            if (bgBrush == null) bgBrush = new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, bgColor);
            if (borderBrush == null) borderBrush = new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, borderColor);
            if (titleBrush == null) titleBrush = new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, titleColor);
            if (priceBrush == null) priceBrush = new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, priceColor);
            if (labelBrush == null) labelBrush = new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, labelColor);
            if (upBrush == null) upBrush = new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, upColor);
            if (downBrush == null) downBrush = new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, downColor);
            if (separatorBrush == null) separatorBrush = new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, sepColor);

            if (titleFormat == null)
                titleFormat = new SharpDX.DirectWrite.TextFormat(dwFactory, "Consolas", FontSize + 2)
                { TextAlignment = SharpDX.DirectWrite.TextAlignment.Leading };

            if (priceFormat == null)
                priceFormat = new SharpDX.DirectWrite.TextFormat(dwFactory, "Consolas", FontSize + 4)
                { TextAlignment = SharpDX.DirectWrite.TextAlignment.Leading };

            if (labelFormat == null)
                labelFormat = new SharpDX.DirectWrite.TextFormat(dwFactory, "Consolas", FontSize)
                { TextAlignment = SharpDX.DirectWrite.TextAlignment.Leading };

            if (smallFormat == null)
                smallFormat = new SharpDX.DirectWrite.TextFormat(dwFactory, "Consolas", FontSize - 2)
                { TextAlignment = SharpDX.DirectWrite.TextAlignment.Leading };
        }

        private void DrawPanel(ChartControl chartControl, ChartScale chartScale)
        {
            // ── Collecte des données ──────────────────────────
            double lastPrice = Close[0];
            double openPrice = Open[0];
            double highPrice = High[0];
            double lowPrice = Low[0];
            double prevClose = CurrentBar > 0 ? Close[1] : lastPrice;
            long volume = (long)Volume[0];
            double change = lastPrice - prevClose;
            double changePct = prevClose != 0 ? (change / prevClose) * 100 : 0;

            // ATR
            double atrValue = 0;
            if (ShowATR && CurrentBar >= ATRPeriod)
            {
                try { atrValue = ATR(ATRPeriod)[0]; }
                catch { }
            }

            // Heure et date
            DateTime barTime = Time[0];
            string timeStr = barTime.ToString("HH:mm:ss");
            string dateStr = barTime.ToString("dd/MM/yyyy");
            string serverTime = DateTime.Now.ToString("HH:mm:ss.fff");

            // Nom de l'instrument
            string instrument = Instrument.FullName;
            string timeframe = BarsPeriod.ToString();

            // Spread (si disponible)
            double spread = 0;
            try
            {
                if (Instrument.MasterInstrument != null)
                    spread = Instrument.MasterInstrument.TickSize;
            }
            catch { }

            // ── Calcul de la taille du panneau ───────────────
            float panelWidth = 320;
            float lineHeight = FontSize + 8;
            float padding = 12;
            float titleHeight = lineHeight + 4;
            float separatorH = 2;

            int lineCount = 8; // Lignes de base
            if (ShowATR) lineCount++;
            if (ShowVolume) lineCount++;
            if (ShowSpread) lineCount++;

            float panelHeight = padding * 2 + titleHeight + separatorH + lineCount * lineHeight + 10;

            // ── Dessin du fond ────────────────────────────────
            var panelRect = new SharpDX.RectangleF(PanelX, PanelY, panelWidth, panelHeight);
            RenderTarget.FillRectangle(panelRect, bgBrush);
            RenderTarget.DrawRectangle(panelRect, borderBrush, 2.0f);

            // ── Titre ─────────────────────────────────────────
            float y = PanelY + padding;
            float x = PanelX + padding;
            float w = panelWidth - padding * 2;

            string titleText = $"CALIBRATION PANEL";
            DrawText(titleText, titleFormat, titleBrush, x, y, w, lineHeight);
            y += lineHeight;

            // Ligne séparatrice
            RenderTarget.DrawLine(
                new SharpDX.Vector2(PanelX + 4, y),
                new SharpDX.Vector2(PanelX + panelWidth - 4, y),
                borderBrush, 1.5f
            );
            y += separatorH + 4;

            // ── Instrument + Timeframe ────────────────────────
            DrawLabelValue("INSTRUMENT", instrument, labelFormat, priceFormat, labelBrush, priceBrush, x, y, w, lineHeight);
            y += lineHeight;

            DrawLabelValue("TIMEFRAME ", timeframe, labelFormat, priceFormat, labelBrush, priceBrush, x, y, w, lineHeight);
            y += lineHeight;

            // Ligne séparatrice
            RenderTarget.DrawLine(
                new SharpDX.Vector2(PanelX + 4, y),
                new SharpDX.Vector2(PanelX + panelWidth - 4, y),
                separatorBrush, 1.0f
            );
            y += separatorH + 4;

            // ── Date et Heure ─────────────────────────────────
            DrawLabelValue("DATE      ", dateStr, labelFormat, priceFormat, labelBrush, priceBrush, x, y, w, lineHeight);
            y += lineHeight;

            DrawLabelValue("BAR TIME  ", timeStr, labelFormat, priceFormat, labelBrush, priceBrush, x, y, w, lineHeight);
            y += lineHeight;

            // Ligne séparatrice
            RenderTarget.DrawLine(
                new SharpDX.Vector2(PanelX + 4, y),
                new SharpDX.Vector2(PanelX + panelWidth - 4, y),
                separatorBrush, 1.0f
            );
            y += separatorH + 4;

            // ── Prix OHLC ─────────────────────────────────────
            DrawLabelValue("OPEN      ", openPrice.ToString("F2"), labelFormat, priceFormat, labelBrush, priceBrush, x, y, w, lineHeight);
            y += lineHeight;

            DrawLabelValue("HIGH      ", highPrice.ToString("F2"), labelFormat, priceFormat, labelBrush, upBrush, x, y, w, lineHeight);
            y += lineHeight;

            DrawLabelValue("LOW       ", lowPrice.ToString("F2"), labelFormat, priceFormat, labelBrush, downBrush, x, y, w, lineHeight);
            y += lineHeight;

            // LAST avec couleur selon direction
            var lastBrush = change >= 0 ? upBrush : downBrush;
            string changeStr = $"{lastPrice:F2}  ({(change >= 0 ? "+" : "")}{change:F2} / {(changePct >= 0 ? "+" : "")}{changePct:F2}%)";
            DrawLabelValue("LAST      ", changeStr, labelFormat, priceFormat, labelBrush, lastBrush, x, y, w, lineHeight);
            y += lineHeight;

            // Ligne séparatrice
            RenderTarget.DrawLine(
                new SharpDX.Vector2(PanelX + 4, y),
                new SharpDX.Vector2(PanelX + panelWidth - 4, y),
                separatorBrush, 1.0f
            );
            y += separatorH + 4;

            // ── Métriques supplémentaires ─────────────────────
            if (ShowATR && atrValue > 0)
            {
                DrawLabelValue($"ATR({ATRPeriod})   ", atrValue.ToString("F2"), labelFormat, priceFormat, labelBrush, priceBrush, x, y, w, lineHeight);
                y += lineHeight;
            }

            if (ShowVolume)
            {
                DrawLabelValue("VOLUME    ", volume.ToString("N0"), labelFormat, priceFormat, labelBrush, priceBrush, x, y, w, lineHeight);
                y += lineHeight;
            }

            if (ShowSpread && spread > 0)
            {
                DrawLabelValue("TICK SIZE ", spread.ToString("F2"), labelFormat, priceFormat, labelBrush, priceBrush, x, y, w, lineHeight);
                y += lineHeight;
            }

            // ── Timestamp serveur (précision ms) ─────────────
            RenderTarget.DrawLine(
                new SharpDX.Vector2(PanelX + 4, y),
                new SharpDX.Vector2(PanelX + panelWidth - 4, y),
                separatorBrush, 1.0f
            );
            y += separatorH + 4;

            DrawText($"SERVER: {serverTime}", smallFormat, labelBrush, x, y, w, lineHeight);
        }

        private void DrawLabelValue(
            string label, string value,
            SharpDX.DirectWrite.TextFormat labelFmt,
            SharpDX.DirectWrite.TextFormat valueFmt,
            SharpDX.Direct2D1.Brush lBrush,
            SharpDX.Direct2D1.Brush vBrush,
            float x, float y, float w, float h)
        {
            float labelW = 110;
            DrawText(label + ":", labelFmt, lBrush, x, y, labelW, h);
            DrawText(value, valueFmt, vBrush, x + labelW, y, w - labelW, h);
        }

        private void DrawText(
            string text,
            SharpDX.DirectWrite.TextFormat format,
            SharpDX.Direct2D1.Brush brush,
            float x, float y, float w, float h)
        {
            var rect = new SharpDX.RectangleF(x, y, w, h);
            RenderTarget.DrawText(text, format, rect, brush);
        }

        private void DisposeResources()
        {
            bgBrush?.Dispose(); bgBrush = null;
            borderBrush?.Dispose(); borderBrush = null;
            titleBrush?.Dispose(); titleBrush = null;
            priceBrush?.Dispose(); priceBrush = null;
            labelBrush?.Dispose(); labelBrush = null;
            upBrush?.Dispose(); upBrush = null;
            downBrush?.Dispose(); downBrush = null;
            separatorBrush?.Dispose(); separatorBrush = null;
            titleFormat?.Dispose(); titleFormat = null;
            priceFormat?.Dispose(); priceFormat = null;
            labelFormat?.Dispose(); labelFormat = null;
            smallFormat?.Dispose(); smallFormat = null;
            dwFactory?.Dispose(); dwFactory = null;
        }

        // ── Propriétés configurables ──────────────────────────

        [NinjaScriptProperty]
        [Display(Name = "Position X (gauche)", Order = 1, GroupName = "Panneau")]
        public int PanelX
        {
            get { return panelX; }
            set { panelX = Math.Max(0, value); }
        }

        [NinjaScriptProperty]
        [Display(Name = "Position Y (haut)", Order = 2, GroupName = "Panneau")]
        public int PanelY
        {
            get { return panelY; }
            set { panelY = Math.Max(0, value); }
        }

        [NinjaScriptProperty]
        [Display(Name = "Taille de police", Order = 3, GroupName = "Panneau")]
        public int FontSize
        {
            get { return fontSize; }
            set { fontSize = Math.Max(8, Math.Min(24, value)); }
        }

        [NinjaScriptProperty]
        [Display(Name = "Opacité fond (0-255)", Order = 4, GroupName = "Panneau")]
        public int BackgroundOpacity { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Afficher ATR", Order = 5, GroupName = "Métriques")]
        public bool ShowATR
        {
            get { return showATR; }
            set { showATR = value; }
        }

        [NinjaScriptProperty]
        [Display(Name = "Période ATR", Order = 6, GroupName = "Métriques")]
        public int ATRPeriod
        {
            get { return atrPeriod; }
            set { atrPeriod = Math.Max(1, value); }
        }

        [NinjaScriptProperty]
        [Display(Name = "Afficher Volume", Order = 7, GroupName = "Métriques")]
        public bool ShowVolume
        {
            get { return showVolume; }
            set { showVolume = value; }
        }

        [NinjaScriptProperty]
        [Display(Name = "Afficher Tick Size", Order = 8, GroupName = "Métriques")]
        public bool ShowSpread
        {
            get { return showSpread; }
            set { showSpread = value; }
        }
    }
}

#region NinjaScript generated code. Neither change nor remove.

namespace NinjaTrader.NinjaScript.Indicators
{
    public partial class Indicator : NinjaTrader.Gui.NinjaScript.IndicatorRenderBase
    {
        private CalibrationPanel[] cacheCalibrationPanel;
        public CalibrationPanel CalibrationPanel(int panelX, int panelY, int fontSize, int backgroundOpacity, bool showATR, int aTRPeriod, bool showVolume, bool showSpread)
        {
            return CalibrationPanel(Input, panelX, panelY, fontSize, backgroundOpacity, showATR, aTRPeriod, showVolume, showSpread);
        }

        public CalibrationPanel CalibrationPanel(ISeries<double> input, int panelX, int panelY, int fontSize, int backgroundOpacity, bool showATR, int aTRPeriod, bool showVolume, bool showSpread)
        {
            if (cacheCalibrationPanel != null)
                for (int idx = 0; idx < cacheCalibrationPanel.Length; idx++)
                    if (cacheCalibrationPanel[idx] != null && cacheCalibrationPanel[idx].PanelX == panelX && cacheCalibrationPanel[idx].PanelY == panelY && cacheCalibrationPanel[idx].FontSize == fontSize && cacheCalibrationPanel[idx].BackgroundOpacity == backgroundOpacity && cacheCalibrationPanel[idx].ShowATR == showATR && cacheCalibrationPanel[idx].ATRPeriod == aTRPeriod && cacheCalibrationPanel[idx].ShowVolume == showVolume && cacheCalibrationPanel[idx].ShowSpread == showSpread && cacheCalibrationPanel[idx].EqualsInput(input))
                        return cacheCalibrationPanel[idx];
            return CacheIndicator<CalibrationPanel>(new CalibrationPanel(){ PanelX = panelX, PanelY = panelY, FontSize = fontSize, BackgroundOpacity = backgroundOpacity, ShowATR = showATR, ATRPeriod = aTRPeriod, ShowVolume = showVolume, ShowSpread = showSpread }, input, ref cacheCalibrationPanel);
        }
    }
}

namespace NinjaTrader.NinjaScript.MarketAnalyzerColumns
{
    public partial class MarketAnalyzerColumn : MarketAnalyzerColumnBase
    {
        public Indicators.CalibrationPanel CalibrationPanel(int panelX, int panelY, int fontSize, int backgroundOpacity, bool showATR, int aTRPeriod, bool showVolume, bool showSpread)
        {
            return indicator.CalibrationPanel(Input, panelX, panelY, fontSize, backgroundOpacity, showATR, aTRPeriod, showVolume, showSpread);
        }
    }
}

namespace NinjaTrader.NinjaScript.Strategies
{
    public partial class Strategy : NinjaTrader.Gui.NinjaScript.StrategyRenderBase
    {
        public Indicators.CalibrationPanel CalibrationPanel(int panelX, int panelY, int fontSize, int backgroundOpacity, bool showATR, int aTRPeriod, bool showVolume, bool showSpread)
        {
            return indicator.CalibrationPanel(Input, panelX, panelY, fontSize, backgroundOpacity, showATR, aTRPeriod, showVolume, showSpread);
        }
    }
}

#endregion
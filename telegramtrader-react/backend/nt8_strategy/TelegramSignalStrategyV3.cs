// ================================================================
//  TelegramSignalStrategyV3.cs  –  NinjaTrader 8 (STRATÉGIE + PANNEAU FUSIONNÉS)
// ================================================================
//  Cette version fusionne en UN SEUL fichier :
//    1) La logique de trading automatique (ex-TelegramSignalStrategyV2.cs)
//    2) Le panneau visuel de calibration OHLC/session (ex-CalibrationPanel.cs,
//       ex-indicateur séparé à installer dans Custom\Indicators\)
//
//  Avantage : l'utilisateur ne télécharge/installe qu'UN SEUL fichier,
//  placé uniquement dans Documents\NinjaTrader 8\bin\Custom\Strategies\.
//
//  Règles de trading (inchangées par rapport à la V2) :
//   1. Signal valide = entry + SL + TP1 tous présents
//   2. Pas de nouveau trade si position déjà ouverte
//   3. Sizing = 1% du compte (paramétrable), plafond configurable de contrats
//   4. Limite journalière -$400 / +$900 (paramétrable)
//   5. Ordres Limite ou Marché configurables
//   6. Validation du timestamp du signal (rejet si > 5 min)
//
//  Panneau de calibration (inchangé par rapport à CalibrationPanel.cs) :
//   - Affiche OHLC de la barre courante + données cumulées depuis
//     l'ouverture de session (High/Low/Range/Variation), ATR, volume,
//     date/heure, tick size — utile pour calibrer les données de référence
//     de l'app TelegramTrader.
//   - Peut être désactivé via le paramètre "Afficher panneau calibration".
//
//  INSTALLATION :
//   1. Copier ce fichier dans Documents\NinjaTrader 8\bin\Custom\Strategies\
//   2. NinjaTrader → Tools → Edit NinjaScript → Compile (F5)
//   3. Appliquer "TelegramSignalStrategyV3" comme STRATÉGIE sur le graphique
//      (Stratégies → Ajouter une stratégie). Le panneau s'affiche automatiquement.
// ================================================================
#region Using declarations
using System;
using System.IO;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Windows.Media;
using NinjaTrader.Cbi;
using NinjaTrader.Gui;
using NinjaTrader.Gui.Chart;
using NinjaTrader.Gui.Tools;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.Strategies;
using NinjaTrader.NinjaScript.DrawingTools;
#endregion

// ────────────────────────────────────────────────────────────────
// CHANGELOG (suite à audit externe) :
//  - Ajout d'une tolérance de glissement paramétrable (SlippageTolerancePoints)
//  - Validation structurelle du JSON avant extraction (accolades + champs requis)
//  - Signal en erreur mis en quarantaine (renommé) au lieu d'être supprimé silencieusement
//  - Option d'inclusion du PnL latent (position ouverte) dans les limites journalières
//  - FontSize désormais appliqué au rendu du panneau de calibration (SimpleFont)
// ────────────────────────────────────────────────────────────────

namespace NinjaTrader.NinjaScript.Strategies
{
    public class TelegramSignalStrategyV3 : Strategy
    {
        // ══════════════════════════════════════════════════════════
        // ── Paramètres UI : TRADING ─────────────────────────────
        // ══════════════════════════════════════════════════════════
        [NinjaScriptProperty]
        [Display(Name = "Type d'ordre", Order = 1, GroupName = "Exécution")]
        public OrderMode EntryMode { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Expiry ordre limite (min)", Order = 2, GroupName = "Exécution")]
        public int LimitExpiryMin { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "% risque par trade", Order = 3, GroupName = "Money Management")]
        public double RiskPct { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Contrats max (MGC)", Order = 4, GroupName = "Money Management")]
        public int MaxContracts { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Perte max/jour ($)", Order = 5, GroupName = "Money Management")]
        public double DailyLossLimit { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Gain max/jour ($)", Order = 6, GroupName = "Money Management")]
        public double DailyProfitLimit { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Vérification (sec)", Order = 7, GroupName = "Paramètres")]
        public int PollSec { get; set; }

        [NinjaScriptProperty]
        [Range(1, 500)]
        [Display(Name = "Tolérance glissement (points)", Order = 8, GroupName = "Exécution")]
        public double SlippageTolerancePoints { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Inclure PnL latent dans limites/jour", Order = 9, GroupName = "Money Management")]
        public bool IncludeUnrealizedInDailyLimits { get; set; }

        // ══════════════════════════════════════════════════════════
        // ── Paramètres UI : PANNEAU DE CALIBRATION ──────────────
        // ══════════════════════════════════════════════════════════
        [NinjaScriptProperty]
        [Display(Name = "Afficher panneau calibration", Order = 8, GroupName = "Panneau Calibration")]
        public bool ShowCalibrationPanel { get; set; }

        [NinjaScriptProperty]
        [Range(0, 3)]
        [Display(Name = "Position (0=TopLeft 1=TopRight 2=BotLeft 3=BotRight)", Order = 9, GroupName = "Panneau Calibration")]
        public int PanelPosition { get; set; }

        [NinjaScriptProperty]
        [Range(8, 24)]
        [Display(Name = "Taille de police", Order = 10, GroupName = "Panneau Calibration")]
        public int FontSize { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Afficher ATR", Order = 11, GroupName = "Métriques Calibration")]
        public bool ShowATR { get; set; }

        [NinjaScriptProperty]
        [Range(1, 100)]
        [Display(Name = "Période ATR", Order = 12, GroupName = "Métriques Calibration")]
        public int ATRPeriod { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Afficher Volume", Order = 13, GroupName = "Métriques Calibration")]
        public bool ShowVolume { get; set; }

        // ── Champs internes : TRADING ────────────────────────────
        private string   signalFile;
        private string   priceFile;
        private string   statusFile;
        private DateTime lastCheck      = DateTime.MinValue;
        private int      currentDayOfYear = -1;  // Utiliser jour de l'année au lieu de Date (fix bug boucle infinie)
        private bool     blocked        = false;
        private bool     limitPending   = false;
        private DateTime limitExpiry    = DateTime.MinValue;
        private string   pendingLabel   = "";
        private string   pendingDir     = "";
        private OrderMode pendingMode   = OrderMode.Limit;
        private int      won = 0, lost = 0, total = 0;

        public enum OrderMode { Market, Limit, LimitThenMarket }

        // MGC : $10 par point
        private const double MGC_POINT = 10.0;

        // ── Champs internes : PANNEAU DE CALIBRATION (session) ───
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
                Name            = "TelegramSignalStrategyV3";
                Description     = "MGC | Telegram signals + Panneau calibration fusionnés | MM 1% | Max 10 contrats";
                Calculate       = Calculate.OnEachTick;
                IsExitOnSessionCloseStrategy = true;

                // Défauts trading
                EntryMode        = OrderMode.Limit;
                LimitExpiryMin   = 60;
                RiskPct          = 1.0;
                MaxContracts     = 10;
                DailyLossLimit   = 400;
                DailyProfitLimit = 900;
                PollSec          = 2;
                SlippageTolerancePoints        = 50;
                IncludeUnrealizedInDailyLimits = false;

                // Défauts panneau calibration
                ShowCalibrationPanel = true;
                PanelPosition        = 0;
                FontSize             = 12;
                ATRPeriod            = 14;
                ShowATR              = true;
                ShowVolume           = true;

                string docs = Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments);
                string nt8  = System.IO.Path.Combine(docs, "NinjaTrader 8");
                signalFile  = System.IO.Path.Combine(nt8, "telegram_signal.json");
                priceFile   = System.IO.Path.Combine(nt8, "nt8_current_price.json");
                statusFile  = System.IO.Path.Combine(nt8, "nt8_last_signal_status.json");
            }
            else if (State == State.Configure)
            {
                Print("[TGv3] ══ TelegramSignalStrategyV3 démarré (Stratégie + Panneau fusionnés) ══");
                Print("[TGv3] Mode     : " + EntryMode);
                Print("[TGv3] Risk     : " + RiskPct + "% | Max " + MaxContracts + " MGC");
                Print("[TGv3] Limite   : -$" + DailyLossLimit + " / +$" + DailyProfitLimit + " / jour");
                Print("[TGv3] Panneau calibration : " + (ShowCalibrationPanel ? "activé" : "désactivé"));
            }
            else if (State == State.Terminated)
            {
                double wr = total > 0 ? (double)won / total * 100 : 0;
                Print("[TGv3] ══ FIN SESSION ══");
                Print("[TGv3] W=" + won + " L=" + lost + " Total=" + total + " WR=" + wr.ToString("F1") + "%");
                ExportPriceFile(0, false);
            }
        }

        protected override void OnBarUpdate()
        {
            if (CurrentBar < 1) return;

            // FIX: Reset journalier basé sur DayOfYear au lieu de Date
            int todayDayOfYear = Time[0].DayOfYear;
            if (currentDayOfYear == -1)
            {
                currentDayOfYear = todayDayOfYear;
                Print("[TGv3] Initialisation jour : " + Time[0].ToShortDateString());
            }
            else if (todayDayOfYear != currentDayOfYear)
            {
                currentDayOfYear = todayDayOfYear;
                blocked    = false;
                won = lost = total = 0;
                Print("[TGv3] ✅ Nouveau jour — Reset : " + Time[0].ToShortDateString());
            }

            CheckDailyLimits();

            // ── Mise à jour + affichage du panneau de calibration (indépendant du trading) ──
            UpdateSessionTracking();
            if (ShowCalibrationPanel && CurrentBar >= 2)
                RenderCalibrationPanel();

            if (blocked) return;

            // Expiry ordre limite
            if (limitPending && DateTime.Now > limitExpiry)
            {
                Print("[TGv3] Ordre limite expiré : " + pendingLabel);
                limitPending = false;
                if (pendingMode == OrderMode.LimitThenMarket
                    && Position.MarketPosition == MarketPosition.Flat)
                {
                    Print("[TGv3] → Basculement marché");
                    PlaceMarket(pendingDir, 1, pendingLabel + "_MKT");
                }
            }

            // Throttle
            if ((DateTime.Now - lastCheck).TotalSeconds < PollSec) return;
            lastCheck = DateTime.Now;

            // Export prix pour Python
            ExportPriceFile(GetCurrentPnL(), blocked);

            // ── Règle : pas de trade si position déjà ouverte ───
            if (Position.MarketPosition != MarketPosition.Flat)
            {
                return;  // Pas de log pour éviter spam
            }
            if (limitPending) return;

            ReadAndExecuteSignal();
        }

        // ══════════════════════════════════════════════════════════
        // ── LOGIQUE TRADING (inchangée par rapport à la V2) ─────
        // ══════════════════════════════════════════════════════════

        private void CheckDailyLimits()
        {
            double pnl = GetCurrentPnL();
            if (!blocked)
            {
                if (pnl <= -DailyLossLimit)
                {
                    blocked = true;
                    Print("[TGv3] 🛑 STOP — Perte journalière $" + pnl.ToString("F0") + " ≥ -$" + DailyLossLimit);
                }
                else if (pnl >= DailyProfitLimit)
                {
                    blocked = true;
                    Print("[TGv3] 🎯 STOP — Gain journalier $" + pnl.ToString("F0") + " ≥ +$" + DailyProfitLimit);
                }
            }
        }

        private double GetCurrentPnL()
        {
            double pnl = 0;
            try
            {
                foreach (Trade t in SystemPerformance.AllTrades)
                    pnl += t.ProfitCurrency;
            }
            catch { }

            // ── Correctif audit externe : intégration optionnelle du PnL latent
            // (position ouverte non clôturée) dans le calcul utilisé pour les
            // limites journalières, car SystemPerformance.AllTrades ne contient
            // que les trades déjà clôturés (PnL réalisé).
            if (IncludeUnrealizedInDailyLimits)
            {
                try
                {
                    if (Position != null && Position.MarketPosition != MarketPosition.Flat)
                        pnl += Position.GetUnrealizedProfitLoss(PerformanceUnit.Currency, Close[0]);
                }
                catch { }
            }

            return pnl;
        }


        private void ExportPriceFile(double pnl, bool isBlocked)
        {
            try
            {
                double balance = (Account != null) ? Account.Get(AccountItem.CashValue, Currency.UsDollar) : 0;
                string json = "{"
                    + "\"timestamp\":\"" + DateTime.UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ") + "\","
                    + "\"mid\":"              + Close[0].ToString("F2", System.Globalization.CultureInfo.InvariantCulture) + ","
                    + "\"daily_pnl\":"        + pnl.ToString("F2",     System.Globalization.CultureInfo.InvariantCulture) + ","
                    + "\"account_balance\":"  + balance.ToString("F2", System.Globalization.CultureInfo.InvariantCulture) + ","
                    + "\"trading_blocked\":"  + (isBlocked ? "true" : "false") + ","
                    + "\"position_open\":"    + (Position.MarketPosition != MarketPosition.Flat ? "true" : "false") + ","
                    + "\"account_name\":\""   + (Account != null ? Account.Name : "") + "\","
                    + "\"instrument\":\""     + Instrument.FullName + "\","
                    + "\"tick_size\":"        + TickSize.ToString("F6", System.Globalization.CultureInfo.InvariantCulture) + ","
                    + "\"point_value\":"      + Instrument.MasterInstrument.PointValue.ToString("F2", System.Globalization.CultureInfo.InvariantCulture)
                    + "}";
                File.WriteAllText(priceFile, json, System.Text.Encoding.UTF8);
            }
            catch { }
        }

        private void ReadAndExecuteSignal()
        {
            if (!File.Exists(signalFile)) return;

            string content = "";
            string processingFile = signalFile + ".processing";
            try
            {
                // On déplace (rename) le fichier immédiatement pour éviter un
                // retraitement au cycle suivant, MAIS SANS LE SUPPRIMER tant que
                // le signal n'a pas été validé et exécuté avec succès
                // (correctif suite à audit externe — priorité haute).
                File.Move(signalFile, processingFile);
                content = File.ReadAllText(processingFile, System.Text.Encoding.UTF8);
            }
            catch (IOException ex) { Print("[TGv3] Erreur lecture : " + ex.Message); return; }

            // ── VALIDATION STRUCTURELLE JSON (avant toute extraction) ────
            if (!IsValidJsonStructure(content))
            {
                Print("[TGv3] ❌ Rejeté : structure JSON invalide");
                QuarantineSignal(processingFile, "json_structure_invalide");
                return;
            }

            // ── Parse champs ─────────────────────────────────────
            string direction = ExtractStr(content, "direction");
            double entry     = ExtractDbl(content, "entry");
            double sl        = ExtractDbl(content, "sl");
            double tp        = ExtractDbl(content, "tp");
            double tp2       = ExtractDbl(content, "tp2");
            int    contracts = (int)ExtractDbl(content, "contracts");
            double confidence = ExtractDbl(content, "confidence");
            string channels  = ExtractStr(content, "channels") ?? "";
            string timestamp = ExtractStr(content, "timestamp");

            // ── Champs optionnels de surcharge PAR SIGNAL (ajoutés pour
            // permettre à l'utilisateur de choisir type d'ordre / risque
            // depuis la page Trading de l'app, sans reconfigurer la stratégie) ──
            string orderTypeStr    = ExtractStr(content, "order_type");
            double riskPctOverride = ExtractDbl(content, "risk_pct");

            OrderMode effectiveMode = EntryMode;
            if (!string.IsNullOrEmpty(orderTypeStr))
            {
                string ot = orderTypeStr.Trim().ToUpperInvariant();
                if (ot == "MARKET") effectiveMode = OrderMode.Market;
                else if (ot == "LIMIT") effectiveMode = OrderMode.Limit;
                else if (ot == "LIMIT_THEN_MARKET" || ot == "LIMITTHENMARKET") effectiveMode = OrderMode.LimitThenMarket;
            }
            double effectiveRiskPct = riskPctOverride > 0 ? riskPctOverride : RiskPct;

            // ── Correctif : en mode Marché, l'entrée n'est pas obligatoire
            // (l'UI de la page Trading permet désormais de l'omettre pour un
            // ordre "Marché"). On utilise alors le prix courant de la barre
            // comme prix d'entrée effectif pour la suite des calculs
            // (money management, cohérence SL/TP, etc.). Auparavant, un
            // signal Marché sans "entry" était rejeté silencieusement ici,
            // ce qui expliquait les exécutions "fantômes" (succès annoncé
            // côté app web, mais aucun ordre réellement passé dans NinjaTrader).
            if (effectiveMode == OrderMode.Market && entry <= 0)
            {
                entry = Close[0];
                Print("[TGv3] ℹ️  Ordre Marché sans prix d'entrée fourni → utilisation du prix courant : " + entry.ToString("F2"));
            }

            // ── VALIDATION TIMESTAMP : rejeter signaux périmés ────
            if (!string.IsNullOrEmpty(timestamp))
            {
                try
                {
                    DateTime signalTime = DateTime.Parse(timestamp).ToUniversalTime();
                    double ageMinutes = (DateTime.UtcNow - signalTime).TotalMinutes;
                    if (ageMinutes > 5)
                    {
                        Print("[TGv3] ❌ Signal périmé (" + ageMinutes.ToString("F0") + " min) → ignoré");
                        QuarantineSignal(processingFile, "signal_perime");
                        return;
                    }
                    Print("[TGv3] ✅ Signal frais (" + ageMinutes.ToString("F1") + " min)");
                }
                catch
                {
                    Print("[TGv3] ⚠️  Timestamp invalide, signal accepté quand même");
                }
            }

            // ── VALIDATION STRICTE : entry + SL + TP obligatoires
            if (string.IsNullOrEmpty(direction))
            { Print("[TGv3] ❌ Rejeté : direction manquante"); QuarantineSignal(processingFile, "direction_manquante"); return; }
            if (entry <= 0)
            { Print("[TGv3] ❌ Rejeté : prix d'entrée manquant (signal incomplet)"); QuarantineSignal(processingFile, "entry_manquant"); return; }
            if (sl <= 0)
            { Print("[TGv3] ❌ Rejeté : SL manquant"); QuarantineSignal(processingFile, "sl_manquant"); return; }
            if (tp <= 0)
            { Print("[TGv3] ❌ Rejeté : TP manquant"); QuarantineSignal(processingFile, "tp_manquant"); return; }

            // Cohérence logique
            if (direction=="BUY"  && sl >= entry) { Print("[TGv3] ❌ SL BUY invalide");  QuarantineSignal(processingFile, "sl_buy_invalide"); return; }
            if (direction=="SELL" && sl <= entry) { Print("[TGv3] ❌ SL SELL invalide"); QuarantineSignal(processingFile, "sl_sell_invalide"); return; }
            if (direction=="BUY"  && tp <= entry) { Print("[TGv3] ❌ TP BUY invalide");  QuarantineSignal(processingFile, "tp_buy_invalide"); return; }
            if (direction=="SELL" && tp >= entry) { Print("[TGv3] ❌ TP SELL invalide"); QuarantineSignal(processingFile, "tp_sell_invalide"); return; }


            // ── MONEY MANAGEMENT : sizing basé sur le compte ─────
            double balance = (Account != null) ? Account.Get(AccountItem.CashValue, Currency.UsDollar) : 0;
            double slPoints = Math.Abs(entry - sl);

            int finalQty;
            if (contracts > 0)
            {
                finalQty = Math.Min(contracts, MaxContracts);
            }
            else if (balance > 0 && slPoints > 0)
            {
                double maxRisk = balance * effectiveRiskPct / 100.0;
                finalQty = (int)Math.Floor(maxRisk / (slPoints * MGC_POINT));
                finalQty = Math.Max(1, Math.Min(finalQty, MaxContracts));
            }
            else
            {
                finalQty = 1;
            }

            double price = Close[0];
            string label = "TGv3_" + direction + "_" + DateTime.Now.ToString("HHmmss");

            Print("[TGv3] ══════════════════════════════════════");
            Print("[TGv3] " + direction + " " + finalQty + " MGC");
            Print("[TGv3] Entry=" + entry.ToString("F2") + " SL=" + sl.ToString("F2") + " TP=" + tp.ToString("F2") + (tp2>0?" TP2="+tp2.ToString("F2"):""));
            Print("[TGv3] Conf=" + confidence.ToString("F1") + "% | Compte=$" + balance.ToString("F0") + " | Risque=$" + (slPoints*MGC_POINT*finalQty).ToString("F0"));
            Print("[TGv3] Canaux: " + channels);
            Print("[TGv3] P&L jour: $" + GetCurrentPnL().ToString("F0") + " | Limite: -$" + DailyLossLimit + "/+$" + DailyProfitLimit);

            try
            {
                if (effectiveMode == OrderMode.Market)
                {
                    PlaceMarket(direction, finalQty, label);
                    SetSLTP(label, sl, tp);
                }
                else
                {
                    double slippage = Math.Abs(price - entry);
                    if (slippage > SlippageTolerancePoints)
                    {
                        Print("[TGv3] Entry " + entry.ToString("F2") + " trop loin du prix " + price.ToString("F2") + " (tolérance " + SlippageTolerancePoints.ToString("F0") + " pts)");
                        if (effectiveMode == OrderMode.LimitThenMarket)
                        { PlaceMarket(direction, finalQty, label); SetSLTP(label, sl, tp); }
                        else
                        {
                            // Signal valide mais non exécuté (hors tolérance) → quarantaine, pas de suppression silencieuse
                            QuarantineSignal(processingFile, "slippage_excessif");
                            return;
                        }
                    }
                    else
                    {
                        PlaceLimit(direction, finalQty, entry, label);
                        SetSLTP(label, sl, tp);
                        limitPending  = true;
                        limitExpiry   = DateTime.Now.AddMinutes(LimitExpiryMin);
                        pendingLabel  = label;
                        pendingDir    = direction;
                        pendingMode   = effectiveMode;
                        Print("[TGv3] Ordre LIMITE @ " + entry.ToString("F2") + " | Expiry " + LimitExpiryMin + "min");
                    }
                }
                total++;
                Print("[TGv3] ✅ Ordre #" + total + " : " + label);
                WriteStatusFile("executed", "ok", direction + " " + finalQty + " @ " + entry.ToString("F2") + " (" + effectiveMode + ")");

                // ── Correctif audit (priorité haute) : on ne supprime le
                // fichier de signal QU'APRÈS exécution réussie de l'ordre.
                TryDeleteProcessingFile(processingFile);
            }
            catch (Exception ex)
            {
                Print("[TGv3] ❌ Erreur : " + ex.Message);
                // En cas d'exception pendant l'exécution, on NE PERD PAS le signal :
                // il est mis en quarantaine pour analyse plutôt que supprimé.
                QuarantineSignal(processingFile, "exception_execution");
            }
        }

        /// <summary>
        /// Valide grossièrement la structure JSON avant toute extraction :
        /// non vide, encadré par des accolades, et contient les champs obligatoires.
        /// (Correctif audit externe : validation structurelle avant extraction.)
        /// </summary>
        private bool IsValidJsonStructure(string content)
        {
            if (string.IsNullOrWhiteSpace(content)) return false;
            string trimmed = content.Trim();
            if (!trimmed.StartsWith("{") || !trimmed.EndsWith("}")) return false;

            string[] requiredFields = { "direction", "entry", "sl", "tp" };
            foreach (string field in requiredFields)
            {
                if (trimmed.IndexOf("\"" + field + "\"", StringComparison.OrdinalIgnoreCase) < 0)
                    return false;
            }
            return true;
        }

        /// <summary>
        /// Met en quarantaine un signal rejeté/en erreur en le renommant
        /// (au lieu de le supprimer silencieusement), afin de permettre une
        /// analyse a posteriori. (Correctif audit externe.)
        /// </summary>
        private void QuarantineSignal(string processingFile, string reason)
        {
            WriteStatusFile("rejected", reason);
            try
            {
                if (!File.Exists(processingFile)) return;
                string quarantineFile = processingFile.Replace(".processing",
                    "_error_" + DateTime.Now.ToString("yyyyMMdd_HHmmss") + "_" + reason + ".json");
                File.Move(processingFile, quarantineFile);
                Print("[TGv3] ⚠️  Signal mis en quarantaine : " + System.IO.Path.GetFileName(quarantineFile));
            }
            catch (Exception ex)
            {
                Print("[TGv3] ❌ Erreur quarantaine (fichier conservé) : " + ex.Message);
            }
        }

        /// <summary>
        /// Écrit un fichier de statut (nt8_last_signal_status.json) résumant
        /// le résultat du dernier signal traité (accepté ou rejeté, avec la
        /// raison). Ce fichier est lu par l'agent .exe (mode debug) afin de
        /// permettre à l'utilisateur de diagnostiquer, DEPUIS L'APPLICATION
        /// WEB / le menu de l'agent, pourquoi un signal n'a pas été exécuté
        /// dans NinjaTrader — sans avoir à ouvrir la fenêtre "NinjaScript
        /// Output" de NinjaTrader. (Ajout suite au rapport utilisateur :
        /// "j'ai exécuté... mais sur ninja trader rien".)
        /// </summary>
        private void WriteStatusFile(string status, string reason, string extra = "")
        {
            try
            {
                if (string.IsNullOrEmpty(statusFile)) return;
                string json = "{"
                    + "\"timestamp\":\"" + DateTime.UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ") + "\","
                    + "\"status\":\"" + status + "\","
                    + "\"reason\":\"" + reason + "\","
                    + "\"extra\":\"" + extra.Replace("\"", "'") + "\""
                    + "}";
                File.WriteAllText(statusFile, json, System.Text.Encoding.UTF8);
            }
            catch { }
        }

        /// <summary>
        /// Supprime le fichier de traitement temporaire une fois le signal
        /// traité avec succès (ordre placé). Best-effort : si la suppression
        /// échoue, le fichier reste présent mais ne sera plus retraité
        /// (extension .processing non reconnue par ReadAndExecuteSignal).
        /// </summary>
        private void TryDeleteProcessingFile(string processingFile)
        {
            try
            {
                if (File.Exists(processingFile)) File.Delete(processingFile);
            }
            catch (Exception ex)
            {
                Print("[TGv3] ⚠️  Impossible de supprimer le fichier traité : " + ex.Message);
            }
        }


        private void PlaceMarket(string dir, int qty, string lbl)
        {
            if (dir=="BUY") EnterLong(qty, lbl);
            else            EnterShort(qty, lbl);
        }

        private void PlaceLimit(string dir, int qty, double price, string lbl)
        {
            if (dir=="BUY") EnterLongLimit(qty, price, lbl);
            else            EnterShortLimit(qty, price, lbl);
        }

        private void SetSLTP(string lbl, double sl, double tp)
        {
            SetStopLoss(lbl,     CalculationMode.Price, sl, false);
            SetProfitTarget(lbl, CalculationMode.Price, tp);
        }

        protected override void OnExecutionUpdate(
            Execution execution, string executionId, double price,
            int quantity, MarketPosition marketPosition, string orderId, DateTime time)
        {
            if (execution.Order == null) return;
            if (!execution.Order.Name.StartsWith("TGv3_")) return;

            if (limitPending &&
               (execution.Order.OrderAction == OrderAction.Buy ||
                execution.Order.OrderAction == OrderAction.SellShort))
                limitPending = false;

            bool isClose = execution.Order.OrderAction == OrderAction.Sell
                        || execution.Order.OrderAction == OrderAction.BuyToCover;
            if (!isClose) return;

            bool isTP = execution.Order.OrderType == OrderType.Limit;
            bool isSL = execution.Order.OrderType == OrderType.StopMarket;

            if (isTP) { won++;  Print("[TGv3] 🏆 TP | W=" + won + " L=" + lost + " | P&L=$" + GetCurrentPnL().ToString("F0")); }
            if (isSL) { lost++; Print("[TGv3] ❌ SL | W=" + won + " L=" + lost + " | P&L=$" + GetCurrentPnL().ToString("F0")); }
        }

        private string ExtractStr(string json, string key)
        {
            int i = json.IndexOf("\""+key+"\""); if (i<0) return null;
            int c = json.IndexOf(':', i);        if (c<0) return null;
            int q1 = json.IndexOf('"', c+1);     if (q1<0) return null;
            int q2 = json.IndexOf('"', q1+1);    if (q2<0) return null;
            return json.Substring(q1+1, q2-q1-1);
        }

        private double ExtractDbl(string json, string key)
        {
            int i = json.IndexOf("\""+key+"\""); if (i<0) return 0;
            int c = json.IndexOf(':', i);        if (c<0) return 0;
            int s = c+1;
            while (s < json.Length && (json[s]==' '||json[s]=='\n'||json[s]=='\r')) s++;
            if (s >= json.Length) return 0;
            char ch = json[s];
            if (ch=='"'||ch=='{'||ch=='['||ch=='n'||ch=='t'||ch=='f') return 0;
            int e = s;
            while (e < json.Length && (char.IsDigit(json[e])||json[e]=='.'||json[e]=='-')) e++;
            double r;
            return double.TryParse(json.Substring(s,e-s),
                System.Globalization.NumberStyles.Any,
                System.Globalization.CultureInfo.InvariantCulture, out r) ? r : 0;
        }

        // ══════════════════════════════════════════════════════════
        // ── PANNEAU DE CALIBRATION (inchangé par rapport à CalibrationPanel.cs) ─
        // ══════════════════════════════════════════════════════════

        private void UpdateSessionTracking()
        {
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
        }

        private void RenderCalibrationPanel()
        {
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
                    "  === CALIBRATION PANEL (V3 fusionné) ===\n" +
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
                    string.Format("  HIGH MAX   : {0:F2}  << SAISIR DANS L'APP\n", _sessHigh) +
                    string.Format("  LOW MIN    : {0:F2}  << SAISIR DANS L'APP\n", _sessLow) +
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
                // Correctif audit externe : FontSize désormais réellement appliqué
                // via un objet SimpleFont, au lieu d'être ignoré (null).
                SimpleFont panelFont = new SimpleFont("Arial", FontSize);

                Draw.TextFixed(
                    this,
                    "CalibrationPanel_Text",
                    text,
                    GetTextPosition(),
                    Brushes.Cyan,
                    panelFont,
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
                    new SimpleFont("Arial", FontSize),
                    Brushes.Transparent,
                    Brushes.Black,
                    200
                );
            }
        }

    }
}

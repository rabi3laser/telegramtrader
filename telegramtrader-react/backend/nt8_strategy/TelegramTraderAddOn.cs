// ================================================================
//  TelegramTraderAddOn.cs  –  NinjaTrader 8 ADD-ON (MULTI-COMPTES)
// ================================================================
//  OBJECTIF
//  --------
//  Contrairement à TelegramSignalStrategyV3.cs (une Strategy liée à
//  UN SEUL compte, celui assigné au graphique), cet Add-On permet de :
//
//    1. Voir tous les comptes disponibles dans NinjaTrader (Account.All)
//    2. Se connecter / déconnecter d'une connexion (Rithmic, Tradovate,
//       Simulated, ...) directement depuis un panneau dédié
//    3. CHOISIR le compte actif sur lequel les signaux Telegram seront
//       exécutés — utile pour les traders de prop firms (Rithmic/
//       Tradovate) qui ne peuvent connecter qu'UN SEUL compte à la fois,
//       mais qui veulent pouvoir en changer facilement (FTMO le matin,
//       TopStep l'après-midi, etc.) sans reconfigurer quoi que ce soit
//    4. Exécuter automatiquement les signaux (identique à la V3 : entry/
//       SL/TP, sizing par risque %, limites journalières, tolérance de
//       glissement, fichier de statut de diagnostic)
//
//  Tout tient dans CE SEUL FICHIER (pas besoin d'installer plusieurs
//  scripts), conformément à la demande : "il faudra compacter le tout
//  dans l'addon pour ne pas demander à l'utilisateur de télécharger
//  plusieurs fichiers".
//
//  INSTALLATION
//  ------------
//   1. Copier ce fichier dans :
//      Documents\NinjaTrader 8\bin\Custom\AddOns\
//      (⚠️ dossier "AddOns", PAS "Strategies")
//   2. NinjaTrader → Tools → Edit NinjaScript → Compile (F5)
//   3. Un nouveau menu "TelegramTrader Manager" apparaît dans le menu
//      "New" (Nouveau) de la fenêtre principale (Control Center).
//      Cliquer dessus ouvre le panneau de gestion.
//
//  COMPATIBILITÉ
//  -------------
//  Utilise EXACTEMENT les mêmes fichiers d'échange que la Strategy V3 et
//  l'agent .exe existant (telegram_signal.json, nt8_last_signal_status.json,
//  nt8_current_price.json) → AUCUN changement requis côté agent Python.
//  Vous pouvez utiliser SOIT la Strategy V3 (1 compte, plus simple), SOIT
//  cet Add-On (multi-comptes), mais évitez d'activer les deux en même
//  temps sur le même fichier de signal (l'un consommerait le signal de
//  l'autre).
//
//  ⚠️ NOTE IMPORTANTE SUR CETTE PREMIÈRE VERSION
//  ----------------------------------------------
//  Certains noms exacts de membres de l'API NinjaTrader (ex: propriétés
//  de la classe Connection, signature exacte de Account.CreateOrder)
//  n'ont pas pu être vérifiés par compilation réelle dans cet environnement
//  (les DLL propriétaires NinjaTrader ne sont pas disponibles ici). Le code
//  ci-dessous suit fidèlement les patterns officiels documentés par
//  NinjaTrader pour les Add-Ons. Si la compilation (F5) affiche une erreur,
//  copiez le message d'erreur exact — la correction sera immédiate.
// ================================================================
#region Using declarations
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Threading;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.Gui;
using NinjaTrader.Gui.Tools;
using NinjaTrader.NinjaScript;
#endregion


namespace NinjaTrader.NinjaScript.AddOns
{
    // ════════════════════════════════════════════════════════════════
    // 1) ADD-ON PRINCIPAL : intégration du menu dans NinjaTrader
    // ════════════════════════════════════════════════════════════════
    public class TelegramTraderAddOn : AddOnBase
    {
        private NTMenuItem telegramMenuItem;
        private NTMenuItem mainMenuItem;
        private static TelegramTraderWindow controlWindow;

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Name        = "TelegramTraderAddOn";
                Description = "TelegramTrader — Manager multi-comptes + exécution automatique des signaux";
            }
            else if (State == State.Terminated)
            {
                TelegramTraderEngine.Instance.Stop();
                if (controlWindow != null)
                {
                    controlWindow.Close();
                    controlWindow = null;
                }
            }
        }

        protected override void OnWindowCreated(Window window)
        {
            ControlCenter cc = window as ControlCenter;
            if (cc == null) return;

            telegramMenuItem = new NTMenuItem { Header = "TelegramTrader Manager" };
            telegramMenuItem.Click += OnMenuItemClick;

            mainMenuItem = cc.FindFirst("ControlCenterMenuItemNew") as NTMenuItem;
            if (mainMenuItem != null)
                mainMenuItem.Items.Add(telegramMenuItem);

            // ── Démarrage automatique du moteur dès l'ouverture du Control Center ──
            // Sans cela, l'utilisateur devait cliquer sur "TelegramTrader Manager"
            // pour que le moteur démarre et que nt8_current_price.json soit écrit.
            // Maintenant le moteur démarre silencieusement en arrière-plan dès que
            // NinjaTrader est ouvert — l'agent Python détecte NT8 comme "actif"
            // immédiatement, sans aucune action manuelle requise.
            TelegramTraderEngine.Instance.Start();
        }

        protected override void OnWindowDestroyed(Window window)
        {
            ControlCenter cc = window as ControlCenter;
            if (cc == null) return;

            if (mainMenuItem != null && telegramMenuItem != null)
                mainMenuItem.Items.Remove(telegramMenuItem);

            if (telegramMenuItem != null)
                telegramMenuItem.Click -= OnMenuItemClick;
        }

        private void OnMenuItemClick(object sender, RoutedEventArgs e)
        {
            if (controlWindow == null)
            {
                controlWindow = new TelegramTraderWindow();
                controlWindow.Closed += (s, args) => controlWindow = null;
            }

            TelegramTraderEngine.Instance.Start();

            controlWindow.Show();
            controlWindow.WindowState = WindowState.Normal;
            controlWindow.Activate();
        }
    }

    // ════════════════════════════════════════════════════════════════
    // 2) CONFIGURATION PERSISTANTE (JSON)
    // ════════════════════════════════════════════════════════════════
    public class TelegramConfig
    {
        public string SelectedAccountName    = "";
        public double RiskPct                = 1.0;
        public int    MaxContracts           = 10;
        public double DailyLossLimit         = 400;
        public double DailyProfitLimit       = 900;
        public double SlippageTolerancePoints = 50;
        public int    PollSec                = 2;
        public string DefaultOrderMode       = "Limit"; // Market | Limit
        public int    LimitExpiryMin         = 60;
        public string DefaultInstrument      = "MGC AUG26";

    }

    // ════════════════════════════════════════════════════════════════
    // 3) MOTEUR PRINCIPAL (singleton) : polling, exécution, comptes
    // ════════════════════════════════════════════════════════════════
    public class TelegramTraderEngine
    {
        private static readonly TelegramTraderEngine _instance = new TelegramTraderEngine();
        public static TelegramTraderEngine Instance { get { return _instance; } }

        public TelegramConfig Config { get; private set; }

        private readonly string nt8Dir;
        private readonly string signalFile;
        private readonly string processingFile;
        private readonly string statusFile;
        private readonly string priceFile;
        private readonly string configFile;
        private readonly string commandFile;
        private readonly string commandProcessingFile;
        private readonly string accountsStatusFile;

        private System.Threading.Timer pollTimer;
        private System.Threading.Timer priceTimer;
        private bool started = false;

        private DateTime currentDay = DateTime.MinValue;
        private double dailyStartBalance = 0;
        private bool blocked = false;

        private Instrument subscribedInstrument;
        private double lastTick = 0;

        // ── Panneau de calibration (portage simplifié de UpdateSessionTracking()/
        // RenderCalibrationPanel() de TelegramSignalStrategyV3.cs). Un Add-On n'étant
        // pas rattaché à un graphique, il n'y a pas de "barres" ni d'ATR/Volume
        // disponibles nativement : la session est ici suivie via les ticks Level1
        // reçus (OnMarketDataUpdate) plutôt que via des barres OHLC. Reset automatique
        // au changement de jour calendaire (approximation raisonnable de "nouvelle session").
        private DateTime _sessDate  = DateTime.MinValue;
        private double   _sessOpen  = 0;
        private double   _sessHigh  = double.MinValue;
        private double   _sessLow   = double.MaxValue;
        private string   _sessStart = "";
        private long     _tickCount = 0;
        private DateTime _lastTickTime = DateTime.MinValue;

        public double   LastPrice     { get { return lastTick; } }
        public double   SessOpen      { get { return _sessOpen; } }
        public double   SessHigh      { get { return _sessHigh == double.MinValue ? 0 : _sessHigh; } }
        public double   SessLow       { get { return _sessLow  == double.MaxValue ? 0 : _sessLow; } }
        public string   SessStart     { get { return _sessStart; } }
        public long     TickCount     { get { return _tickCount; } }
        public DateTime LastTickTime  { get { return _lastTickTime; } }
        public string   CurrentInstrumentName { get { return subscribedInstrument != null ? subscribedInstrument.FullName : Config.DefaultInstrument; } }
        public double   TickSize      { get { try { return subscribedInstrument != null ? subscribedInstrument.MasterInstrument.TickSize : 0; } catch { return 0; } } }
        public double   PointValue    { get { try { return subscribedInstrument != null ? subscribedInstrument.MasterInstrument.PointValue : 0; } catch { return 0; } } }


        // Ordre d'entrée en attente de fill (pour poser SL/TP juste après)
        private readonly object lockObj = new object();
        private string pendingEntryName = null;
        private string pendingDirection = null;
        private double pendingSl = 0;
        private double pendingTp = 0;

        public string LastStatus { get; private set; } = "—";
        public string LastReason { get; private set; } = "";
        public string LastExtra  { get; private set; } = "";
        public DateTime LastStatusTime { get; private set; }

        private TelegramTraderEngine()
        {
            string docs = Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments);
            nt8Dir         = System.IO.Path.Combine(docs, "NinjaTrader 8");
            signalFile     = System.IO.Path.Combine(nt8Dir, "telegram_signal.json");
            processingFile = signalFile + ".processing";
            statusFile     = System.IO.Path.Combine(nt8Dir, "nt8_last_signal_status.json");
            priceFile      = System.IO.Path.Combine(nt8Dir, "nt8_current_price.json");
            configFile     = System.IO.Path.Combine(nt8Dir, "telegramtrader_addon_config.json");
            commandFile           = System.IO.Path.Combine(nt8Dir, "telegramtrader_addon_command.json");
            commandProcessingFile = commandFile + ".processing";
            accountsStatusFile    = System.IO.Path.Combine(nt8Dir, "nt8_accounts_status.json");

            Config = LoadConfig();

        }

        // ─────────────────────────────────────────────────────────
        // CYCLE DE VIE
        // ─────────────────────────────────────────────────────────
        public void Start()
        {
            if (started) return;
            started = true;

            try
            {
                foreach (Account a in Account.All)
                    a.ExecutionUpdate += OnExecutionUpdate;
            }
            catch { }

            SubscribeInstrument(Config.DefaultInstrument);

            pollTimer  = new System.Threading.Timer(_ => SafePoll(), null, 1000, Math.Max(500, Config.PollSec * 1000));
            priceTimer = new System.Threading.Timer(_ => SafeWritePrice(), null, 1000, 3000);
        }

        public void Stop()
        {
            if (!started) return;
            started = false;

            try
            {
                foreach (Account a in Account.All)
                    a.ExecutionUpdate -= OnExecutionUpdate;
            }
            catch { }

            if (subscribedInstrument != null)
            {
                subscribedInstrument = null;
            }

            if (pollTimer  != null) { pollTimer.Dispose();  pollTimer  = null; }
            if (priceTimer != null) { priceTimer.Dispose(); priceTimer = null; }
        }

        public bool IsRunning { get { return started; } }

        // ─────────────────────────────────────────────────────────
        // ⚠️ CORRECTIF ROBUSTESSE : un Add-On NinjaTrader n'est PAS
        // rechargé aussi proprement qu'une Strategy/Indicator lors d'une
        // simple compilation (F5). En particulier, OnWindowCreated() ne
        // se redéclenche PAS pour la fenêtre "Control Center" déjà ouverte
        // (elle n'est recréée que lors d'un redémarrage complet de
        // NinjaTrader). Résultat possible : après un F5, l'ancienne
        // instance de l'Add-On (avec ses références de compte/instrument
        // devenues obsolètes) continue de répondre au clic du menu, et
        // son moteur "semble" actif (started = true) mais échoue
        // silencieusement (exceptions avalées par les try/catch) sans
        // jamais rafraîchir nt8_current_price.json.
        //
        // ForceRestart() permet de forcer un arrêt + redémarrage complet
        // du moteur (nouveaux timers, nouvel abonnement instrument, nouvelle
        // souscription ExecutionUpdate) SANS avoir à fermer tout NinjaTrader.
        // Utilisable depuis un bouton dédié dans le panneau.
        // ─────────────────────────────────────────────────────────
        public void ForceRestart()
        {
            try { started = false; Stop(); } catch { }
            started = false;
            // Recharge aussi la config depuis le disque : permet de forcer une
            // valeur (ex: DefaultInstrument) via édition directe du fichier JSON
            // si jamais l'enregistrement via le panneau UI ne s'applique pas.
            Config = LoadConfig();
            Start();
        }


        /// <summary>
        /// Réinitialise manuellement le blocage journalier (perte/gain max atteint).
        /// Une fois "blocked" passé à true, il ne se réinitialise normalement qu'au
        /// changement de jour calendaire (CheckDayReset) ou au changement de compte
        /// sélectionné (SaveConfig). Ce bouton permet un reset manuel immédiat, utile
        /// par exemple après avoir clôturé manuellement une position qui faussait le
        /// calcul du PnL journalier (dailyStartBalance recalculé sur le solde actuel).
        /// </summary>
        public void ResetDailyBlock()
        {
            Account account = GetSelectedAccount();
            dailyStartBalance = account != null ? account.Get(AccountItem.CashValue, Currency.UsDollar) : 0;
            currentDay = DateTime.Now.Date;
            blocked = false;
        }

        public bool IsBlocked { get { return blocked; } }



        // ─────────────────────────────────────────────────────────
        // CONFIG
        // ─────────────────────────────────────────────────────────
        public TelegramConfig LoadConfig()
        {
            try
            {
                if (File.Exists(configFile))
                {
                    string json = File.ReadAllText(configFile);
                    TelegramConfig cfg = JsonConvert.DeserializeObject<TelegramConfig>(json);
                    if (cfg != null) return cfg;
                }
            }
            catch { }
            return new TelegramConfig();
        }

        // CORRECTIF BUG ALIASING : TelegramConfig est un type référence. Tous les
        // appelants mutaient Config.SelectedAccountName AVANT d'appeler SaveConfig(),
        // donc la capture de previousAccount ci-dessous lisait déjà la nouvelle valeur
        // → la comparaison était toujours fausse → le reset journalier ne se déclenchait
        // jamais au changement de compte. Solution : les appelants passent explicitement
        // la valeur AVANT mutation via le paramètre optionnel previousAccountName.
        public void SaveConfig(TelegramConfig cfg, string previousAccountName = null)
        {
            string previousInstrument = Config != null ? Config.DefaultInstrument : null;
            // Utilise la valeur explicitement fournie par l'appelant (capturée avant
            // mutation), ou fallback sur Config courant si appelé sans paramètre
            // (ex: chargement initial au démarrage où Config est encore null).
            string prevAcc = previousAccountName ?? (Config != null ? Config.SelectedAccountName : null);
            Config = cfg;
            try
            {
                Directory.CreateDirectory(nt8Dir);
                File.WriteAllText(configFile, JsonConvert.SerializeObject(cfg, Formatting.Indented));
            }
            catch { }

            if (previousInstrument != cfg.DefaultInstrument)
                SubscribeInstrument(cfg.DefaultInstrument);

            // Si le compte sélectionné change (ou est choisi pour la première fois),
            // on force le recalcul du solde de référence du jour (dailyStartBalance).
            // Sans cela, si aucun compte n'était sélectionné au démarrage de l'Add-On,
            // dailyStartBalance restait à 0 pour toute la journée (CheckDayReset() ne
            // s'exécute qu'une fois par changement de jour calendaire), ce qui provoquait
            // un faux déclenchement du blocage "gain/perte journalier" dès qu'un compte
            // était sélectionné (pnl calculé = solde entier du compte).
            if (prevAcc != cfg.SelectedAccountName)
            {
                currentDay = DateTime.MinValue;
                blocked = false;
            }


            if (started)
            {
                // Redémarre le timer de polling avec le nouvel intervalle éventuel
                if (pollTimer != null) pollTimer.Dispose();
                pollTimer = new System.Threading.Timer(_ => SafePoll(), null, 500, Math.Max(500, Config.PollSec * 1000));
            }
        }

        // ─────────────────────────────────────────────────────────
        // COMPTES / CONNEXIONS
        // ─────────────────────────────────────────────────────────
        public List<Account> GetAvailableAccounts()
        {
            try { return Account.All.ToList(); }
            catch { return new List<Account>(); }
        }

        public Account GetSelectedAccount()
        {
            try { return Account.All.FirstOrDefault(a => a.Name == Config.SelectedAccountName); }
            catch { return null; }
        }

        public List<Connection> GetConnections()
        {
            try { return Connection.Connections.ToList(); }
            catch { return new List<Connection>(); }
        }

        // ── Connexion/déconnexion via réflexion ──────────────────
        // La signature exacte de Connection.Connect(...) varie selon les versions
        // de NinjaTrader (paramètre ConnectOptions requis, propriétés internes non
        // documentées de façon stable). Pour éviter des erreurs de compilation liées
        // à une signature exacte qui n'a pas pu être vérifiée dans cet environnement
        // (DLL NinjaTrader indisponibles ici), on invoque ces méthodes par réflexion :
        // cela permet de s'adapter automatiquement à la signature réelle trouvée à
        // l'exécution (paramètre requis ou non), sans bloquer la compilation.
        public void ConnectConnection(Connection c)
        {
            try
            {
                var method = c.GetType().GetMethods()
                    .FirstOrDefault(m => m.Name == "Connect");
                if (method == null) return;

                var parameters = method.GetParameters();
                if (parameters.Length == 0)
                {
                    method.Invoke(c, null);
                    return;
                }

                object arg = null;
                var optionsProp = c.GetType().GetProperty("Options");
                if (optionsProp != null)
                    arg = optionsProp.GetValue(c, null);
                if (arg == null)
                {
                    try { arg = Activator.CreateInstance(parameters[0].ParameterType); }
                    catch { }
                }
                method.Invoke(c, new[] { arg });
            }
            catch { }
        }

        public void DisconnectConnection(Connection c)
        {
            try
            {
                var method = c.GetType().GetMethods()
                    .FirstOrDefault(m => m.Name == "Disconnect" && m.GetParameters().Length == 0);
                if (method != null) method.Invoke(c, null);
            }
            catch { }
        }

        /// <summary>
        /// Nom d'affichage d'une connexion, obtenu par réflexion pour la même
        /// raison que ci-dessus (propriété exacte non vérifiable ici : "Name",
        /// "Options.Name", etc. selon la version de NinjaTrader).
        /// </summary>
        public string GetConnectionDisplayName(Connection c)
        {
            try
            {
                var nameProp = c.GetType().GetProperty("Name");
                if (nameProp != null)
                {
                    var val = nameProp.GetValue(c, null);
                    if (val != null && !string.IsNullOrWhiteSpace(val.ToString())) return val.ToString();
                }
                var optionsProp = c.GetType().GetProperty("Options");
                if (optionsProp != null)
                {
                    var options = optionsProp.GetValue(c, null);
                    if (options != null)
                    {
                        var optName = options.GetType().GetProperty("Name");
                        if (optName != null)
                        {
                            var val = optName.GetValue(options, null);
                            if (val != null && !string.IsNullOrWhiteSpace(val.ToString())) return val.ToString();
                        }
                    }
                }
            }
            catch { }
            return c.ToString();
        }


        // ─────────────────────────────────────────────────────────
        // PRIX (abonnement Level1 pour l'instrument par défaut)
        // ─────────────────────────────────────────────────────────
        private void SubscribeInstrument(string name)
        {
            try
            {
                subscribedInstrument = null;
                if (string.IsNullOrWhiteSpace(name)) return;

                subscribedInstrument = ResolveInstrument(name);
            }
            catch { }
        }

        // ⚠️ Le nom exact attendu par Instrument.GetInstrument(...) dépend du format
        // interne NinjaTrader, qui peut différer de ce qui est affiché à l'écran
        // (ex: table des ordres affiche parfois "MGC AUG26" alors que le nom interne
        // réel est "MGC 08-26", ou l'inverse selon la version/langue). Pour éviter de
        // bloquer l'utilisateur sur un format exact à deviner, on essaie plusieurs
        // variantes courantes automatiquement avant d'abandonner.
        private static readonly string[] MonthCodes = { "F","G","H","J","K","M","N","Q","U","V","X","Z" };
        private static readonly string[] MonthAbbr  = { "JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC" };

        private Instrument ResolveInstrument(string rawName)
        {
            string name = rawName.Trim();

            // 1) Tentative directe (nom tel quel)
            Instrument inst = TryGetInstrument(name);
            if (inst != null) return inst;

            // 2) Si le format est "XXX MMMYY" (ex: "MGC AUG26"), essayer "XXX MM-YY"
            var parts = name.Split(' ');
            if (parts.Length == 2 && parts[1].Length == 5)
            {
                string root = parts[0];
                string abbr = parts[1].Substring(0, 3).ToUpperInvariant();
                string yy   = parts[1].Substring(3, 2);
                int monthIdx = Array.IndexOf(MonthAbbr, abbr);
                if (monthIdx >= 0)
                {
                    string alt = root + " " + (monthIdx + 1).ToString("00") + "-" + yy;
                    inst = TryGetInstrument(alt);
                    if (inst != null) return inst;
                }
            }

            // 3) Si le format est "XXX MM-YY" (ex: "MGC 08-26"), essayer "XXX MMMYY"
            if (parts.Length == 2 && parts[1].Length == 5 && parts[1][2] == '-')
            {
                string root = parts[0];
                int month;
                if (int.TryParse(parts[1].Substring(0, 2), out month) && month >= 1 && month <= 12)
                {
                    string yy = parts[1].Substring(3, 2);
                    string alt = root + " " + MonthAbbr[month - 1] + yy;
                    inst = TryGetInstrument(alt);
                    if (inst != null) return inst;
                }
            }

            return null;
        }

        private Instrument TryGetInstrument(string name)
        {
            try { return Instrument.GetInstrument(name); }
            catch { return null; }
        }


        /// <summary>
        /// Portage simplifié de UpdateSessionTracking() (TelegramSignalStrategyV3.cs), mais
        /// basé sur un POLLING PÉRIODIQUE de Instrument.MarketData.Last.Price plutôt que sur
        /// un abonnement à un événement (le type d'événement exact de MarketData n'a pas pu
        /// être vérifié par compilation réelle dans cet environnement — le polling évite
        /// totalement ce problème car il ne dépend d'aucune signature de delegate/EventArgs).
        /// Appelée périodiquement par SafeWritePrice() (déclenché par priceTimer).
        /// </summary>
        private void PollPrice()
        {
            try
            {
                if (subscribedInstrument == null) return;
                if (subscribedInstrument.MarketData == null || subscribedInstrument.MarketData.Last == null) return;

                double price = subscribedInstrument.MarketData.Last.Price;
                if (price <= 0) return;
                if (price == lastTick) return; // pas de nouveau tick

                lastTick = price;
                _tickCount++;
                _lastTickTime = DateTime.Now;

                // Portage simplifié de UpdateSessionTracking() (TelegramSignalStrategyV3.cs) :
                // pas de notion de "barre" dans un Add-On, donc on suit la session sur
                // la base du jour calendaire courant (reset à minuit) plutôt que sur
                // Bars.IsFirstBarOfSession qui n'existe pas hors contexte de Strategy.
                if (DateTime.Now.Date != _sessDate)
                {
                    _sessDate  = DateTime.Now.Date;
                    _sessOpen  = price;
                    _sessHigh  = price;
                    _sessLow   = price;
                    _sessStart = DateTime.Now.ToString("HH:mm");
                    _tickCount = 1;
                }
                else
                {
                    if (price > _sessHigh) _sessHigh = price;
                    if (price < _sessLow)  _sessLow  = price;
                }
            }
            catch { }
        }


        private double GetLastPrice(Account account, Instrument instrument)
        {
            try
            {
                if (account != null && instrument != null)
                {
                    var pos = account.Positions.FirstOrDefault(p => p.Instrument == instrument && p.MarketPosition != MarketPosition.Flat);
                    if (pos != null && pos.AveragePrice > 0) return pos.AveragePrice;
                }
                if (lastTick > 0) return lastTick;
                if (instrument != null && instrument.MarketData != null && instrument.MarketData.Last != null)
                    return instrument.MarketData.Last.Price;
            }
            catch { }
            return 0;
        }

        // ⚠️ CORRECTION IMPORTANTE : cette méthode se basait auparavant sur une
        // éventuelle position déjà ouverte sur le compte (n'importe quel instrument)
        // pour déterminer l'instrument à trader, ce qui provoquait un bug grave :
        // si le compte avait une position ouverte sur un instrument SANS RAPPORT
        // avec le signal (ex: CL JUN26 alors que le signal concerne MGC 12-25),
        // l'Add-On soumettait l'ordre sur le MAUVAIS instrument.
        // Priorité désormais : 1) instrument explicite du signal JSON (champ
        // "instrument"), 2) instrument par défaut configuré dans l'Add-On.
        private Instrument GetTradingInstrument(Account account, string signalInstrument)
        {
            try
            {
                if (!string.IsNullOrWhiteSpace(signalInstrument))
                {
                    Instrument fromSignal = ResolveInstrument(signalInstrument);
                    if (fromSignal != null) return fromSignal;
                }
                if (!string.IsNullOrWhiteSpace(Config.DefaultInstrument))
                {
                    Instrument fromConfig = ResolveInstrument(Config.DefaultInstrument);
                    if (fromConfig != null) return fromConfig;
                }
                if (subscribedInstrument != null) return subscribedInstrument;
                return null;
            }
            catch { return null; }
        }



        // ─────────────────────────────────────────────────────────
        // POLLING SIGNAL (identique dans l'esprit à la Strategy V3)
        // ─────────────────────────────────────────────────────────
        private void SafePoll()
        {
            try { PollSignal(); }
            catch (Exception ex) { WriteStatusFile("rejected", "exception_polling", ex.Message); }
            try { PollCommand(); } catch { }
        }

        private void SafeWritePrice()
        {
            try { PollPrice(); } catch { }
            try { WritePriceFile(); }
            catch { }
            try { WriteAccountsStatusFile(); } catch { }
        }

        // ─────────────────────────────────────────────────────────
        // COMMANDES DISTANTES (pilotage depuis l'application web via l'agent
        // local) : select_account, connect_connection, disconnect_connection.
        // Même pattern que PollSignal() (fichier + renommage ".processing"
        // pour éviter une lecture concurrente pendant l'écriture par l'agent),
        // mais sur un fichier séparé pour ne jamais interférer avec le flux
        // d'exécution des signaux de trading.
        // ─────────────────────────────────────────────────────────
        private void PollCommand()
        {
            if (!File.Exists(commandFile)) return;

            string content;
            try
            {
                File.Move(commandFile, commandProcessingFile);
                content = File.ReadAllText(commandProcessingFile, System.Text.Encoding.UTF8);
            }
            catch { return; }

            try
            {
                JObject cmd = JObject.Parse(content);
                string action = (string)cmd["action"];

                if (action == "select_account")
                {
                    string accountName = (string)cmd["account_name"];
                    if (!string.IsNullOrWhiteSpace(accountName))
                    {
                        // Capture la valeur AVANT mutation pour que SaveConfig()
                        // puisse détecter le changement et réinitialiser le blocage journalier.
                        string prevAcc = Config != null ? Config.SelectedAccountName : null;
                        TelegramConfig cfg = Config;
                        cfg.SelectedAccountName = accountName;
                        SaveConfig(cfg, prevAcc);
                    }
                }
                else if (action == "connect_connection" || action == "disconnect_connection")
                {
                    string connectionName = (string)cmd["connection_name"];
                    if (!string.IsNullOrWhiteSpace(connectionName))
                    {
                        Connection target = GetConnections()
                            .FirstOrDefault(c => GetConnectionDisplayName(c) == connectionName);
                        if (target != null)
                        {
                            if (action == "connect_connection") ConnectConnection(target);
                            else DisconnectConnection(target);
                        }
                    }
                }
            }
            catch { }
            finally
            {
                TryDelete(commandProcessingFile);
            }
        }

        /// <summary>
        /// Écrit périodiquement la liste des comptes disponibles (nom + solde),
        /// la liste des connexions (nom + statut + connectée ou non) et le compte
        /// actuellement sélectionné, afin que l'application web (via l'agent
        /// local) puisse afficher et piloter ces informations à distance, de la
        /// même façon que le panneau TelegramTraderWindow le fait localement.
        /// </summary>
        private void WriteAccountsStatusFile()
        {
            try
            {
                JArray accountsArr = new JArray();
                foreach (Account a in GetAvailableAccounts())
                {
                    double bal = 0;
                    try { bal = a.Get(AccountItem.CashValue, Currency.UsDollar); } catch { }
                    accountsArr.Add(new JObject
                    {
                        ["name"] = a.Name,
                        ["balance"] = bal
                    });
                }

                JArray connectionsArr = new JArray();
                foreach (Connection c in GetConnections())
                {
                    string statusStr;
                    try { statusStr = c.Status.ToString(); } catch { statusStr = "?"; }
                    bool isConnected = statusStr.IndexOf("Connected", StringComparison.OrdinalIgnoreCase) >= 0
                                       && statusStr.IndexOf("Disconnected", StringComparison.OrdinalIgnoreCase) < 0;
                    connectionsArr.Add(new JObject
                    {
                        ["name"] = GetConnectionDisplayName(c),
                        ["status"] = statusStr,
                        ["connected"] = isConnected
                    });
                }

                JObject obj = new JObject
                {
                    ["timestamp"] = DateTime.UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ"),
                    ["selected_account"] = Config.SelectedAccountName,
                    ["accounts"] = accountsArr,
                    ["connections"] = connectionsArr
                };
                File.WriteAllText(accountsStatusFile, obj.ToString(Formatting.None), System.Text.Encoding.UTF8);
            }
            catch { }
        }


        private void CheckDayReset()
        {
            if (DateTime.Now.Date != currentDay)
            {
                currentDay = DateTime.Now.Date;
                blocked = false;
                Account account = GetSelectedAccount();
                dailyStartBalance = account != null ? account.Get(AccountItem.CashValue, Currency.UsDollar) : 0;
            }

            Account acct = GetSelectedAccount();
            if (acct == null) return;
            double balance = acct.Get(AccountItem.CashValue, Currency.UsDollar);
            double pnl = balance - dailyStartBalance;
            if (!blocked)
            {
                if (pnl <= -Config.DailyLossLimit) blocked = true;
                else if (pnl >= Config.DailyProfitLimit) blocked = true;
            }
        }

        private void PollSignal()
        {
            CheckDayReset();
            if (blocked) return;
            if (!File.Exists(signalFile)) return;

            string content;
            try
            {
                File.Move(signalFile, processingFile);
                content = File.ReadAllText(processingFile, System.Text.Encoding.UTF8);
            }
            catch { return; }

            JObject signal;
            try { signal = JObject.Parse(content); }
            catch { Quarantine("json_structure_invalide"); return; }

            string direction     = (string)signal["direction"];
            double entry         = (double?)signal["entry"] ?? 0;
            double sl            = (double?)signal["sl"] ?? 0;
            double tp            = (double?)signal["tp"] ?? 0;
            int    contracts     = (int?)signal["contracts"] ?? 0;
            string timestamp     = (string)signal["timestamp"];
            string orderTypeStr  = (string)signal["order_type"];
            double riskOverride  = (double?)signal["risk_pct"] ?? 0;
            string signalInstrument = (string)signal["instrument"];


            string mode = string.IsNullOrEmpty(orderTypeStr)
                ? Config.DefaultOrderMode.ToUpperInvariant()
                : orderTypeStr.Trim().ToUpperInvariant();
            bool isMarket = mode == "MARKET";

            Account account = GetSelectedAccount();
            if (account == null) { Quarantine("aucun_compte_selectionne"); return; }

            Instrument instrument = GetTradingInstrument(account, signalInstrument);
            if (instrument == null) { Quarantine("instrument_introuvable"); return; }


            double lastPrice = GetLastPrice(account, instrument);

            if (isMarket && entry <= 0)
                entry = lastPrice > 0 ? lastPrice : entry;

            if (!string.IsNullOrEmpty(timestamp))
            {
                DateTime st;
                if (DateTime.TryParse(timestamp, CultureInfo.InvariantCulture,
                        DateTimeStyles.AdjustToUniversal | DateTimeStyles.AssumeUniversal, out st))
                {
                    if ((DateTime.UtcNow - st).TotalMinutes > 5) { Quarantine("signal_perime"); return; }
                }
            }

            if (string.IsNullOrEmpty(direction)) { Quarantine("direction_manquante"); return; }
            if (entry <= 0) { Quarantine("entry_manquant"); return; }
            if (sl <= 0)    { Quarantine("sl_manquant"); return; }
            if (tp <= 0)    { Quarantine("tp_manquant"); return; }

            if (direction == "BUY"  && sl >= entry) { Quarantine("sl_buy_invalide"); return; }
            if (direction == "SELL" && sl <= entry) { Quarantine("sl_sell_invalide"); return; }
            if (direction == "BUY"  && tp <= entry) { Quarantine("tp_buy_invalide"); return; }
            if (direction == "SELL" && tp >= entry) { Quarantine("tp_sell_invalide"); return; }

            double effectiveRisk = riskOverride > 0 ? riskOverride : Config.RiskPct;
            double balance   = account.Get(AccountItem.CashValue, Currency.UsDollar);
            double slPoints  = Math.Abs(entry - sl);
            double pointValue = instrument.MasterInstrument.PointValue;

            int finalQty;
            if (contracts > 0)
            {
                finalQty = Math.Min(contracts, Config.MaxContracts);
            }
            else if (balance > 0 && slPoints > 0 && pointValue > 0)
            {
                double maxRisk = balance * effectiveRisk / 100.0;
                finalQty = (int)Math.Floor(maxRisk / (slPoints * pointValue));
                finalQty = Math.Max(1, Math.Min(finalQty, Config.MaxContracts));
            }
            else finalQty = 1;

            string label = "TGAO_" + direction + "_" + DateTime.Now.ToString("HHmmss");

            try
            {
                OrderAction action = direction == "BUY" ? OrderAction.Buy : OrderAction.SellShort;

                if (isMarket)
                {
                    SubmitEntry(account, instrument, action, OrderType.Market, finalQty, 0, label, sl, tp, direction);
                }
                else
                {
                    double slippage = Math.Abs(lastPrice - entry);
                    if (lastPrice > 0 && slippage > Config.SlippageTolerancePoints)
                    {
                        Quarantine("slippage_excessif");
                        return;
                    }
                    SubmitEntry(account, instrument, action, OrderType.Limit, finalQty, entry, label, sl, tp, direction);
                }

                WriteStatusFile("executed", "ok",
                    direction + " " + finalQty + " @ " + entry.ToString("F2") + " (" + mode + ") compte=" + account.Name);
                TryDelete(processingFile);
            }
            catch (Exception ex)
            {
                Quarantine("exception_execution_" + ex.Message.Replace(" ", "_"));
            }
        }

        private void SubmitEntry(Account account, Instrument instrument, OrderAction action, OrderType type,
            int qty, double limitPrice, string label, double sl, double tp, string direction)
        {
            lock (lockObj)
            {
                pendingEntryName = label;
                pendingDirection = direction;
                pendingSl = sl;
                pendingTp = tp;
            }

            Order order = account.CreateOrder(
                instrument, action, type, OrderEntry.Automated, TimeInForce.Day,
                qty, limitPrice, 0, "", label, Core.Globals.MaxDate, null);

            account.Submit(new[] { order });
        }

        private void OnExecutionUpdate(object sender, ExecutionEventArgs e)
        {
            try
            {
                if (e == null || e.Execution == null || e.Execution.Order == null) return;
                string name = e.Execution.Order.Name;
                if (string.IsNullOrEmpty(name) || !name.StartsWith("TGAO_")) return;

                string dir; double sl, tp;
                lock (lockObj)
                {
                    if (name != pendingEntryName) return;
                    dir = pendingDirection; sl = pendingSl; tp = pendingTp;
                    pendingEntryName = null; // consommé (évite double pose du bracket)
                }

                int filledQty = e.Execution.Order.Filled;
                if (filledQty <= 0) return;

                Account acct  = e.Execution.Order.Account;
                Instrument instr = e.Execution.Order.Instrument;
                if (acct == null || instr == null) return;

                OrderAction exitAction = dir == "BUY" ? OrderAction.Sell : OrderAction.BuyToCover;
                string oco = "TGAO_OCO_" + DateTime.Now.ToString("HHmmssfff");

                Order slOrder = acct.CreateOrder(instr, exitAction, OrderType.StopMarket, OrderEntry.Automated,
                    TimeInForce.Day, filledQty, 0, sl, oco, name + "_SL", Core.Globals.MaxDate, null);
                Order tpOrder = acct.CreateOrder(instr, exitAction, OrderType.Limit, OrderEntry.Automated,
                    TimeInForce.Day, filledQty, tp, 0, oco, name + "_TP", Core.Globals.MaxDate, null);

                acct.Submit(new[] { slOrder, tpOrder });
            }
            catch { }
        }

        // ─────────────────────────────────────────────────────────
        // FICHIERS D'ÉCHANGE (mêmes formats que la Strategy V3)
        // ─────────────────────────────────────────────────────────
        private void Quarantine(string reason)
        {
            WriteStatusFile("rejected", reason);
            try
            {
                if (File.Exists(processingFile))
                {
                    string safeReason = reason.Replace(":", "_").Replace(" ", "_");
                    string qf = processingFile.Replace(".processing",
                        "_error_" + DateTime.Now.ToString("yyyyMMdd_HHmmss") + "_" + safeReason + ".json");
                    File.Move(processingFile, qf);
                }
            }
            catch { }
        }

        private void TryDelete(string f)
        {
            try { if (File.Exists(f)) File.Delete(f); } catch { }
        }

        private void WriteStatusFile(string status, string reason, string extra = "")
        {
            LastStatus = status; LastReason = reason; LastExtra = extra; LastStatusTime = DateTime.Now;
            try
            {
                JObject obj = new JObject
                {
                    ["timestamp"] = DateTime.UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ"),
                    ["status"] = status,
                    ["reason"] = reason,
                    ["extra"] = extra
                };
                File.WriteAllText(statusFile, obj.ToString(Formatting.None), System.Text.Encoding.UTF8);
            }
            catch { }
        }

        private void WritePriceFile()
        {
            Account account = GetSelectedAccount();
            double balance = account != null ? account.Get(AccountItem.CashValue, Currency.UsDollar) : 0;
            double pnl = account != null ? balance - dailyStartBalance : 0;
            bool posOpen = false;
            try { posOpen = account != null && account.Positions.Any(p => p.MarketPosition != MarketPosition.Flat); }
            catch { }

            // Nom de l'instrument actif (utilisé par l'agent Python pour remonter
            // la liste des instruments disponibles au frontend via le heartbeat)
            string instrName = CurrentInstrumentName ?? Config.DefaultInstrument ?? "";

            JObject obj = new JObject
            {
                ["timestamp"] = DateTime.UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ"),
                ["instrument"] = instrName,
                ["mid"] = lastTick,
                ["daily_pnl"] = pnl,
                ["account_balance"] = balance,
                ["trading_blocked"] = blocked,
                ["position_open"] = posOpen
            };
            File.WriteAllText(priceFile, obj.ToString(Formatting.None), System.Text.Encoding.UTF8);
        }
    }

    // ════════════════════════════════════════════════════════════════
    // 4) FENÊTRE DE CONTRÔLE (panneau WPF, construit en code — pas de
    //    fichier .xaml séparé pour rester dans UN SEUL fichier .cs)
    // ════════════════════════════════════════════════════════════════
    public class TelegramTraderWindow : Window
    {
        private readonly TelegramTraderEngine engine;
        private readonly DispatcherTimer refreshTimer;

        private ComboBox accountCombo;
        private TextBlock accountBalanceText;
        private StackPanel connectionsPanel;
        private TextBlock lastSignalText;
        private TextBlock priceText;
        private TextBlock calibrationText;


        private TextBox riskPctBox, maxContractsBox, dailyLossBox, dailyProfitBox,
                         slippageBox, pollSecBox, instrumentBox;
        private ComboBox orderModeCombo;
        private TextBlock engineStatusText;

        public TelegramTraderWindow()
        {
            engine = TelegramTraderEngine.Instance;

            Title = "TelegramTrader — Manager";
            Width = 480;
            Height = 720;
            WindowStartupLocation = WindowStartupLocation.CenterScreen;
            Background = new SolidColorBrush(Color.FromRgb(30, 30, 30));

            BuildUI();
            RefreshAll();

            refreshTimer = new DispatcherTimer { Interval = TimeSpan.FromSeconds(2) };
            refreshTimer.Tick += (s, e) => RefreshAll();
            refreshTimer.Start();

            Closed += (s, e) => refreshTimer.Stop();
        }

        private static TextBlock Label(string text, bool bold = false)
        {
            return new TextBlock
            {
                Text = text,
                Foreground = Brushes.White,
                FontWeight = bold ? FontWeights.Bold : FontWeights.Normal,
                Margin = new Thickness(0, 6, 0, 2)
            };
        }

        private void BuildUI()
        {
            ScrollViewer scroll = new ScrollViewer { VerticalScrollBarVisibility = ScrollBarVisibility.Auto };
            StackPanel root = new StackPanel { Margin = new Thickness(14) };
            scroll.Content = root;
            Content = scroll;

            root.Children.Add(new TextBlock
            {
                Text = "🤖 TelegramTrader — Manager multi-comptes",
                Foreground = Brushes.White,
                FontSize = 16,
                FontWeight = FontWeights.Bold,
                Margin = new Thickness(0, 0, 0, 10)
            });

            engineStatusText = Label("");
            root.Children.Add(engineStatusText);

            // ⚠️ Bouton de secours : un F5 (compilation) dans NinjaTrader ne recrée
            // PAS la fenêtre Control Center déjà ouverte, donc le moteur peut rester
            // bloqué dans un état "actif" mais avec des timers/références obsolètes
            // (plus aucune mise à jour de nt8_current_price.json). Ce bouton force
            // un arrêt + redémarrage complet du moteur sans avoir à fermer NinjaTrader.
            Button restartBtn = new Button
            {
                Content = "🔄 Redémarrer le moteur",
                Margin = new Thickness(0, 4, 0, 8),
                Padding = new Thickness(8, 4, 8, 4),
                HorizontalAlignment = HorizontalAlignment.Left
            };
            restartBtn.Click += (s, e) =>
            {
                engine.ForceRestart();
                RefreshAll();
                MessageBox.Show("Moteur redémarré.", "TelegramTrader", MessageBoxButton.OK, MessageBoxImage.Information);
            };
            root.Children.Add(restartBtn);

            // ⚠️ Bouton de secours n°2 : débloque manuellement le trading si le
            // blocage journalier (perte/gain max) s'est déclenché à tort — par
            // exemple à cause d'une position restée ouverte par erreur sur le
            // compte (le PnL journalier était alors calculé sur tout le mouvement
            // de cette position, pas sur les trades réels de l'Add-On).
            Button unblockBtn = new Button
            {
                Content = "🔓 Débloquer le trading (reset PnL du jour)",
                Margin = new Thickness(0, 0, 0, 8),
                Padding = new Thickness(8, 4, 8, 4),
                HorizontalAlignment = HorizontalAlignment.Left
            };
            unblockBtn.Click += (s, e) =>
            {
                engine.ResetDailyBlock();
                RefreshAll();
                MessageBox.Show("Blocage journalier réinitialisé.", "TelegramTrader", MessageBoxButton.OK, MessageBoxImage.Information);
            };
            root.Children.Add(unblockBtn);

            // ── Compte actif ─────────────────────────────────────


            root.Children.Add(Label("Compte actif pour l'exécution des signaux :", true));
            accountCombo = new ComboBox { Margin = new Thickness(0, 2, 0, 2) };
            accountCombo.SelectionChanged += (s, e) =>
            {
                if (accountCombo.SelectedItem != null)
                {
                    // Capture la valeur AVANT mutation pour que SaveConfig()
                    // puisse détecter le changement et réinitialiser le blocage journalier.
                    string prevAcc = engine.Config != null ? engine.Config.SelectedAccountName : null;
                    engine.Config.SelectedAccountName = accountCombo.SelectedItem.ToString();
                    engine.SaveConfig(engine.Config, prevAcc);
                }
            };
            root.Children.Add(accountCombo);
            accountBalanceText = Label("Solde : —");
            root.Children.Add(accountBalanceText);

            // ── Connexions ───────────────────────────────────────
            root.Children.Add(Label("Connexions disponibles (Rithmic / Tradovate / Simulated...) :", true));
            connectionsPanel = new StackPanel();
            root.Children.Add(connectionsPanel);

            // ── Prix / statut live ───────────────────────────────
            root.Children.Add(Label("État en direct :", true));
            priceText = Label("—");
            root.Children.Add(priceText);
            lastSignalText = Label("Aucun signal traité récemment.");
            root.Children.Add(lastSignalText);

            // ── Panneau de calibration (portage simplifié du panneau OHLC/session
            // de TelegramSignalStrategyV3.cs — voir TelegramTraderEngine.SessOpen/
            // SessHigh/SessLow/etc. Pas de vraies barres OHLC hors contexte de
            // graphique, donc suivi basé sur les ticks Level1 reçus). ──
            root.Children.Add(new Separator { Margin = new Thickness(0, 10, 0, 10) });
            root.Children.Add(Label("📊 Panneau de calibration (session) :", true));
            calibrationText = new TextBlock
            {
                Text = "En attente de données de marché...",
                Foreground = Brushes.Cyan,
                FontFamily = new FontFamily("Consolas"),
                FontSize = 12,
                Margin = new Thickness(0, 2, 0, 2),
                TextWrapping = TextWrapping.Wrap
            };
            root.Children.Add(calibrationText);

            // ── Paramètres trading ───────────────────────────────

            root.Children.Add(new Separator { Margin = new Thickness(0, 10, 0, 10) });
            root.Children.Add(Label("Paramètres de trading :", true));

            root.Children.Add(Label("Type d'ordre par défaut (si non précisé par le signal) :"));
            orderModeCombo = new ComboBox();
            orderModeCombo.Items.Add("Market");
            orderModeCombo.Items.Add("Limit");
            root.Children.Add(orderModeCombo);

            root.Children.Add(Label("% risque par trade :"));
            riskPctBox = new TextBox();
            root.Children.Add(riskPctBox);

            root.Children.Add(Label("Contrats max :"));
            maxContractsBox = new TextBox();
            root.Children.Add(maxContractsBox);

            root.Children.Add(Label("Perte max / jour ($) :"));
            dailyLossBox = new TextBox();
            root.Children.Add(dailyLossBox);

            root.Children.Add(Label("Gain max / jour ($) :"));
            dailyProfitBox = new TextBox();
            root.Children.Add(dailyProfitBox);

            root.Children.Add(Label("Tolérance glissement (points) :"));
            slippageBox = new TextBox();
            root.Children.Add(slippageBox);

            root.Children.Add(Label("Vérification signal (sec) :"));
            pollSecBox = new TextBox();
            root.Children.Add(pollSecBox);

            root.Children.Add(Label("Instrument par défaut (ex: MGC 12-25) :"));
            instrumentBox = new TextBox();
            root.Children.Add(instrumentBox);

            Button saveBtn = new Button
            {
                Content = "💾 Enregistrer les paramètres",
                Margin = new Thickness(0, 12, 0, 4),
                Padding = new Thickness(8, 4, 8, 4)
            };
            saveBtn.Click += (s, e) => SaveSettings();
            root.Children.Add(saveBtn);

            LoadSettingsIntoUI();
        }

        private void LoadSettingsIntoUI()
        {
            TelegramConfig c = engine.Config;
            orderModeCombo.SelectedItem = c.DefaultOrderMode;
            if (orderModeCombo.SelectedItem == null) orderModeCombo.SelectedIndex = 1;
            riskPctBox.Text        = c.RiskPct.ToString(CultureInfo.InvariantCulture);
            maxContractsBox.Text   = c.MaxContracts.ToString(CultureInfo.InvariantCulture);
            dailyLossBox.Text      = c.DailyLossLimit.ToString(CultureInfo.InvariantCulture);
            dailyProfitBox.Text    = c.DailyProfitLimit.ToString(CultureInfo.InvariantCulture);
            slippageBox.Text       = c.SlippageTolerancePoints.ToString(CultureInfo.InvariantCulture);
            pollSecBox.Text        = c.PollSec.ToString(CultureInfo.InvariantCulture);
            instrumentBox.Text     = c.DefaultInstrument;
        }

        private void SaveSettings()
        {
            TelegramConfig c = engine.Config;
            double d;
            int i;

            if (orderModeCombo.SelectedItem != null) c.DefaultOrderMode = orderModeCombo.SelectedItem.ToString();
            if (double.TryParse(riskPctBox.Text, NumberStyles.Any, CultureInfo.InvariantCulture, out d)) c.RiskPct = d;
            if (int.TryParse(maxContractsBox.Text, out i)) c.MaxContracts = i;
            if (double.TryParse(dailyLossBox.Text, NumberStyles.Any, CultureInfo.InvariantCulture, out d)) c.DailyLossLimit = d;
            if (double.TryParse(dailyProfitBox.Text, NumberStyles.Any, CultureInfo.InvariantCulture, out d)) c.DailyProfitLimit = d;
            if (double.TryParse(slippageBox.Text, NumberStyles.Any, CultureInfo.InvariantCulture, out d)) c.SlippageTolerancePoints = d;
            if (int.TryParse(pollSecBox.Text, out i)) c.PollSec = Math.Max(1, i);
            c.DefaultInstrument = instrumentBox.Text.Trim();

            engine.SaveConfig(c);
            MessageBox.Show("Paramètres enregistrés.", "TelegramTrader", MessageBoxButton.OK, MessageBoxImage.Information);
        }

        private void RefreshAll()
        {
            engineStatusText.Text = engine.IsRunning
                ? "🟢 Moteur actif — surveillance des signaux en cours"
                : "🔴 Moteur arrêté";

            // Comptes
            string previouslySelected = accountCombo.SelectedItem as string;
            List<Account> accounts = engine.GetAvailableAccounts();
            accountCombo.Items.Clear();
            foreach (Account a in accounts)
                accountCombo.Items.Add(a.Name);

            if (!string.IsNullOrEmpty(engine.Config.SelectedAccountName) &&
                accountCombo.Items.Contains(engine.Config.SelectedAccountName))
            {
                accountCombo.SelectedItem = engine.Config.SelectedAccountName;
            }
            else if (previouslySelected != null && accountCombo.Items.Contains(previouslySelected))
            {
                accountCombo.SelectedItem = previouslySelected;
            }

            Account selected = engine.GetSelectedAccount();
            if (selected != null)
            {
                double bal = 0;
                try { bal = selected.Get(AccountItem.CashValue, Currency.UsDollar); } catch { }
                accountBalanceText.Text = "Solde : $" + bal.ToString("F2");
            }
            else
            {
                accountBalanceText.Text = "Solde : — (aucun compte sélectionné)";
            }

            // Connexions
            connectionsPanel.Children.Clear();
            List<Connection> connections = engine.GetConnections();
            if (connections.Count == 0)
            {
                connectionsPanel.Children.Add(Label("Aucune connexion configurée dans NinjaTrader."));
            }
            foreach (Connection c in connections)
            {
                StackPanel row = new StackPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(0, 2, 0, 2) };

                string statusStr;
                try { statusStr = c.Status.ToString(); } catch { statusStr = "?"; }
                bool isConnected = statusStr.IndexOf("Connected", StringComparison.OrdinalIgnoreCase) >= 0
                                   && statusStr.IndexOf("Disconnected", StringComparison.OrdinalIgnoreCase) < 0;

                string cname = engine.GetConnectionDisplayName(c);


                row.Children.Add(new TextBlock
                {
                    Text = (isConnected ? "🟢 " : "⚪ ") + cname + " [" + statusStr + "]",
                    Foreground = Brushes.White,
                    Width = 260,
                    VerticalAlignment = VerticalAlignment.Center
                });

                Button toggleBtn = new Button
                {
                    Content = isConnected ? "Déconnecter" : "Connecter",
                    Padding = new Thickness(6, 2, 6, 2),
                    Margin = new Thickness(4, 0, 0, 0)
                };
                Connection captured = c;
                toggleBtn.Click += (s, e) =>
                {
                    if (isConnected) engine.DisconnectConnection(captured);
                    else engine.ConnectConnection(captured);
                };
                row.Children.Add(toggleBtn);

                connectionsPanel.Children.Add(row);
            }

            // Prix / statut
            priceText.Text = "Instrument suivi : " + engine.Config.DefaultInstrument;

            if (engine.LastStatus == "executed")
            {
                lastSignalText.Text = "✅ Dernier signal EXÉCUTÉ (" + engine.LastStatusTime.ToString("HH:mm:ss") + ")\n" + engine.LastExtra;
                lastSignalText.Foreground = Brushes.LightGreen;
            }
            else if (engine.LastStatus == "rejected")
            {
                lastSignalText.Text = "❌ Dernier signal REJETÉ (" + engine.LastStatusTime.ToString("HH:mm:ss") + ")\nRaison : " + engine.LastReason;
                lastSignalText.Foreground = Brushes.OrangeRed;
            }
            else
            {
                lastSignalText.Text = "Aucun signal traité récemment.";
                lastSignalText.Foreground = Brushes.White;
            }

            RefreshCalibrationPanel();
        }

        /// <summary>
        /// Portage simplifié de RenderCalibrationPanel() (TelegramSignalStrategyV3.cs),
        /// affiché ici dans un TextBlock du panneau WPF plutôt que dessiné sur un
        /// graphique (un Add-On n'a pas de contexte de graphique par défaut). Les
        /// données OHLC/ATR/Volume "par barre" ne sont pas disponibles hors Strategy ;
        /// on affiche donc les données de session accumulées à partir des ticks Level1
        /// (dernier prix, plus haut/bas de session, range, variation depuis l'ouverture).
        /// </summary>
        private void RefreshCalibrationPanel()
        {
            try
            {
                double last  = engine.LastPrice;
                double open  = engine.SessOpen;
                double high  = engine.SessHigh;
                double low   = engine.SessLow;
                double range = high - low;
                double chg   = last - open;
                double chgPct = open != 0 ? (chg / open) * 100.0 : 0.0;
                string chgSign = chg >= 0 ? "+" : "";

                if (last <= 0)
                {
                    calibrationText.Text = "En attente de données de marché pour " + engine.CurrentInstrumentName + "...\n" +
                        "(vérifiez qu'un compte est connecté et que l'instrument est correct)";
                    return;
                }

                string text =
                    "  INSTRUMENT : " + engine.CurrentInstrumentName + "\n" +
                    "  DATE/HEURE : " + DateTime.Now.ToString("dd/MM/yyyy HH:mm:ss") + "\n" +
                    "  ------------------------------\n" +
                    "  -- DEPUIS OUVERTURE SESSION (" + engine.SessStart + ") --\n" +
                    "  TICKS REÇUS : " + engine.TickCount + "\n" +
                    "  OPEN SES.   : " + open.ToString("F2") + "\n" +
                    "  HIGH MAX    : " + high.ToString("F2") + "\n" +
                    "  LOW MIN     : " + low.ToString("F2") + "\n" +
                    "  LAST        : " + last.ToString("F2") + "\n" +
                    "  RANGE       : " + range.ToString("F2") + " pts\n" +
                    "  VARIATION   : " + chgSign + chg.ToString("F2") + " pts (" + chgSign + chgPct.ToString("F2") + "%)\n" +
                    "  ------------------------------\n" +
                    "  TICK SIZE   : " + engine.TickSize.ToString("F4") + "\n" +
                    "  POINT VALUE : $" + engine.PointValue.ToString("F2") + "\n" +
                    "  DERNIER TICK: " + (engine.LastTickTime == DateTime.MinValue ? "—" : engine.LastTickTime.ToString("HH:mm:ss"));

                calibrationText.Text = text;
            }
            catch (Exception ex)
            {
                calibrationText.Text = "Erreur panneau calibration : " + ex.Message;
            }
        }
    }
}



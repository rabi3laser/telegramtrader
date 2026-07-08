import { useState, useEffect } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { Info, Download, KeyRound, Wifi, WifiOff, Copy, Clock, ChevronDown, ChevronUp, FileCode, Unlink, Landmark, Plug, PlugZap, CheckCircle2, Activity, Server, Monitor, AlertTriangle, Package } from 'lucide-react'


import { nt8AgentService } from '../services/nt8AgentService'
import type { ConnectorHealth } from '../services/nt8AgentService'
import { useAuthStore } from '../store/authStore'


export default function SettingsPage() {
  const { user } = useAuthStore()
  const queryClient = useQueryClient()

  // ── AGENT LOCAL NINJATRADER 8 (100% gratuit, sans CrossTrade) ──────────
  const [agentAccountName, setAgentAccountName] = useState('')
  const [pairingCode, setPairingCode] = useState<string | null>(null)
  const [pairingExpiresAt, setPairingExpiresAt] = useState<number | null>(null)
  const [pairingCountdown, setPairingCountdown] = useState<string>('')
  const [showAdvanced, setShowAdvanced] = useState(false)

  const { data: agentStatus, isLoading: agentLoading, isError: agentError } = useQuery({
    queryKey: ['nt8-agent', 'status'],
    queryFn: nt8AgentService.getStatus,
    refetchInterval: 5000, // rafraîchit le statut de connexion toutes les 5s
    // Ne pas afficher d'erreur toast automatique — on gère l'état visuellement
    // dans le rendu pour ne pas spammer l'utilisateur toutes les 5 secondes.
    retry: 2,
  })

  // Dès que l'agent devient connecté, on efface le code d'appairage affiché
  useEffect(() => {
    if (agentStatus?.connected && pairingCode) {
      setPairingCode(null)
      toast.success('Agent connecté avec succès ✅')
    }
  }, [agentStatus?.connected])

  // Compte à rebours d'expiration du code d'appairage affiché
  useEffect(() => {
    if (!pairingExpiresAt) {
      setPairingCountdown('')
      return
    }
    const interval = setInterval(() => {
      const remaining = Math.max(0, Math.floor(pairingExpiresAt - Date.now() / 1000))
      if (remaining <= 0) {
        setPairingCode(null)
        setPairingExpiresAt(null)
        setPairingCountdown('')
        clearInterval(interval)
      } else {
        const m = Math.floor(remaining / 60)
        const s = remaining % 60
        setPairingCountdown(`${m}:${s.toString().padStart(2, '0')}`)
      }
    }, 1000)
    return () => clearInterval(interval)
  }, [pairingExpiresAt])

  const generatePairingCodeMutation = useMutation({
    mutationFn: () => nt8AgentService.generatePairingCode(agentAccountName || undefined),
    onSuccess: (res) => {
      setPairingCode(res.code)
      setPairingExpiresAt(res.expires_at)
      toast.success('Code généré ! Saisissez-le dans la fenêtre de TelegramTraderAgent.exe.')
      queryClient.invalidateQueries({ queryKey: ['nt8-agent', 'status'] })
    },
    onError: () => toast.error('Erreur lors de la génération du code'),
  })

  const generateAgentTokenMutation = useMutation({
    mutationFn: () => nt8AgentService.generateToken(agentAccountName || undefined),
    onSuccess: () => {
      toast.success('Token généré ! Téléchargez maintenant le script agent.')
      queryClient.invalidateQueries({ queryKey: ['nt8-agent', 'status'] })
    },
    onError: () => toast.error('Erreur lors de la génération du token'),
  })

  const revokeAgentMutation = useMutation({
    mutationFn: () => nt8AgentService.revokeToken(),
    onSuccess: () => {
      toast.success('Agent local révoqué')
      setPairingCode(null)
      queryClient.invalidateQueries({ queryKey: ['nt8-agent', 'status'] })
    },
    onError: () => toast.error('Erreur lors de la révocation'),
  })

  // ── DASHBOARD DE SANTÉ DU CONNECTEUR (amélioration A) ──────────────────
  const { data: healthData, isError: healthError } = useQuery<ConnectorHealth>({
    queryKey: ['nt8-agent', 'health'],
    queryFn: nt8AgentService.getConnectorHealth,
    // Rafraîchissement toutes les 5s — même fréquence que le statut agent
    // pour que le dashboard reste synchronisé avec l'état réel du connecteur.
    refetchInterval: 5000,
    enabled: !!agentStatus?.linked,
    retry: 1,
  })

  // ── GESTION DES COMPTES / CONNEXIONS NINJATRADER (pilotage à distance) ──
  const { data: accountsData, isLoading: accountsLoading, isError: accountsError } = useQuery({
    queryKey: ['nt8-agent', 'accounts'],
    queryFn: nt8AgentService.getAccountsStatus,
    enabled: !!agentStatus?.linked,
    refetchInterval: 5000,
    retry: 2,
  })
  const accountsStatus = accountsData?.accounts_status

  const selectAccountMutation = useMutation({
    mutationFn: (accountName: string) => nt8AgentService.selectAccount(accountName),
    onSuccess: (_data, accountName) => {
      toast.success(`Commande envoyée : sélection du compte ${accountName}`)
      queryClient.invalidateQueries({ queryKey: ['nt8-agent', 'accounts'] })
    },
    onError: () => toast.error('Erreur lors de l\'envoi de la commande de sélection de compte'),
  })

  const toggleConnectionMutation = useMutation({
    mutationFn: ({ name, connect }: { name: string; connect: boolean }) =>
      nt8AgentService.toggleConnection(name, connect),
    onSuccess: (_data, vars) => {
      toast.success(`Commande envoyée : ${vars.connect ? 'connexion' : 'déconnexion'} de ${vars.name}`)
      queryClient.invalidateQueries({ queryKey: ['nt8-agent', 'accounts'] })
    },
    onError: () => toast.error('Erreur lors de l\'envoi de la commande de connexion'),
  })


  const handleDownloadScript = async () => {
    try {
      await nt8AgentService.downloadScript()
      toast.success('Script téléchargé ! Lancez-le sur la machine où tourne NinjaTrader 8.')
    } catch {
      toast.error('Erreur lors du téléchargement du script')
    }
  }

  const handleDownloadExe = async () => {
    try {
      await nt8AgentService.downloadExe()
      toast.success("Téléchargement lancé ! Double-cliquez sur TelegramTraderAgent.exe une fois terminé.")
    } catch {
      toast.error("L'exécutable n'est pas encore disponible sur ce serveur — utilisez le script Python en attendant.")
    }
  }

  const handleDownloadStrategy = async () => {
    try {
      await nt8AgentService.downloadStrategy()
      toast.success(
        "Stratégie téléchargée ! Copiez-la dans Documents\\NinjaTrader 8\\bin\\Custom\\Strategies\\ puis compilez (F5)."
      )
    } catch {
      toast.error("Erreur lors du téléchargement de la stratégie NinjaTrader.")
    }
  }


  const handleCopyCode = () => {
    if (pairingCode) {
      navigator.clipboard.writeText(pairingCode)
      toast.success('Code copié !')
    }
  }



  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Paramètres</h1>
        <p className="text-gray-500 dark:text-gray-400">Configuration de l'application</p>
      </div>

      <div className="card space-y-3">
        <h2 className="text-lg font-semibold">Compte Telegram</h2>
        <div className="text-sm text-gray-600 dark:text-gray-400">
          <p>Nom : {user?.first_name} {user?.last_name}</p>
          <p>Téléphone : {user?.phone}</p>
          <p>Username : {user?.username ? `@${user.username}` : '-'}</p>
        </div>
      </div>

      <div className="card space-y-4 border-2 border-green-200 dark:border-green-900">
        <h2 className="text-lg font-semibold flex items-center gap-2">
          <KeyRound className="h-5 w-5" /> Agent local NinjaTrader 8 (100% gratuit, sans CrossTrade)
        </h2>

        <div className="flex items-start gap-2 text-sm text-green-700 dark:text-green-400 bg-green-50 dark:bg-green-900/20 rounded-lg p-3">
          <Info className="h-4 w-4 flex-shrink-0 mt-0.5" />
          <p>
            Solution recommandée — 3 clics : <strong>1)</strong> téléchargez l'exécutable
            Windows ci-dessous, <strong>2)</strong> double-cliquez dessus (aucune installation
            Python requise, une icône apparaît dans la zone de notification), <strong>3)</strong>{' '}
            saisissez le code d'appairage généré ici. L'agent se connecte automatiquement,
            démarre avec Windows et exécute vos signaux sur NinjaTrader 8 (stratégie{' '}
            <strong>TelegramSignalStrategyV3</strong>) — sans CrossTrade ni frais mensuels.
          </p>
        </div>

        <div className="flex items-start gap-3 rounded-lg p-3 border-2 border-dashed border-purple-300 dark:border-purple-800 bg-purple-50 dark:bg-purple-900/20">
          <FileCode className="h-5 w-5 flex-shrink-0 text-purple-700 dark:text-purple-400 mt-0.5" />
          <div className="flex-1 space-y-2">
            <p className="text-sm text-purple-800 dark:text-purple-300">
              <strong>Étape préalable indispensable :</strong> installez d'abord la stratégie
              NinjaScript dans NinjaTrader 8 — sans elle, l'agent ne peut exécuter aucun signal.
            </p>
            <button
              className="btn-secondary flex items-center gap-2 text-sm"
              onClick={handleDownloadStrategy}
            >
              <Download className="h-4 w-4" />
              Télécharger la stratégie NinjaTrader (.cs)
            </button>
            <p className="text-xs text-purple-700 dark:text-purple-400">
              Copiez le fichier dans <code>Documents\NinjaTrader 8\bin\Custom\Strategies\</code>,
              puis dans NinjaTrader : Tools → Edit NinjaScript → Compiler (F5), et appliquez
              « TelegramSignalStrategyV3 » comme Stratégie sur votre graphique.
            </p>
          </div>
        </div>

        {agentLoading ? (
          <p className="text-sm text-gray-500 dark:text-gray-400">Chargement...</p>
        ) : agentError ? (
          // Erreur API : afficher un message clair plutôt qu'un état trompeur
          <div className="flex items-start gap-2 text-sm text-red-700 dark:text-red-400 bg-red-50 dark:bg-red-900/20 rounded-lg p-3">
            <Info className="h-4 w-4 flex-shrink-0 mt-0.5" />
            <p>
              Impossible de contacter le serveur pour récupérer le statut de l'agent.
              Vérifiez que le backend est bien démarré.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {agentStatus?.linked && (
              <div
                className={`flex items-center gap-2 text-sm rounded-lg p-3 ${
                  agentStatus.connected
                    ? 'text-green-700 dark:text-green-400 bg-green-50 dark:bg-green-900/20'
                    : 'text-yellow-700 dark:text-yellow-400 bg-yellow-50 dark:bg-yellow-900/20'
                }`}
              >
                {agentStatus.connected ? (
                  <Wifi className="h-4 w-4 flex-shrink-0" />
                ) : (
                  <WifiOff className="h-4 w-4 flex-shrink-0" />
                )}
                <div>
                  <p className="font-medium">
                    {agentStatus.connected ? 'Agent connecté ✅' : 'Agent en attente de connexion...'}
                  </p>
                  <p className="text-xs">
                    Token : {agentStatus.token_masked} · Compte : {agentStatus.account_name || '—'}
                  </p>
                  {agentStatus.last_price && (
                    <p className="text-xs mt-1">
                      Solde : {agentStatus.last_price.balance ?? '—'} · PnL :{' '}
                      {agentStatus.last_price.pnl ?? '—'} · Position :{' '}
                      {agentStatus.last_price.position ?? '—'}
                    </p>
                  )}
                </div>
              </div>
            )}

            {!agentStatus?.linked && (
              <div>
                <label className="block text-sm font-medium mb-1">Nom du compte (optionnel)</label>
                <input
                  type="text"
                  className="input"
                  placeholder="ex: Sim101, MonCompteReel"
                  value={agentAccountName}
                  onChange={(e) => setAgentAccountName(e.target.value)}
                />
              </div>
            )}

            <div className="flex flex-wrap gap-2">
              <button
                className="btn-primary flex items-center gap-2 text-sm"
                onClick={handleDownloadExe}
              >
                <Download className="h-4 w-4" />
                Télécharger l'agent (.exe)
              </button>
              {!agentStatus?.connected && (
                <button
                  className="btn-secondary flex items-center gap-2 text-sm"
                  onClick={() => generatePairingCodeMutation.mutate()}
                  disabled={generatePairingCodeMutation.isPending}
                >
                  <KeyRound className="h-4 w-4" />
                  {generatePairingCodeMutation.isPending
                    ? 'Génération...'
                    : agentStatus?.linked
                    ? 'Régénérer un code d\'appairage'
                    : "Générer un code d'appairage"}
                </button>
              )}
              {agentStatus?.linked && (
                <button
                  className="btn-secondary flex items-center gap-2 text-sm"
                  onClick={handleDownloadScript}
                >
                  <Download className="h-4 w-4" />
                  Script Python (secours)
                </button>
              )}
              {agentStatus?.linked && (
                <button
                  className="btn-danger flex items-center gap-2 text-sm"
                  onClick={() => {
                    if (confirm('Révoquer cet agent ? Vous devrez régénérer un code et relancer l\'agent.')) {
                      revokeAgentMutation.mutate()
                    }
                  }}
                  disabled={revokeAgentMutation.isPending}
                >
                  <Unlink className="h-4 w-4" />
                  Révoquer l'agent
                </button>
              )}
            </div>

            {pairingCode && (
              <div className="flex flex-col sm:flex-row sm:items-center gap-3 text-sm bg-blue-50 dark:bg-blue-900/20 rounded-lg p-4 border border-blue-200 dark:border-blue-900">
                <div className="flex-1">
                  <p className="text-xs text-blue-700 dark:text-blue-400 mb-1">
                    Saisissez ce code dans la fenêtre de TelegramTraderAgent.exe :
                  </p>
                  <div className="flex items-center gap-2">
                    <span className="text-2xl font-mono font-bold tracking-widest text-blue-800 dark:text-blue-300">
                      {pairingCode}
                    </span>
                    <button
                      className="btn-secondary flex items-center gap-1 text-xs px-2 py-1"
                      onClick={handleCopyCode}
                      title="Copier le code"
                    >
                      <Copy className="h-3.5 w-3.5" />
                      Copier
                    </button>
                  </div>
                </div>
                {pairingCountdown && (
                  <div className="flex items-center gap-1 text-xs text-blue-700 dark:text-blue-400 whitespace-nowrap">
                    <Clock className="h-3.5 w-3.5" />
                    Expire dans {pairingCountdown}
                  </div>
                )}
              </div>
            )}

            {!agentStatus?.linked && (
              <>
                <button
                  type="button"
                  className="text-xs text-gray-500 dark:text-gray-400 flex items-center gap-1 hover:underline"
                  onClick={() => setShowAdvanced((v) => !v)}
                >
                  {showAdvanced ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
                  Solution alternative : script Python (si l'exe est bloqué par un antivirus)
                </button>

                {showAdvanced && (
                  <div className="space-y-3 border-t border-gray-200 dark:border-gray-700 pt-3">
                    <p className="text-xs text-gray-500 dark:text-gray-400">
                      Générez un token classique et téléchargez un script Python
                      pré-configuré (aucune dépendance, aucun abonnement) à lancer
                      manuellement sur la machine où tourne NinjaTrader 8.
                    </p>
                    <button
                      className="btn-secondary flex items-center gap-2 text-sm"
                      onClick={() => generateAgentTokenMutation.mutate()}
                      disabled={generateAgentTokenMutation.isPending}
                    >
                      <KeyRound className="h-4 w-4" />
                      {generateAgentTokenMutation.isPending ? 'Génération...' : 'Générer mon token & mon agent'}
                    </button>
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </div>

      {/* ── Dashboard de santé du connecteur ─────────────────────────── */}
      {agentStatus?.linked && (
        <div className="card space-y-4 border-2 border-gray-200 dark:border-gray-700">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <Activity className="h-5 w-5" /> Santé du connecteur NT8
          </h2>

          {healthError ? (
            <div className="flex items-start gap-2 text-sm text-red-700 dark:text-red-400 bg-red-50 dark:bg-red-900/20 rounded-lg p-3">
              <AlertTriangle className="h-4 w-4 flex-shrink-0 mt-0.5" />
              <p>Impossible de récupérer l'état de santé du connecteur.</p>
            </div>
          ) : healthData ? (
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {/* Maillon 1 : Backend */}
              <div className={`rounded-lg p-3 border ${healthData.backend.ok ? 'border-green-400 bg-green-50 dark:bg-green-900/20' : 'border-red-400 bg-red-50 dark:bg-red-900/20'}`}>
                <div className="flex items-center gap-2 mb-1">
                  <Server className={`h-4 w-4 ${healthData.backend.ok ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`} />
                  <span className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">Backend</span>
                </div>
                <p className={`text-sm font-medium ${healthData.backend.ok ? 'text-green-700 dark:text-green-300' : 'text-red-700 dark:text-red-300'}`}>
                  {healthData.backend.message}
                </p>
              </div>

              {/* Maillon 2 : Agent Windows */}
              <div className={`rounded-lg p-3 border ${healthData.agent.ok ? 'border-green-400 bg-green-50 dark:bg-green-900/20' : healthData.agent.linked ? 'border-yellow-400 bg-yellow-50 dark:bg-yellow-900/20' : 'border-red-400 bg-red-50 dark:bg-red-900/20'}`}>
                <div className="flex items-center gap-2 mb-1">
                  <Wifi className={`h-4 w-4 ${healthData.agent.ok ? 'text-green-600 dark:text-green-400' : healthData.agent.linked ? 'text-yellow-600 dark:text-yellow-400' : 'text-red-600 dark:text-red-400'}`} />
                  <span className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">Agent</span>
                </div>
                <p className={`text-sm font-medium ${healthData.agent.ok ? 'text-green-700 dark:text-green-300' : healthData.agent.linked ? 'text-yellow-700 dark:text-yellow-300' : 'text-red-700 dark:text-red-300'}`}>
                  {healthData.agent.message}
                </p>
                {healthData.agent.last_heartbeat_age_sec !== null && (
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                    Dernier heartbeat : {healthData.agent.last_heartbeat_age_sec}s
                  </p>
                )}
              </div>

              {/* Maillon 3 : NinjaTrader 8 */}
              <div className={`rounded-lg p-3 border ${healthData.nt8.ok ? 'border-green-400 bg-green-50 dark:bg-green-900/20' : healthData.agent.connected ? 'border-yellow-400 bg-yellow-50 dark:bg-yellow-900/20' : 'border-gray-300 dark:border-gray-600 bg-gray-50 dark:bg-gray-800/50'}`}>
                <div className="flex items-center gap-2 mb-1">
                  <Monitor className={`h-4 w-4 ${healthData.nt8.ok ? 'text-green-600 dark:text-green-400' : healthData.agent.connected ? 'text-yellow-600 dark:text-yellow-400' : 'text-gray-400'}`} />
                  <span className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">NinjaTrader 8</span>
                </div>
                <p className={`text-sm font-medium ${healthData.nt8.ok ? 'text-green-700 dark:text-green-300' : healthData.agent.connected ? 'text-yellow-700 dark:text-yellow-300' : 'text-gray-500 dark:text-gray-400'}`}>
                  {healthData.nt8.message}
                </p>
                {healthData.nt8.ok && (
                  <div className="text-xs text-gray-500 dark:text-gray-400 mt-1 space-y-0.5">
                    {healthData.nt8.selected_account && <p>Compte : {healthData.nt8.selected_account}</p>}
                    {healthData.nt8.balance != null && <p>Solde : {healthData.nt8.balance.toLocaleString('fr-FR', { maximumFractionDigits: 2 })} $</p>}
                    {healthData.nt8.daily_pnl != null && <p>PnL jour : {healthData.nt8.daily_pnl.toLocaleString('fr-FR', { maximumFractionDigits: 2 })} $</p>}
                    {healthData.nt8.trading_blocked && <p className="text-red-600 dark:text-red-400 font-medium">⛔ Trading bloqué</p>}
                    {healthData.nt8.position_open && <p className="text-blue-600 dark:text-blue-400">📊 Position ouverte</p>}
                  </div>
                )}
              </div>
            </div>
          ) : (
            <p className="text-sm text-gray-500 dark:text-gray-400">Chargement de l'état du connecteur...</p>
          )}

          {/* Files d'attente backend */}
          {healthData && (healthData.queues.signal_queue > 0 || healthData.queues.command_queue > 0) && (
            <div className="flex items-start gap-2 text-sm text-yellow-700 dark:text-yellow-400 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg p-3">
              <Package className="h-4 w-4 flex-shrink-0 mt-0.5" />
              <p>
                File d'attente backend : {healthData.queues.signal_queue} signal(s) et {healthData.queues.command_queue} commande(s) en attente.
                {!healthData.agent.connected && ' L\'agent semble déconnecté — les signaux seront exécutés dès sa reconnexion.'}
              </p>
            </div>
          )}
        </div>
      )}

      {agentStatus?.linked && (
        <div className="card space-y-4 border-2 border-blue-200 dark:border-blue-900">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <Landmark className="h-5 w-5" /> Comptes & connexions NinjaTrader
          </h2>

          <div className="flex items-start gap-2 text-sm text-blue-700 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/20 rounded-lg p-3">
            <Info className="h-4 w-4 flex-shrink-0 mt-0.5" />
            <div>
              <p className="font-medium mb-1">Pilotage à distance multi-comptes</p>
              <p>
                Sélectionnez le compte actif sur lequel les signaux Telegram seront exécutés,
                et connectez / déconnectez vos connexions (Rithmic, Tradovate, Sim...) directement
                depuis cette page — sans toucher à NinjaTrader 8. Pratique pour les prop firms
                (FTMO le matin, TopStep l'après-midi).
              </p>
              <p className="mt-1 text-xs">
                ⚠️ Nécessite que l'<strong>Add-On TelegramTraderAddOn</strong> soit compilé et
                ouvert dans NinjaTrader 8 (menu New → TelegramTrader Manager).
              </p>
            </div>
          </div>

          {accountsLoading ? (
            <p className="text-sm text-gray-500 dark:text-gray-400">Chargement...</p>
          ) : accountsError ? (
            <div className="flex items-start gap-2 text-sm text-red-700 dark:text-red-400 bg-red-50 dark:bg-red-900/20 rounded-lg p-3">
              <AlertTriangle className="h-4 w-4 flex-shrink-0 mt-0.5" />
              <p>
                Erreur lors de la récupération des comptes NinjaTrader. Vérifiez que le
                backend est accessible et que l'agent est bien connecté.
              </p>
            </div>
          ) : !accountsStatus ? (
            <div className="flex items-start gap-2 text-sm text-yellow-700 dark:text-yellow-400 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg p-3">
              <Info className="h-4 w-4 flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-medium">En attente des données NinjaTrader...</p>
                <p className="text-xs mt-1">
                  L'Add-On TelegramTraderAddOn doit être ouvert dans NinjaTrader 8
                  (menu New → TelegramTrader Manager) pour que les comptes et connexions
                  soient visibles ici.
                </p>
              </div>
            </div>
          ) : (
            <div className="space-y-5">

              {/* ── Compte actif (résumé en haut) ────────────────────── */}
              {accountsStatus.selected_account && (
                <div className="flex items-center gap-3 rounded-lg p-3 bg-green-50 dark:bg-green-900/20 border border-green-400 dark:border-green-700 text-sm">
                  <CheckCircle2 className="h-5 w-5 text-green-600 dark:text-green-400 flex-shrink-0" />
                  <div>
                    <p className="font-semibold text-green-800 dark:text-green-300">
                      Compte actif : {accountsStatus.selected_account}
                    </p>
                    <p className="text-xs text-green-700 dark:text-green-400">
                      Les signaux Telegram seront exécutés sur ce compte.
                    </p>
                  </div>
                </div>
              )}

              {/* ── Liste des comptes ────────────────────────────────── */}
              <div>
                <h3 className="text-sm font-semibold mb-2 flex items-center gap-2">
                  <Landmark className="h-4 w-4" />
                  Comptes disponibles ({accountsStatus.accounts?.length ?? 0})
                </h3>
                {!accountsStatus.accounts || accountsStatus.accounts.length === 0 ? (
                  <p className="text-xs text-gray-500 dark:text-gray-400">Aucun compte détecté dans NinjaTrader.</p>
                ) : (
                  <div className="space-y-2">
                    {accountsStatus.accounts.map((acc) => {
                      const isSelected = acc.name === accountsStatus.selected_account
                      return (
                        <div
                          key={acc.name}
                          className={`flex items-center justify-between gap-3 rounded-lg p-3 text-sm border transition-colors ${
                            isSelected
                              ? 'border-green-400 bg-green-50 dark:bg-green-900/20 dark:border-green-700'
                              : 'border-gray-200 dark:border-gray-700 hover:border-blue-300 dark:hover:border-blue-700'
                          }`}
                        >
                          <div className="flex items-center gap-2 min-w-0">
                            {isSelected
                              ? <CheckCircle2 className="h-4 w-4 text-green-600 dark:text-green-400 flex-shrink-0" />
                              : <Landmark className="h-4 w-4 text-gray-400 flex-shrink-0" />
                            }
                            <div className="min-w-0">
                              <p className="font-medium truncate">{acc.name}</p>
                              <p className="text-xs text-gray-500 dark:text-gray-400">
                                Solde : <span className="font-mono">{acc.balance != null ? acc.balance.toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '—'} $</span>
                              </p>
                            </div>
                          </div>
                          <div className="flex items-center gap-2 flex-shrink-0">
                            {isSelected ? (
                              <span className="text-xs font-semibold text-green-700 dark:text-green-400 bg-green-100 dark:bg-green-900/40 px-2 py-1 rounded-full">
                                ✓ Actif
                              </span>
                            ) : (
                              <button
                                className="btn-primary text-xs px-3 py-1.5"
                                onClick={() => selectAccountMutation.mutate(acc.name)}
                                disabled={selectAccountMutation.isPending}
                                title={`Activer le compte ${acc.name} pour l'exécution des signaux`}
                              >
                                {selectAccountMutation.isPending ? '...' : 'Activer'}
                              </button>
                            )}
                          </div>
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>

              {/* ── Liste des connexions ─────────────────────────────── */}
              <div>
                <h3 className="text-sm font-semibold mb-2 flex items-center gap-2">
                  <Plug className="h-4 w-4" />
                  Connexions ({accountsStatus.connections?.length ?? 0})
                </h3>
                {!accountsStatus.connections || accountsStatus.connections.length === 0 ? (
                  <p className="text-xs text-gray-500 dark:text-gray-400">Aucune connexion détectée dans NinjaTrader.</p>
                ) : (
                  <div className="space-y-2">
                    {accountsStatus.connections.map((conn) => (
                      <div
                        key={conn.name}
                        className={`flex items-center justify-between gap-3 rounded-lg p-3 text-sm border transition-colors ${
                          conn.connected
                            ? 'border-green-400 bg-green-50 dark:bg-green-900/20 dark:border-green-700'
                            : 'border-gray-200 dark:border-gray-700'
                        }`}
                      >
                        <div className="flex items-center gap-2 min-w-0">
                          {conn.connected ? (
                            <PlugZap className="h-4 w-4 text-green-600 dark:text-green-400 flex-shrink-0" />
                          ) : (
                            <Plug className="h-4 w-4 text-gray-400 flex-shrink-0" />
                          )}
                          <div className="min-w-0">
                            <p className="font-medium truncate">{conn.name}</p>
                            <p className="text-xs text-gray-500 dark:text-gray-400">{conn.status}</p>
                          </div>
                        </div>
                        <button
                          className={`text-xs px-3 py-1.5 flex-shrink-0 ${conn.connected ? 'btn-danger' : 'btn-primary'}`}
                          onClick={() =>
                            toggleConnectionMutation.mutate({ name: conn.name, connect: !conn.connected })
                          }
                          disabled={toggleConnectionMutation.isPending}
                          title={conn.connected ? `Déconnecter ${conn.name}` : `Connecter ${conn.name}`}
                        >
                          {toggleConnectionMutation.isPending ? '...' : conn.connected ? 'Déconnecter' : 'Connecter'}
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {accountsStatus.timestamp && (
                <p className="text-xs text-gray-400 dark:text-gray-500 flex items-center gap-1">
                  <Clock className="h-3 w-3" />
                  Dernière mise à jour : {new Date(accountsStatus.timestamp).toLocaleTimeString('fr-FR')}
                  {' '}· Rafraîchissement automatique toutes les 5s
                </p>
              )}
            </div>
          )}
        </div>
      )}

      <div className="card space-y-2">
        <h2 className="text-lg font-semibold">À propos</h2>

        <p className="text-sm text-gray-500 dark:text-gray-400">TelegramTrader v1.0.0</p>
        <p className="text-sm text-gray-500 dark:text-gray-400">
          Migration React + FastAPI depuis l'application Streamlit d'origine.
        </p>
        <p className="text-xs text-gray-400 dark:text-gray-500">
          Intégration CrossTrade / Tradovate temporairement masquée — focus actuel sur
          l'agent local NinjaTrader 8. Reviendra dans une prochaine mise à jour.
        </p>
      </div>
    </div>
  )
}

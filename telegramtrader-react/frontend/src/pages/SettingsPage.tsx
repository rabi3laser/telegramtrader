import { useState, useEffect } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import {
  Info, Download, KeyRound, Wifi, WifiOff, Copy, Clock, ChevronDown, ChevronUp,
  FileCode, Unlink, Landmark, Plug, PlugZap, CheckCircle2, Activity, Server,
  Monitor, AlertTriangle, Package, ShieldOff, ShieldCheck, History, TrendingUp,
  TrendingDown, AlertCircle, Radio,
} from 'lucide-react'

import { nt8AgentService } from '../services/nt8AgentService'
import type { ConnectorHealth, KillSwitchState, ActionLogEntry } from '../services/nt8AgentService'
import { useAuthStore } from '../store/authStore'
import { useConnectorWS } from '../hooks/useConnectorWS'


// ── Composant Modal de confirmation générique ──────────────────────────────
interface ConfirmModalProps {
  open: boolean
  title: string
  message: string
  confirmLabel: string
  confirmClass?: string
  onConfirm: () => void
  onCancel: () => void
}

function ConfirmModal({ open, title, message, confirmLabel, confirmClass = 'btn-danger', onConfirm, onCancel }: ConfirmModalProps) {
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="bg-white dark:bg-gray-900 rounded-xl shadow-2xl p-6 max-w-md w-full mx-4 border border-gray-200 dark:border-gray-700">
        <div className="flex items-start gap-3 mb-4">
          <AlertCircle className="h-6 w-6 text-orange-500 flex-shrink-0 mt-0.5" />
          <div>
            <h3 className="text-base font-semibold">{title}</h3>
            <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">{message}</p>
          </div>
        </div>
        <div className="flex gap-3 justify-end">
          <button className="btn-secondary text-sm px-4 py-2" onClick={onCancel}>
            Annuler
          </button>
          <button className={`${confirmClass} text-sm px-4 py-2`} onClick={onConfirm}>
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}


// ── Libellés lisibles pour les actions du log ──────────────────────────────
function actionLabel(action: string, details: Record<string, any>): string {
  switch (action) {
    case 'select_account':
      return `Compte activé : ${details.account_name ?? '?'}`
    case 'connect_connection':
      return `Connexion établie : ${details.connection_name ?? '?'}`
    case 'disconnect_connection':
      return `Connexion coupée : ${details.connection_name ?? '?'}`
    case 'kill_switch_on':
      return `⛔ Trading suspendu${details.reason ? ` — ${details.reason}` : ''}`
    case 'kill_switch_off':
      return `✅ Trading réactivé`
    default:
      return action
  }
}

function actionColor(action: string): string {
  if (action === 'kill_switch_on') return 'text-red-600 dark:text-red-400'
  if (action === 'kill_switch_off') return 'text-green-600 dark:text-green-400'
  if (action === 'disconnect_connection') return 'text-orange-600 dark:text-orange-400'
  if (action === 'connect_connection') return 'text-blue-600 dark:text-blue-400'
  return 'text-gray-700 dark:text-gray-300'
}


export default function SettingsPage() {
  const { user } = useAuthStore()
  const queryClient = useQueryClient()

  // ── AGENT LOCAL NINJATRADER 8 ──────────────────────────────────────────
  const [agentAccountName, setAgentAccountName] = useState('')
  const [pairingCode, setPairingCode] = useState<string | null>(null)
  const [pairingExpiresAt, setPairingExpiresAt] = useState<number | null>(null)
  const [pairingCountdown, setPairingCountdown] = useState<string>('')
  const [showAdvanced, setShowAdvanced] = useState(false)

  // ── MODALS DE CONFIRMATION ─────────────────────────────────────────────
  const [confirmModal, setConfirmModal] = useState<{
    open: boolean
    title: string
    message: string
    confirmLabel: string
    confirmClass?: string
    onConfirm: () => void
  }>({ open: false, title: '', message: '', confirmLabel: '', onConfirm: () => {} })

  const openConfirm = (opts: Omit<typeof confirmModal, 'open'>) =>
    setConfirmModal({ ...opts, open: true })
  const closeConfirm = () =>
    setConfirmModal(prev => ({ ...prev, open: false }))

  // ── QUERY : statut de l'agent (polling léger, nécessaire pour savoir si lié) ──
  const { data: agentStatus, isLoading: agentLoading, isError: agentError } = useQuery({
    queryKey: ['nt8-agent', 'status'],
    queryFn: nt8AgentService.getStatus,
    refetchInterval: 5000,
    retry: 2,
  })

  // ── WEBSOCKET temps réel (remplace les 4 useQuery de polling) ──────────
  const ws = useConnectorWS(!!agentStatus?.linked)

  // Aliases pour compatibilité avec le JSX existant
  const healthData: ConnectorHealth | null = ws.health
  const healthError = !ws.wsConnected && ws.error !== null && ws.health === null
  const accountsLoading = !ws.wsConnected && ws.accounts === null && ws.error === null
  const accountsError = !ws.wsConnected && ws.error !== null && ws.accounts === null
  const accountsStatus = ws.accounts?.accounts_status ?? null
  const killSwitchData: KillSwitchState | null = ws.killSwitch
  const actionLogData = ws.actionLog.length > 0
    ? { entries: ws.actionLog, count: ws.actionLog.length }
    : null

  // ── EFFETS ─────────────────────────────────────────────────────────────
  useEffect(() => {
    if (agentStatus?.connected && pairingCode) {
      setPairingCode(null)
      toast.success('Agent connecté avec succès ✅')
    }
  }, [agentStatus?.connected])

  useEffect(() => {
    if (!pairingExpiresAt) { setPairingCountdown(''); return }
    const interval = setInterval(() => {
      const remaining = Math.max(0, Math.floor(pairingExpiresAt - Date.now() / 1000))
      if (remaining <= 0) {
        setPairingCode(null); setPairingExpiresAt(null); setPairingCountdown('')
        clearInterval(interval)
      } else {
        const m = Math.floor(remaining / 60)
        const s = remaining % 60
        setPairingCountdown(`${m}:${s.toString().padStart(2, '0')}`)
      }
    }, 1000)
    return () => clearInterval(interval)
  }, [pairingExpiresAt])

  // ── MUTATIONS ──────────────────────────────────────────────────────────
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

  const selectAccountMutation = useMutation({
    mutationFn: (accountName: string) => nt8AgentService.selectAccount(accountName),
    onSuccess: (_data, accountName) => {
      toast.success(`Commande envoyée : sélection du compte ${accountName}`)
      // Le WebSocket recevra automatiquement la mise à jour dans ~3s
    },
    onError: () => toast.error("Erreur lors de l'envoi de la commande de sélection de compte"),
  })

  const toggleConnectionMutation = useMutation({
    mutationFn: ({ name, connect }: { name: string; connect: boolean }) =>
      nt8AgentService.toggleConnection(name, connect),
    onSuccess: (_data, vars) => {
      toast.success(`Commande envoyée : ${vars.connect ? 'connexion' : 'déconnexion'} de ${vars.name}`)
      // Le WebSocket recevra automatiquement la mise à jour dans ~3s
    },
    onError: () => toast.error("Erreur lors de l'envoi de la commande de connexion"),
  })

  const killSwitchMutation = useMutation({
    mutationFn: ({ active, reason }: { active: boolean; reason?: string }) =>
      nt8AgentService.setKillSwitch(active, reason),
    onSuccess: (_data, vars) => {
      if (vars.active) {
        toast.error('⛔ Trading suspendu — aucun signal ne sera exécuté')
      } else {
        toast.success('✅ Trading réactivé — les signaux seront à nouveau exécutés')
      }
      // Le WebSocket recevra automatiquement la mise à jour dans ~3s
    },
    onError: () => toast.error("Erreur lors du changement d'état du kill switch"),
  })

  // ── HANDLERS ───────────────────────────────────────────────────────────
  const handleDownloadScript = async () => {
    try {
      await nt8AgentService.downloadScript()
      toast.success('Script téléchargé ! Lancez-le sur la machine où tourne NinjaTrader 8.')
    } catch { toast.error('Erreur lors du téléchargement du script') }
  }

  const handleDownloadExe = async () => {
    try {
      await nt8AgentService.downloadExe()
      toast.success("Téléchargement lancé ! Double-cliquez sur TelegramTraderAgent.exe une fois terminé.")
    } catch { toast.error("L'exécutable n'est pas encore disponible sur ce serveur — utilisez le script Python en attendant.") }
  }

  const handleDownloadStrategy = async () => {
    try {
      await nt8AgentService.downloadStrategy()
      toast.success("Stratégie téléchargée ! Copiez-la dans Documents\\NinjaTrader 8\\bin\\Custom\\Strategies\\ puis compilez (F5).")
    } catch { toast.error("Erreur lors du téléchargement de la stratégie NinjaTrader.") }
  }

  const handleCopyCode = () => {
    if (pairingCode) { navigator.clipboard.writeText(pairingCode); toast.success('Code copié !') }
  }

  // Handlers avec confirmation
  const handleSelectAccount = (accountName: string) => {
    openConfirm({
      title: `Activer le compte ${accountName} ?`,
      message: `Les prochains signaux Telegram seront exécutés sur le compte "${accountName}". Cette action prend effet dans les 5 secondes.`,
      confirmLabel: 'Activer ce compte',
      confirmClass: 'btn-primary',
      onConfirm: () => { closeConfirm(); selectAccountMutation.mutate(accountName) },
    })
  }

  const handleToggleConnection = (name: string, connect: boolean) => {
    openConfirm({
      title: connect ? `Connecter ${name} ?` : `Déconnecter ${name} ?`,
      message: connect
        ? `La connexion "${name}" sera établie dans NinjaTrader 8. Les ordres pourront être passés sur cette connexion.`
        : `La connexion "${name}" sera coupée dans NinjaTrader 8. Les ordres en cours sur cette connexion pourraient être affectés.`,
      confirmLabel: connect ? 'Connecter' : 'Déconnecter',
      confirmClass: connect ? 'btn-primary' : 'btn-danger',
      onConfirm: () => { closeConfirm(); toggleConnectionMutation.mutate({ name, connect }) },
    })
  }

  const handleKillSwitch = (activate: boolean) => {
    if (activate) {
      openConfirm({
        title: '⛔ Suspendre le trading ?',
        message: "Aucun nouveau signal Telegram ne sera exécuté sur NinjaTrader 8 tant que le trading est suspendu. L'agent et NinjaTrader restent connectés. Réactivation manuelle obligatoire.",
        confirmLabel: 'Suspendre le trading',
        confirmClass: 'btn-danger',
        onConfirm: () => { closeConfirm(); killSwitchMutation.mutate({ active: true }) },
      })
    } else {
      openConfirm({
        title: '✅ Réactiver le trading ?',
        message: 'Les signaux Telegram seront à nouveau exécutés automatiquement sur NinjaTrader 8.',
        confirmLabel: 'Réactiver',
        confirmClass: 'btn-primary',
        onConfirm: () => { closeConfirm(); killSwitchMutation.mutate({ active: false }) },
      })
    }
  }

  const isKillSwitchActive = killSwitchData?.active === true

  return (
    <div className="space-y-6">
      {/* Modal de confirmation global */}
      <ConfirmModal
        open={confirmModal.open}
        title={confirmModal.title}
        message={confirmModal.message}
        confirmLabel={confirmModal.confirmLabel}
        confirmClass={confirmModal.confirmClass}
        onConfirm={confirmModal.onConfirm}
        onCancel={closeConfirm}
      />

      {/* En-tête avec indicateur WebSocket */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Paramètres</h1>
          <p className="text-gray-500 dark:text-gray-400">Configuration de l'application</p>
        </div>
        {agentStatus?.linked && (
          <div className={`flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full border ${
            ws.wsConnected
              ? 'border-green-300 bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400'
              : ws.reconnectAttempts > 0
              ? 'border-yellow-300 bg-yellow-50 dark:bg-yellow-900/20 text-yellow-700 dark:text-yellow-400'
              : 'border-gray-300 bg-gray-50 dark:bg-gray-800 text-gray-500 dark:text-gray-400'
          }`}>
            <Radio className={`h-3 w-3 ${ws.wsConnected ? 'text-green-500' : 'text-yellow-500'}`} />
            {ws.wsConnected
              ? 'Temps réel'
              : ws.reconnectAttempts > 0
              ? `Reconnexion… (${ws.reconnectAttempts})`
              : 'Connexion…'
            }
          </div>
        )}
      </div>

      <div className="card space-y-3">
        <h2 className="text-lg font-semibold">Compte Telegram</h2>
        <div className="text-sm text-gray-600 dark:text-gray-400">
          <p>Nom : {user?.first_name} {user?.last_name}</p>
          <p>Téléphone : {user?.phone}</p>
          <p>Username : {user?.username ? `@${user.username}` : '-'}</p>
        </div>
      </div>

      {/* ── KILL SWITCH (visible dès que l'agent est lié) ─────────────────── */}
      {agentStatus?.linked && (
        <div className={`card border-2 ${isKillSwitchActive ? 'border-red-400 dark:border-red-700 bg-red-50 dark:bg-red-900/10' : 'border-gray-200 dark:border-gray-700'}`}>
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              {isKillSwitchActive
                ? <ShieldOff className="h-6 w-6 text-red-600 dark:text-red-400 flex-shrink-0" />
                : <ShieldCheck className="h-6 w-6 text-green-600 dark:text-green-400 flex-shrink-0" />
              }
              <div>
                <p className={`font-semibold ${isKillSwitchActive ? 'text-red-700 dark:text-red-300' : 'text-gray-800 dark:text-gray-200'}`}>
                  {isKillSwitchActive ? '⛔ Trading suspendu' : '✅ Trading actif'}
                </p>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  {isKillSwitchActive
                    ? `Suspendu${killSwitchData?.activated_at ? ` le ${new Date(killSwitchData.activated_at * 1000).toLocaleString('fr-FR')}` : ''}. Aucun signal ne sera exécuté.`
                    : 'Les signaux Telegram sont exécutés normalement sur NinjaTrader 8.'
                  }
                </p>
              </div>
            </div>
            <button
              className={`flex-shrink-0 text-sm px-4 py-2 ${isKillSwitchActive ? 'btn-primary' : 'btn-danger'}`}
              onClick={() => handleKillSwitch(!isKillSwitchActive)}
              disabled={killSwitchMutation.isPending}
            >
              {killSwitchMutation.isPending ? '...' : isKillSwitchActive ? 'Réactiver' : 'Suspendre'}
            </button>
          </div>
        </div>
      )}

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
            <strong>TelegramSignalStrategyV3</strong> requise).
          </p>
        </div>

        {agentError && (
          <div className="flex items-start gap-2 text-sm text-red-700 dark:text-red-400 bg-red-50 dark:bg-red-900/20 rounded-lg p-3">
            <AlertTriangle className="h-4 w-4 flex-shrink-0 mt-0.5" />
            <p>Impossible de récupérer le statut de l'agent. Vérifiez que le backend est accessible.</p>
          </div>
        )}

        {/* Statut de connexion */}
        {!agentError && agentStatus && (
          <div className={`flex items-center gap-2 text-sm rounded-lg p-3 ${
            agentStatus.connected
              ? 'bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400'
              : agentStatus.linked
              ? 'bg-yellow-50 dark:bg-yellow-900/20 text-yellow-700 dark:text-yellow-400'
              : 'bg-gray-50 dark:bg-gray-800 text-gray-600 dark:text-gray-400'
          }`}>
            {agentStatus.connected
              ? <Wifi className="h-4 w-4 flex-shrink-0" />
              : <WifiOff className="h-4 w-4 flex-shrink-0" />
            }
            <span>
              {agentStatus.connected
                ? `Agent connecté ✅${agentStatus.account_name ? ` — ${agentStatus.account_name}` : ''}`
                : agentStatus.linked
                ? "Agent lié mais inactif (lancez TelegramTraderAgent.exe sur votre PC)"
                : "Aucun agent lié — générez un code d'appairage ci-dessous"
              }
            </span>
          </div>
        )}

        {/* Boutons de téléchargement */}
        <div className="flex flex-wrap gap-2">
          <button className="btn-primary flex items-center gap-2 text-sm" onClick={handleDownloadExe}>
            <Download className="h-4 w-4" /> Télécharger TelegramTraderAgent.exe
          </button>
          <button className="btn-secondary flex items-center gap-2 text-sm" onClick={handleDownloadStrategy}>
            <FileCode className="h-4 w-4" /> Stratégie NinjaScript V3
          </button>
        </div>

        {/* Code d'appairage */}
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <input
              type="text"
              className="input flex-1 text-sm"
              placeholder="Nom du compte (optionnel)"
              value={agentAccountName}
              onChange={(e) => setAgentAccountName(e.target.value)}
            />
            <button
              className="btn-primary text-sm whitespace-nowrap"
              onClick={() => generatePairingCodeMutation.mutate()}
              disabled={generatePairingCodeMutation.isPending}
            >
              {generatePairingCodeMutation.isPending ? '...' : 'Générer un code'}
            </button>
          </div>

          {pairingCode && (
            <div className="flex items-center gap-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg p-3 border border-blue-300 dark:border-blue-700">
              <div className="flex-1">
                <p className="text-xs text-blue-600 dark:text-blue-400 mb-1">Code d'appairage (expire dans {pairingCountdown})</p>
                <p className="text-2xl font-mono font-bold tracking-widest text-blue-800 dark:text-blue-200">{pairingCode}</p>
              </div>
              <button className="btn-secondary text-xs flex items-center gap-1" onClick={handleCopyCode}>
                <Copy className="h-3 w-3" /> Copier
              </button>
            </div>
          )}
        </div>

        {/* Section avancée */}
        <button
          className="flex items-center gap-1 text-xs text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200"
          onClick={() => setShowAdvanced(!showAdvanced)}
        >
          {showAdvanced ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
          Options avancées (token brut / script Python)
        </button>

        {showAdvanced && (
          <div className="space-y-2 border-t border-gray-200 dark:border-gray-700 pt-3">
            <div className="flex flex-wrap gap-2">
              <button className="btn-secondary flex items-center gap-2 text-xs" onClick={handleDownloadScript}>
                <Download className="h-3 w-3" /> Script Python (avancé)
              </button>
              <button
                className="btn-secondary flex items-center gap-2 text-xs"
                onClick={() => generateAgentTokenMutation.mutate()}
                disabled={generateAgentTokenMutation.isPending}
              >
                <KeyRound className="h-3 w-3" /> Régénérer le token
              </button>
              {agentStatus?.linked && (
                <button
                  className="btn-danger flex items-center gap-2 text-xs"
                  onClick={() => openConfirm({
                    title: "Révoquer l'agent ?",
                    message: "L'agent sera déconnecté et son token invalidé. Vous devrez générer un nouveau code d'appairage pour le reconnecter.",
                    confirmLabel: 'Révoquer',
                    onConfirm: () => { closeConfirm(); revokeAgentMutation.mutate() },
                  })}
                  disabled={revokeAgentMutation.isPending}
                >
                  <Unlink className="h-3 w-3" /> Révoquer l'agent
                </button>
              )}
            </div>
            {agentStatus?.token_masked && (
              <p className="text-xs text-gray-400 dark:text-gray-500 font-mono">Token : {agentStatus.token_masked}</p>
            )}
          </div>
        )}
      </div>

      {/* ── DASHBOARD DE SANTÉ ─────────────────────────────────────────────── */}
      {agentStatus?.linked && (
        <div className="card space-y-4">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <Activity className="h-5 w-5" /> État du connecteur
          </h2>

          {healthError ? (
            <div className="flex items-start gap-2 text-sm text-red-700 dark:text-red-400 bg-red-50 dark:bg-red-900/20 rounded-lg p-3">
              <AlertTriangle className="h-4 w-4 flex-shrink-0 mt-0.5" />
              <p>Impossible de récupérer l'état de santé du connecteur.</p>
            </div>
          ) : healthData ? (
            <>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                {/* Backend */}
                <div className={`rounded-lg p-3 border ${healthData.backend.ok ? 'border-green-400 bg-green-50 dark:bg-green-900/20' : 'border-red-400 bg-red-50 dark:bg-red-900/20'}`}>
                  <div className="flex items-center gap-2 mb-1">
                    <Server className={`h-4 w-4 ${healthData.backend.ok ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`} />
                    <span className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">Backend</span>
                  </div>
                  <p className={`text-sm font-medium ${healthData.backend.ok ? 'text-green-700 dark:text-green-300' : 'text-red-700 dark:text-red-300'}`}>
                    {healthData.backend.message}
                  </p>
                </div>

                {/* Agent */}
                <div className={`rounded-lg p-3 border ${healthData.agent.ok ? 'border-green-400 bg-green-50 dark:bg-green-900/20' : healthData.agent.linked ? 'border-yellow-400 bg-yellow-50 dark:bg-yellow-900/20' : 'border-red-400 bg-red-50 dark:bg-red-900/20'}`}>
                  <div className="flex items-center gap-2 mb-1">
                    <Wifi className={`h-4 w-4 ${healthData.agent.ok ? 'text-green-600 dark:text-green-400' : healthData.agent.linked ? 'text-yellow-600 dark:text-yellow-400' : 'text-red-600 dark:text-red-400'}`} />
                    <span className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">Agent</span>
                  </div>
                  <p className={`text-sm font-medium ${healthData.agent.ok ? 'text-green-700 dark:text-green-300' : healthData.agent.linked ? 'text-yellow-700 dark:text-yellow-300' : 'text-red-700 dark:text-red-300'}`}>
                    {healthData.agent.message}
                  </p>
                  {healthData.agent.last_heartbeat_age_sec !== null && (
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">Dernier heartbeat : {healthData.agent.last_heartbeat_age_sec}s</p>
                  )}
                </div>

                {/* NinjaTrader 8 */}
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
                      {healthData.nt8.daily_pnl != null && (
                        <p className={healthData.nt8.daily_pnl >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}>
                          PnL jour : {healthData.nt8.daily_pnl >= 0 ? '+' : ''}{healthData.nt8.daily_pnl.toLocaleString('fr-FR', { maximumFractionDigits: 2 })} $
                        </p>
                      )}
                      {healthData.nt8.trading_blocked && <p className="text-red-600 dark:text-red-400 font-medium">⛔ Trading bloqué</p>}
                      {healthData.nt8.position_open && <p className="text-blue-600 dark:text-blue-400">📊 Position ouverte</p>}
                    </div>
                  )}
                </div>
              </div>

              {/* Widget P&L temps réel */}
              {healthData.nt8.ok && healthData.nt8.daily_pnl != null && (
                <div className={`flex items-center gap-3 rounded-lg p-3 border text-sm ${
                  healthData.nt8.daily_pnl >= 0
                    ? 'border-green-300 bg-green-50 dark:bg-green-900/20 dark:border-green-700'
                    : 'border-red-300 bg-red-50 dark:bg-red-900/20 dark:border-red-700'
                }`}>
                  {healthData.nt8.daily_pnl >= 0
                    ? <TrendingUp className="h-5 w-5 text-green-600 dark:text-green-400 flex-shrink-0" />
                    : <TrendingDown className="h-5 w-5 text-red-600 dark:text-red-400 flex-shrink-0" />
                  }
                  <div>
                    <p className={`font-semibold ${healthData.nt8.daily_pnl >= 0 ? 'text-green-800 dark:text-green-300' : 'text-red-800 dark:text-red-300'}`}>
                      P&L journalier : {healthData.nt8.daily_pnl >= 0 ? '+' : ''}{healthData.nt8.daily_pnl.toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} $
                    </p>
                    {healthData.nt8.balance != null && (
                      <p className="text-xs text-gray-500 dark:text-gray-400">
                        Solde du compte : {healthData.nt8.balance.toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} $
                        {healthData.nt8.position_open && ' · Position ouverte'}
                      </p>
                    )}
                  </div>
                </div>
              )}

              {/* Files d'attente */}
              {(healthData.queues.signal_queue > 0 || healthData.queues.command_queue > 0) && (
                <div className="flex items-start gap-2 text-sm text-yellow-700 dark:text-yellow-400 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg p-3">
                  <Package className="h-4 w-4 flex-shrink-0 mt-0.5" />
                  <p>
                    File d'attente backend : {healthData.queues.signal_queue} signal(s) et {healthData.queues.command_queue} commande(s) en attente.
                    {!healthData.agent.connected && " L'agent semble déconnecté — les signaux seront exécutés dès sa reconnexion."}
                  </p>
                </div>
              )}
            </>
          ) : (
            <p className="text-sm text-gray-500 dark:text-gray-400">Chargement de l'état du connecteur...</p>
          )}
        </div>
      )}

      {/* ── COMPTES & CONNEXIONS NINJATRADER ──────────────────────────────── */}
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
              <p>Erreur lors de la récupération des comptes NinjaTrader. Vérifiez que le backend est accessible et que l'agent est bien connecté.</p>
            </div>
          ) : !accountsStatus ? (
            <div className="flex items-start gap-2 text-sm text-yellow-700 dark:text-yellow-400 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg p-3">
              <Info className="h-4 w-4 flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-medium">En attente des données NinjaTrader...</p>
                <p className="text-xs mt-1">L'Add-On TelegramTraderAddOn doit être ouvert dans NinjaTrader 8 (menu New → TelegramTrader Manager) pour que les comptes et connexions soient visibles ici.</p>
              </div>
            </div>
          ) : (
            <div className="space-y-5">
              {/* Compte actif */}
              {accountsStatus.selected_account && (
                <div className="flex items-center gap-3 rounded-lg p-3 bg-green-50 dark:bg-green-900/20 border border-green-400 dark:border-green-700 text-sm">
                  <CheckCircle2 className="h-5 w-5 text-green-600 dark:text-green-400 flex-shrink-0" />
                  <div>
                    <p className="font-semibold text-green-800 dark:text-green-300">Compte actif : {accountsStatus.selected_account}</p>
                    <p className="text-xs text-green-700 dark:text-green-400">Les signaux Telegram seront exécutés sur ce compte.</p>
                  </div>
                </div>
              )}

              {/* Liste des comptes */}
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
                              <span className="text-xs font-semibold text-green-700 dark:text-green-400 bg-green-100 dark:bg-green-900/40 px-2 py-1 rounded-full">✓ Actif</span>
                            ) : (
                              <button
                                className="btn-primary text-xs px-3 py-1.5"
                                onClick={() => handleSelectAccount(acc.name)}
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

              {/* Liste des connexions */}
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
                          {conn.connected
                            ? <PlugZap className="h-4 w-4 text-green-600 dark:text-green-400 flex-shrink-0" />
                            : <Plug className="h-4 w-4 text-gray-400 flex-shrink-0" />
                          }
                          <div className="min-w-0">
                            <p className="font-medium truncate">{conn.name}</p>
                            <p className="text-xs text-gray-500 dark:text-gray-400">{conn.status}</p>
                          </div>
                        </div>
                        <button
                          className={`text-xs px-3 py-1.5 flex-shrink-0 ${conn.connected ? 'btn-danger' : 'btn-primary'}`}
                          onClick={() => handleToggleConnection(conn.name, !conn.connected)}
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

              {(accountsStatus.timestamp || ws.lastUpdate) && (
                <p className="text-xs text-gray-400 dark:text-gray-500 flex items-center gap-1">
                  <Clock className="h-3 w-3" />
                  Dernière mise à jour : {new Date(accountsStatus.timestamp ?? (ws.lastUpdate! * 1000)).toLocaleTimeString('fr-FR')}
                  {' '}· {ws.wsConnected ? 'Temps réel via WebSocket' : 'Rafraîchissement automatique'}
                </p>
              )}
            </div>
          )}
        </div>
      )}

      {/* ── HISTORIQUE DES ACTIONS ─────────────────────────────────────────── */}
      {agentStatus?.linked && actionLogData && actionLogData.count > 0 && (
        <div className="card space-y-3">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <History className="h-5 w-5" /> Historique des actions
          </h2>
          <div className="space-y-1">
            {actionLogData.entries.map((entry: ActionLogEntry, i: number) => (
              <div key={i} className="flex items-start gap-3 text-sm py-1.5 border-b border-gray-100 dark:border-gray-800 last:border-0">
                <span className="text-xs text-gray-400 dark:text-gray-500 whitespace-nowrap mt-0.5 w-32 flex-shrink-0">
                  {new Date(entry.timestamp * 1000).toLocaleString('fr-FR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}
                </span>
                <span className={`flex-1 ${actionColor(entry.action)}`}>
                  {actionLabel(entry.action, entry.details)}
                </span>
              </div>
            ))}
          </div>
          <p className="text-xs text-gray-400 dark:text-gray-500">
            Les 15 dernières actions · {ws.wsConnected ? 'Mis à jour en temps réel via WebSocket' : 'Rafraîchissement automatique'}
          </p>
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

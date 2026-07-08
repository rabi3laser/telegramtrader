import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { Send, Zap, Info, History, Target, Percent, AlertCircle, CheckCircle2, Landmark } from 'lucide-react'
import { nt8AgentService } from '../services/nt8AgentService'
import { useConnectorWS } from '../hooks/useConnectorWS'
import { useAuthStore } from '../store/authStore'
import { tradingService } from '../services/tradingService'
import { MARKETS, type MarketType, type SignalType, type OrderExecutionType, type Signal } from '../types'

type SizingMode = 'quantity' | 'risk'

// Marchés NT8 connus (fallback si NT8 ne remonte pas la liste)
const NT8_MARKETS_FALLBACK: Record<string, { name: string; icon: string; instrument: string }> = {
  gold_mgc:   { name: 'Gold (MGC)',      icon: '🥇', instrument: 'MGC' },
  mnq_nasdaq: { name: 'Nasdaq (MNQ)',    icon: '📊', instrument: 'MNQ' },
  mcl_crude:  { name: 'Crude Oil (MCL)', icon: '🛢️', instrument: 'MCL' },
  mes_sp500:  { name: 'S&P 500 (MES)',   icon: '📈', instrument: 'MES' },
  es_sp500:   { name: 'S&P 500 (ES)',    icon: '📈', instrument: 'ES' },
  nq_nasdaq:  { name: 'Nasdaq (NQ)',     icon: '📊', instrument: 'NQ' },
  gc_gold:    { name: 'Gold (GC)',       icon: '🥇', instrument: 'GC' },
  cl_crude:   { name: 'Crude Oil (CL)',  icon: '🛢️', instrument: 'CL' },
  custom:     { name: 'Personnalisé',    icon: '🔍', instrument: '' },
}

export default function TradingPage() {
  const queryClient = useQueryClient()
  const { isAuthenticated } = useAuthStore()

  const [signalForm, setSignalForm] = useState({
    type: 'BUY' as SignalType,
    market: 'gold_mgc' as string,
    instrument: '',   // instrument NT8 libre (ex: "MGC", "MNQ", "AAPL"...)
    order_type: 'MARKET' as OrderExecutionType,
    entry_price: '',
    target_price: '',
    target_price_2: '',
    stop_loss: '',
    quantity: '1',
    risk_pct: '1',
  })
  const [sizingMode, setSizingMode] = useState<SizingMode>('quantity')
  const [showConfirm, setShowConfirm] = useState(false)

  // ── Statut agent (pour savoir si lié) ─────────────────────────────────
  const { data: agentStatus } = useQuery({
    queryKey: ['nt8-agent', 'status'],
    queryFn: nt8AgentService.getStatus,
    refetchInterval: 5000,
    retry: 2,
  })

  // ── WebSocket temps réel (comptes, instruments disponibles) ───────────
  const ws = useConnectorWS(!!agentStatus?.linked)

  // Compte actif depuis le WebSocket
  const activeAccount = ws.accounts?.accounts_status?.selected_account ?? null

  // Liste des instruments disponibles depuis NT8 (via heartbeat)
  // Format attendu dans last_accounts : { instruments: ["MGC", "MNQ", "MCL", ...] }
  const nt8Instruments: string[] = ws.accounts?.accounts_status?.instruments ?? []

  // Historique des trades
  const { data: history, isLoading: historyLoading, isError: historyError } = useQuery({
    queryKey: ['trading', 'history'],
    queryFn: () => tradingService.getTradeHistory(50),
    retry: 2,
  })

  const { data: positions, isError: positionsError } = useQuery({
    queryKey: ['trading', 'positions'],
    queryFn: tradingService.getPositions,
    retry: 2,
  })

  // ── Mutation d'exécution — utilise directement l'agent NT8 ────────────
  const executeMutation = useMutation({
    mutationFn: () => {
      // Déterminer l'instrument NT8 à utiliser
      // Priorité : instrument libre saisi > instrument du marché sélectionné
      const instrumentName = signalForm.instrument.trim()
        || NT8_MARKETS_FALLBACK[signalForm.market]?.instrument
        || signalForm.market

      const signal = {
        id: `manual-${Date.now()}`,
        type: signalForm.type,
        entry_price: parseFloat(signalForm.entry_price) || 0,
        target_price: signalForm.target_price ? parseFloat(signalForm.target_price) : undefined,
        target_price_2: signalForm.target_price_2 ? parseFloat(signalForm.target_price_2) : undefined,
        stop_loss: signalForm.stop_loss ? parseFloat(signalForm.stop_loss) : undefined,
        market: instrumentName,  // on envoie le nom d'instrument NT8 directement
        source_channel: 'manuel',
        date: new Date().toISOString(),
        order_type: signalForm.order_type,
        quantity: sizingMode === 'quantity' ? parseInt(signalForm.quantity, 10) || 1 : undefined,
        risk_pct: sizingMode === 'risk' ? parseFloat(signalForm.risk_pct) || undefined : undefined,
      }

      // Si l'agent NT8 est lié → pousser directement via nt8AgentService
      // (évite le passage par CrossTrade qui génère une erreur 400)
      if (agentStatus?.linked) {
        return nt8AgentService.pushSignal(signal)
      }

      // Fallback : route trading classique (CrossTrade)
      return tradingService.executeSignal(signal as Signal, 'nt8')
    },
    onSuccess: (res: any) => {
      if (res.success !== false) {
        toast.success(res.message || 'Signal envoyé à NinjaTrader 8 ✅')
        queryClient.invalidateQueries({ queryKey: ['trading', 'history'] })
      } else {
        toast.error(res.message || res.error || "Échec de l'exécution")
      }
    },
    onError: () => toast.error("Erreur lors de l'exécution du signal"),
  })

  const handleExecute = (e: React.FormEvent) => {
    e.preventDefault()
    if (signalForm.order_type !== 'MARKET' && !signalForm.entry_price) {
      toast.error("Veuillez saisir un prix d'entrée pour un ordre limite")
      return
    }
    // SL obligatoire : l'Add-On NT8 rejette tout signal sans Stop Loss (raison : sl_manquant)
    if (!signalForm.stop_loss || parseFloat(signalForm.stop_loss) <= 0) {
      toast.error('⛔ Stop Loss obligatoire — NinjaTrader rejette les signaux sans SL')
      return
    }
    if (sizingMode === 'risk' && (!signalForm.risk_pct || parseFloat(signalForm.risk_pct) <= 0)) {
      toast.error('Veuillez saisir un pourcentage de risque valide')
      return
    }
    setShowConfirm(true)
  }

  const handleConfirmExecute = () => {
    setShowConfirm(false)
    executeMutation.mutate()
  }

  // Nom d'affichage du marché sélectionné
  const marketDisplay = NT8_MARKETS_FALLBACK[signalForm.market]
  const displayName = signalForm.instrument.trim()
    ? signalForm.instrument.trim()
    : (marketDisplay?.name ?? signalForm.market)

  return (
    <div className="space-y-6">

      {/* ── Modal de confirmation avant exécution d'ordre ─────────────────── */}
      {showConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
          <div className="bg-white dark:bg-gray-900 rounded-xl shadow-2xl p-6 max-w-md w-full mx-4 border border-gray-200 dark:border-gray-700">
            <div className="flex items-start gap-3 mb-4">
              <AlertCircle className="h-6 w-6 text-orange-500 flex-shrink-0 mt-0.5" />
              <div>
                <h3 className="text-base font-semibold">Confirmer l'exécution du signal</h3>
                <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                  Vous êtes sur le point d'envoyer un ordre réel à NinjaTrader 8.
                </p>
              </div>
            </div>
            {/* Résumé du signal */}
            <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-3 mb-4 text-sm space-y-1">
              {activeAccount && (
                <div className="flex justify-between border-b border-gray-200 dark:border-gray-700 pb-1 mb-1">
                  <span className="text-gray-500 dark:text-gray-400">Compte</span>
                  <span className="font-semibold text-green-700 dark:text-green-400">{activeAccount}</span>
                </div>
              )}
              <div className="flex justify-between">
                <span className="text-gray-500 dark:text-gray-400">Direction</span>
                <span className={`font-semibold ${signalForm.type === 'BUY' ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                  {signalForm.type}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500 dark:text-gray-400">Instrument</span>
                <span className="font-medium">{marketDisplay?.icon ?? '🔍'} {displayName}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500 dark:text-gray-400">Type d'ordre</span>
                <span className="font-medium">{signalForm.order_type}</span>
              </div>
              {signalForm.entry_price && (
                <div className="flex justify-between">
                  <span className="text-gray-500 dark:text-gray-400">Prix d'entrée</span>
                  <span className="font-mono">{signalForm.entry_price}</span>
                </div>
              )}
              {signalForm.stop_loss && (
                <div className="flex justify-between">
                  <span className="text-gray-500 dark:text-gray-400">Stop Loss</span>
                  <span className="font-mono text-red-600 dark:text-red-400">{signalForm.stop_loss}</span>
                </div>
              )}
              {signalForm.target_price && (
                <div className="flex justify-between">
                  <span className="text-gray-500 dark:text-gray-400">TP1</span>
                  <span className="font-mono text-green-600 dark:text-green-400">{signalForm.target_price}</span>
                </div>
              )}
              <div className="flex justify-between border-t border-gray-200 dark:border-gray-700 pt-1 mt-1">
                <span className="text-gray-500 dark:text-gray-400">
                  {sizingMode === 'quantity' ? 'Quantité' : 'Risque'}
                </span>
                <span className="font-semibold">
                  {sizingMode === 'quantity' ? `${signalForm.quantity} contrat(s)` : `${signalForm.risk_pct}% du capital`}
                </span>
              </div>
            </div>
            <div className="flex gap-3 justify-end">
              <button className="btn-secondary text-sm px-4 py-2" onClick={() => setShowConfirm(false)}>
                Annuler
              </button>
              <button className="btn-primary text-sm px-4 py-2 flex items-center gap-2" onClick={handleConfirmExecute}>
                <Send className="h-4 w-4" /> Confirmer l'envoi
              </button>
            </div>
          </div>
        </div>
      )}

      <div>
        <h1 className="text-2xl font-bold">Trading</h1>
        <p className="text-gray-500 dark:text-gray-400">
          Exécution des signaux sur NinjaTrader 8 (agent local gratuit)
        </p>
      </div>

      {/* ── Compte actif (affiché si agent connecté) ──────────────────────── */}
      {agentStatus?.linked && activeAccount && (
        <div className="flex items-center gap-3 rounded-lg p-3 bg-green-50 dark:bg-green-900/20 border border-green-400 dark:border-green-700 text-sm">
          <CheckCircle2 className="h-5 w-5 text-green-600 dark:text-green-400 flex-shrink-0" />
          <div>
            <p className="font-semibold text-green-800 dark:text-green-300">
              Compte actif : {activeAccount}
            </p>
            <p className="text-xs text-green-700 dark:text-green-400">
              Les signaux seront exécutés sur ce compte. Pour changer de compte, allez dans <strong>Paramètres</strong>.
            </p>
          </div>
        </div>
      )}

      {/* ── Avertissement si agent non lié ────────────────────────────────── */}
      {!agentStatus?.linked && (
        <div className="flex items-start gap-2 text-sm text-yellow-700 dark:text-yellow-400 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg p-3">
          <Info className="h-4 w-4 flex-shrink-0 mt-0.5" />
          <p>
            Aucun agent NT8 lié. Allez dans <strong>Paramètres</strong> pour configurer votre agent local NinjaTrader 8.
            Sans agent, les ordres passeront par CrossTrade (si configuré).
          </p>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <form onSubmit={handleExecute} className="card space-y-4">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <Zap className="h-5 w-5" /> Exécuter un signal manuel
          </h2>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium mb-1">Direction</label>
              <select
                className="input"
                value={signalForm.type}
                onChange={(e) => setSignalForm({ ...signalForm, type: e.target.value as SignalType })}
              >
                <option value="BUY">BUY ↑</option>
                <option value="SELL">SELL ↓</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Marché</label>
              <select
                className="input"
                value={signalForm.market}
                onChange={(e) => {
                  const key = e.target.value
                  setSignalForm({
                    ...signalForm,
                    market: key,
                    // Pré-remplir l'instrument si connu, vider si custom
                    instrument: key === 'custom' ? '' : (NT8_MARKETS_FALLBACK[key]?.instrument ?? ''),
                  })
                }}
              >
                {Object.entries(NT8_MARKETS_FALLBACK)
                  .filter(([key]) => key !== 'custom')
                  .map(([key, m]) => (
                    <option key={key} value={key}>
                      {m.icon} {m.name}
                    </option>
                  ))}
                <option value="custom">🔍 Autre instrument…</option>
              </select>
            </div>
          </div>

          {/* ── Instrument NT8 libre ─────────────────────────────────────── */}
          <div>
            <label className="block text-sm font-medium mb-1">
              Instrument NinjaTrader
              {nt8Instruments.length > 0 && (
                <span className="text-xs text-gray-400 dark:text-gray-500 ml-2">
                  (instruments détectés sur votre compte)
                </span>
              )}
            </label>
            {nt8Instruments.length > 0 ? (
              <select
                className="input"
                value={signalForm.instrument || NT8_MARKETS_FALLBACK[signalForm.market]?.instrument || ''}
                onChange={(e) => setSignalForm({ ...signalForm, instrument: e.target.value })}
              >
                {nt8Instruments.map((inst) => (
                  <option key={inst} value={inst}>{inst}</option>
                ))}
              </select>
            ) : (
              <input
                type="text"
                className="input"
                placeholder={NT8_MARKETS_FALLBACK[signalForm.market]?.instrument || 'Ex: MGC, MNQ, MCL, ES, NQ...'}
                value={signalForm.instrument}
                onChange={(e) => setSignalForm({ ...signalForm, instrument: e.target.value })}
              />
            )}
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
              {nt8Instruments.length > 0
                ? `${nt8Instruments.length} instrument(s) disponible(s) sur le compte ${activeAccount ?? ''}`
                : "Laissez vide pour utiliser l'instrument par défaut du marché sélectionné. L'agent NT8 doit être connecté pour voir la liste automatiquement."
              }
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">Type d'ordre</label>
            <select
              className="input"
              value={signalForm.order_type}
              onChange={(e) => setSignalForm({ ...signalForm, order_type: e.target.value as OrderExecutionType })}
            >
              <option value="MARKET">Marché (exécution immédiate)</option>
              <option value="LIMIT">Limite (au prix indiqué)</option>
              <option value="LIMIT_THEN_MARKET">Limite puis Marché (si non touché)</option>
            </select>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
              Remplace temporairement le mode par défaut configuré dans la stratégie NinjaScript.
            </p>
          </div>

          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium mb-1">
                Prix d'entrée {signalForm.order_type === 'MARKET' ? '(optionnel)' : ''}
              </label>
              <input
                type="number"
                step="0.01"
                className="input"
                value={signalForm.entry_price}
                onChange={(e) => setSignalForm({ ...signalForm, entry_price: e.target.value })}
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">TP1 (optionnel)</label>
              <input
                type="number"
                step="0.01"
                className="input"
                value={signalForm.target_price}
                onChange={(e) => setSignalForm({ ...signalForm, target_price: e.target.value })}
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">TP2 (optionnel)</label>
              <input
                type="number"
                step="0.01"
                className="input"
                value={signalForm.target_price_2}
                onChange={(e) => setSignalForm({ ...signalForm, target_price_2: e.target.value })}
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">
              Stop Loss <span className="text-red-500">*</span>
              <span className="text-xs font-normal text-gray-400 dark:text-gray-500 ml-1">(obligatoire)</span>
            </label>
            <input
              type="number"
              step="0.01"
              className={`input w-40 ${!signalForm.stop_loss ? 'border-orange-300 dark:border-orange-700' : ''}`}
              placeholder="Ex: 3280.5"
              value={signalForm.stop_loss}
              onChange={(e) => setSignalForm({ ...signalForm, stop_loss: e.target.value })}
            />
            <p className="text-xs text-orange-600 dark:text-orange-400 mt-1">
              NinjaTrader rejette les signaux sans SL — requis pour le calcul du risque et la protection du compte.
            </p>
          </div>

          <div className="border-t border-gray-200 dark:border-gray-700 pt-4">
            <label className="block text-sm font-medium mb-2">Dimensionnement de la position</label>
            <div className="flex gap-2 mb-3">
              <button
                type="button"
                className={sizingMode === 'quantity' ? 'btn-primary text-sm px-3 py-1.5' : 'btn-secondary text-sm px-3 py-1.5'}
                onClick={() => setSizingMode('quantity')}
              >
                <Target className="h-3.5 w-3.5 inline mr-1" />
                Quantité fixe
              </button>
              <button
                type="button"
                className={sizingMode === 'risk' ? 'btn-primary text-sm px-3 py-1.5' : 'btn-secondary text-sm px-3 py-1.5'}
                onClick={() => setSizingMode('risk')}
              >
                <Percent className="h-3.5 w-3.5 inline mr-1" />
                Risque % du capital
              </button>
            </div>

            {sizingMode === 'quantity' ? (
              <div>
                <label className="block text-sm font-medium mb-1">Quantité (contrats)</label>
                <input
                  type="number"
                  className="input w-32"
                  value={signalForm.quantity}
                  onChange={(e) => setSignalForm({ ...signalForm, quantity: e.target.value })}
                />
              </div>
            ) : (
              <div>
                <label className="block text-sm font-medium mb-1">Risque (% du capital du compte)</label>
                <input
                  type="number"
                  step="0.1"
                  className="input w-32"
                  value={signalForm.risk_pct}
                  onChange={(e) => setSignalForm({ ...signalForm, risk_pct: e.target.value })}
                />
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  La stratégie NinjaScript calcule automatiquement le nombre de contrats en
                  fonction de ce risque et de la distance au Stop Loss.
                </p>
              </div>
            )}
          </div>

          <button type="submit" className="btn-primary w-full flex items-center justify-center gap-2" disabled={executeMutation.isPending}>
            <Send className="h-4 w-4" />
            {executeMutation.isPending ? 'Envoi en cours...' : 'Exécuter le signal sur NinjaTrader 8'}
          </button>
        </form>

        <div className="card space-y-4">
          <h2 className="text-lg font-semibold">Positions actives</h2>
          {positionsError ? (
            <div className="flex items-start gap-2 text-sm text-red-700 dark:text-red-400 bg-red-50 dark:bg-red-900/20 rounded-lg p-3">
              <Info className="h-4 w-4 flex-shrink-0 mt-0.5" />
              <p>
                Impossible de récupérer les positions. Vérifiez que le backend est accessible.
              </p>
            </div>
          ) : (
            <div className="flex items-start gap-2 text-sm text-blue-700 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/20 rounded-lg p-3">
              <Info className="h-4 w-4 flex-shrink-0 mt-0.5" />
              <p>
                L'agent local NinjaTrader 8 exécute les ordres directement dans la plateforme.
                Consultez NinjaTrader 8 pour l'état réel de vos positions et de votre compte.
              </p>
            </div>
          )}
          {!positionsError && positions && positions.length > 0 && (
            <div className="space-y-2">
              {positions.map((p) => (
                <div key={p.id} className="flex justify-between text-sm border-b border-gray-100 dark:border-gray-800 pb-2">
                  <span>{p.market} · {p.type}</span>
                  <span>{p.quantity} @ {p.entry_price}</span>
                </div>
              ))}
            </div>
          )}

          {/* ── Comptes disponibles (depuis WebSocket) ──────────────────── */}
          {agentStatus?.linked && ws.accounts?.accounts_status?.accounts && ws.accounts.accounts_status.accounts.length > 0 && (
            <div className="border-t border-gray-200 dark:border-gray-700 pt-3">
              <h3 className="text-sm font-semibold mb-2 flex items-center gap-2">
                <Landmark className="h-4 w-4" /> Comptes NinjaTrader
              </h3>
              <div className="space-y-1.5">
                {ws.accounts.accounts_status.accounts.map((acc) => {
                  const isActive = acc.name === activeAccount
                  return (
                    <div key={acc.name} className={`flex items-center justify-between text-xs rounded-lg px-3 py-2 border ${
                      isActive
                        ? 'border-green-400 bg-green-50 dark:bg-green-900/20 dark:border-green-700'
                        : 'border-gray-200 dark:border-gray-700'
                    }`}>
                      <div className="flex items-center gap-2">
                        {isActive && <CheckCircle2 className="h-3.5 w-3.5 text-green-600 dark:text-green-400" />}
                        <span className={isActive ? 'font-semibold text-green-800 dark:text-green-300' : 'text-gray-700 dark:text-gray-300'}>
                          {acc.name}
                        </span>
                        {isActive && <span className="text-green-600 dark:text-green-400 text-xs">(actif)</span>}
                      </div>
                      {acc.balance != null && (
                        <span className="font-mono text-gray-500 dark:text-gray-400">
                          {acc.balance.toLocaleString('fr-FR', { minimumFractionDigits: 0, maximumFractionDigits: 0 })} $
                        </span>
                      )}
                    </div>
                  )
                })}
              </div>
              <p className="text-xs text-gray-400 dark:text-gray-500 mt-2">
                Pour changer de compte actif → <strong>Paramètres</strong>
              </p>
            </div>
          )}
        </div>
      </div>

      <div className="card">
        <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <History className="h-5 w-5" /> Historique des trades
        </h2>
        {historyLoading ? (
          <p className="text-sm text-gray-500 dark:text-gray-400">Chargement...</p>
        ) : historyError ? (
          <div className="flex items-start gap-2 text-sm text-red-700 dark:text-red-400 bg-red-50 dark:bg-red-900/20 rounded-lg p-3">
            <Info className="h-4 w-4 flex-shrink-0 mt-0.5" />
            <p>
              Impossible de charger l'historique des trades. Vérifiez que le backend est accessible.
            </p>
          </div>
        ) : !history || history.length === 0 ? (
          <p className="text-sm text-gray-500 dark:text-gray-400">Aucun trade exécuté pour le moment.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-700">
                  <th className="py-2 pr-4">Type</th>
                  <th className="py-2 pr-4">Instrument</th>
                  <th className="py-2 pr-4">Entrée</th>
                  <th className="py-2 pr-4">Quantité</th>
                  <th className="py-2 pr-4">Statut</th>
                  <th className="py-2 pr-4">Date</th>
                </tr>
              </thead>
              <tbody>
                {history.map((t: any, i: number) => (
                  <tr key={t.id ?? i} className="border-b border-gray-100 dark:border-gray-800">
                    <td className="py-2 pr-4">
                      <span className={t.type === 'BUY' ? 'badge-success' : 'badge-danger'}>{t.type}</span>
                    </td>
                    <td className="py-2 pr-4">
                      {MARKETS[t.market as keyof typeof MARKETS]?.icon ?? '🔍'} {t.market}
                    </td>
                    <td className="py-2 pr-4">{t.entry_price}</td>
                    <td className="py-2 pr-4">{t.quantity}</td>
                    <td className="py-2 pr-4">{t.status ?? '-'}</td>
                    <td className="py-2 pr-4 text-gray-500 dark:text-gray-400">
                      {t.date ? new Date(t.date).toLocaleString('fr-FR') : '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

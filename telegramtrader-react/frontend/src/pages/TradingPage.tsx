import { useState, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import {
  Send, Zap, Info, History, AlertCircle, CheckCircle2, Landmark,
  TrendingUp, TrendingDown, DollarSign, Percent, Calculator, Target,
  ChevronDown, ChevronUp, Activity,
} from 'lucide-react'
import { nt8AgentService } from '../services/nt8AgentService'
import { useConnectorWS } from '../hooks/useConnectorWS'
import { tradingService } from '../services/tradingService'
import { MARKETS, type SignalType, type OrderExecutionType, type Signal } from '../types'

// ── Types ──────────────────────────────────────────────────────────────────
type SizingMode = 'contracts' | 'risk_pct' | 'risk_dollar'

// ── Marchés NT8 connus (fallback si NT8 ne remonte pas la liste) ───────────
const NT8_MARKETS_FALLBACK: Record<string, { name: string; icon: string; instrument: string; tickSize: number; pointValue: number }> = {
  gold_mgc:   { name: 'Gold (MGC)',      icon: '🥇', instrument: 'MGC',  tickSize: 0.1,  pointValue: 10   },
  mnq_nasdaq: { name: 'Nasdaq (MNQ)',    icon: '📊', instrument: 'MNQ',  tickSize: 0.25, pointValue: 2    },
  mcl_crude:  { name: 'Crude Oil (MCL)', icon: '🛢️', instrument: 'MCL',  tickSize: 0.01, pointValue: 100  },
  mes_sp500:  { name: 'S&P 500 (MES)',   icon: '📈', instrument: 'MES',  tickSize: 0.25, pointValue: 5    },
  es_sp500:   { name: 'S&P 500 (ES)',    icon: '📈', instrument: 'ES',   tickSize: 0.25, pointValue: 50   },
  nq_nasdaq:  { name: 'Nasdaq (NQ)',     icon: '📊', instrument: 'NQ',   tickSize: 0.25, pointValue: 20   },
  gc_gold:    { name: 'Gold (GC)',       icon: '🥇', instrument: 'GC',   tickSize: 0.1,  pointValue: 100  },
  cl_crude:   { name: 'Crude Oil (CL)',  icon: '🛢️', instrument: 'CL',   tickSize: 0.01, pointValue: 1000 },
  custom:     { name: 'Personnalisé',    icon: '🔍', instrument: '',     tickSize: 0,    pointValue: 0    },
}

// ── Calcul MM ──────────────────────────────────────────────────────────────
function calcContracts(
  sizingMode: SizingMode,
  contracts: number,
  riskPct: number,
  riskDollar: number,
  balance: number,
  entry: number,
  sl: number,
  pointValue: number,
): { qty: number; riskPerContract: number; totalRisk: number } {
  const slDistance = Math.abs(entry - sl)
  const riskPerContract = slDistance * pointValue

  if (sizingMode === 'contracts') {
    return { qty: contracts, riskPerContract, totalRisk: contracts * riskPerContract }
  }

  let maxRisk = 0
  if (sizingMode === 'risk_pct' && balance > 0) {
    maxRisk = balance * riskPct / 100
  } else if (sizingMode === 'risk_dollar') {
    maxRisk = riskDollar
  }

  if (riskPerContract <= 0 || maxRisk <= 0) {
    return { qty: 1, riskPerContract, totalRisk: riskPerContract }
  }

  const qty = Math.max(1, Math.floor(maxRisk / riskPerContract))
  return { qty, riskPerContract, totalRisk: qty * riskPerContract }
}

export default function TradingPage() {
  const queryClient = useQueryClient()

  const [signalForm, setSignalForm] = useState({
    type: 'BUY' as SignalType,
    market: 'gold_mgc' as string,
    instrument: '',
    order_type: 'MARKET' as OrderExecutionType,
    entry_price: '',
    target_price: '',
    target_price_2: '',
    stop_loss: '',
    contracts: '1',
    risk_pct: '1',
    risk_dollar: '100',
  })
  const [sizingMode, setSizingMode] = useState<SizingMode>('contracts')
  const [showConfirm, setShowConfirm] = useState(false)
  const [showHistory, setShowHistory] = useState(false)

  // ── Agent + WebSocket ──────────────────────────────────────────────────
  const { data: agentStatus } = useQuery({
    queryKey: ['nt8-agent', 'status'],
    queryFn: nt8AgentService.getStatus,
    refetchInterval: 5000,
    retry: 2,
  })
  const ws = useConnectorWS(!!agentStatus?.linked)

  // ── Données du compte actif ────────────────────────────────────────────
  const accountsStatus = ws.accounts?.accounts_status
  const activeAccountName = accountsStatus?.selected_account ?? null
  const activeAccount = accountsStatus?.accounts?.find(a => a.name === activeAccountName) ?? null
  const balance = activeAccount?.balance ?? 0
  const dailyPnl = activeAccount?.daily_pnl ?? null
  const buyingPower = activeAccount?.buying_power ?? null
  const openPositions = activeAccount?.positions ?? []

  // ── Instruments depuis NT8 ─────────────────────────────────────────────
  const nt8Instruments: string[] = accountsStatus?.instruments ?? []
  const activeInstrument = accountsStatus?.active_instrument ?? null

  // ── Point value / tick size (NT8 > fallback) ───────────────────────────
  const fallbackMarket = NT8_MARKETS_FALLBACK[signalForm.market]
  const pointValue = activeInstrument?.point_value && activeInstrument.point_value > 0
    ? activeInstrument.point_value
    : (fallbackMarket?.pointValue ?? 0)
  const tickSize = activeInstrument?.tick_size && activeInstrument.tick_size > 0
    ? activeInstrument.tick_size
    : (fallbackMarket?.tickSize ?? 0)
  const lastPrice = activeInstrument?.last_price ?? 0

  // ── Calcul MM en temps réel ────────────────────────────────────────────
  const entry = parseFloat(signalForm.entry_price) || lastPrice || 0
  const sl = parseFloat(signalForm.stop_loss) || 0
  const tp = parseFloat(signalForm.target_price) || 0

  const mm = useMemo(() => calcContracts(
    sizingMode,
    parseInt(signalForm.contracts, 10) || 1,
    parseFloat(signalForm.risk_pct) || 1,
    parseFloat(signalForm.risk_dollar) || 100,
    balance,
    entry,
    sl,
    pointValue,
  ), [sizingMode, signalForm.contracts, signalForm.risk_pct, signalForm.risk_dollar, balance, entry, sl, pointValue])

  // R:R ratio
  const rrRatio = useMemo(() => {
    if (!entry || !sl || !tp) return null
    const risk = Math.abs(entry - sl)
    const reward = Math.abs(tp - entry)
    if (risk <= 0) return null
    return reward / risk
  }, [entry, sl, tp])

  // ── Historique ─────────────────────────────────────────────────────────
  const { data: history, isLoading: historyLoading } = useQuery({
    queryKey: ['trading', 'history'],
    queryFn: () => tradingService.getTradeHistory(50),
    retry: 2,
    enabled: showHistory,
  })

  // ── Mutation d'exécution ───────────────────────────────────────────────
  const executeMutation = useMutation({
    mutationFn: () => {
      const instrumentName = signalForm.instrument.trim()
        || fallbackMarket?.instrument
        || signalForm.market

      const signal = {
        id: `manual-${Date.now()}`,
        type: signalForm.type,
        entry_price: entry || 0,
        target_price: tp || undefined,
        target_price_2: signalForm.target_price_2 ? parseFloat(signalForm.target_price_2) : undefined,
        stop_loss: sl || undefined,
        market: instrumentName,
        source_channel: 'manuel',
        date: new Date().toISOString(),
        order_type: signalForm.order_type,
        quantity: mm.qty,
        risk_pct: sizingMode === 'risk_pct' ? parseFloat(signalForm.risk_pct) : undefined,
      }

      if (agentStatus?.linked) return nt8AgentService.pushSignal(signal)
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
    if (!signalForm.stop_loss || sl <= 0) {
      toast.error('⛔ Stop Loss obligatoire — NinjaTrader rejette les signaux sans SL')
      return
    }
    if (signalForm.type === 'BUY' && sl >= entry) {
      toast.error('⛔ SL invalide : pour un BUY, le SL doit être inférieur au prix d\'entrée')
      return
    }
    if (signalForm.type === 'SELL' && sl <= entry) {
      toast.error('⛔ SL invalide : pour un SELL, le SL doit être supérieur au prix d\'entrée')
      return
    }
    setShowConfirm(true)
  }

  const instrumentDisplay = signalForm.instrument.trim() || fallbackMarket?.instrument || signalForm.market

  return (
    <div className="space-y-4">

      {/* ── Modal de confirmation ──────────────────────────────────────────── */}
      {showConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
          <div className="bg-white dark:bg-gray-900 rounded-xl shadow-2xl p-6 max-w-md w-full mx-4 border border-gray-200 dark:border-gray-700">
            <div className="flex items-start gap-3 mb-4">
              <AlertCircle className="h-6 w-6 text-orange-500 flex-shrink-0 mt-0.5" />
              <div>
                <h3 className="text-base font-semibold">Confirmer l'exécution</h3>
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">Ordre réel sur NinjaTrader 8</p>
              </div>
            </div>
            <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-3 mb-4 text-sm space-y-1.5">
              {activeAccountName && (
                <div className="flex justify-between border-b border-gray-200 dark:border-gray-700 pb-1.5 mb-1.5">
                  <span className="text-gray-500">Compte</span>
                  <span className="font-semibold text-green-700 dark:text-green-400">{activeAccountName}</span>
                </div>
              )}
              <div className="flex justify-between">
                <span className="text-gray-500">Direction</span>
                <span className={`font-bold ${signalForm.type === 'BUY' ? 'text-green-600' : 'text-red-600'}`}>{signalForm.type}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Instrument</span>
                <span className="font-medium">{fallbackMarket?.icon ?? '🔍'} {instrumentDisplay}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Quantité</span>
                <span className="font-bold">{mm.qty} contrat{mm.qty > 1 ? 's' : ''}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Type d'ordre</span>
                <span>{signalForm.order_type}</span>
              </div>
              {entry > 0 && <div className="flex justify-between"><span className="text-gray-500">Entrée</span><span className="font-mono">{entry.toFixed(2)}</span></div>}
              <div className="flex justify-between"><span className="text-gray-500">Stop Loss</span><span className="font-mono text-red-600">{sl.toFixed(2)}</span></div>
              {tp > 0 && <div className="flex justify-between"><span className="text-gray-500">TP1</span><span className="font-mono text-green-600">{tp.toFixed(2)}</span></div>}
              <div className="flex justify-between border-t border-gray-200 dark:border-gray-700 pt-1.5 mt-1.5">
                <span className="text-gray-500">Risque estimé</span>
                <span className="font-bold text-red-600 dark:text-red-400">
                  {mm.totalRisk > 0 ? `${mm.totalRisk.toLocaleString('fr-FR', { maximumFractionDigits: 0 })} $` : '—'}
                </span>
              </div>
              {rrRatio && (
                <div className="flex justify-between">
                  <span className="text-gray-500">R:R</span>
                  <span className={`font-bold ${rrRatio >= 2 ? 'text-green-600' : rrRatio >= 1 ? 'text-yellow-600' : 'text-red-600'}`}>
                    1 : {rrRatio.toFixed(2)}
                  </span>
                </div>
              )}
            </div>
            <div className="flex gap-3 justify-end">
              <button className="btn-secondary text-sm px-4 py-2" onClick={() => setShowConfirm(false)}>Annuler</button>
              <button className="btn-primary text-sm px-4 py-2 flex items-center gap-2" onClick={() => { setShowConfirm(false); executeMutation.mutate() }}>
                <Send className="h-4 w-4" /> Confirmer l'envoi
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── En-tête ────────────────────────────────────────────────────────── */}
      <div>
        <h1 className="text-2xl font-bold">Trading</h1>
        <p className="text-gray-500 dark:text-gray-400 text-sm">Exécution des signaux sur NinjaTrader 8</p>
      </div>

      {/* ── Bandeau compte actif ───────────────────────────────────────────── */}
      {agentStatus?.linked && activeAccountName ? (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {/* Compte */}
          <div className="card py-3 px-4 flex items-center gap-3 col-span-2 sm:col-span-1">
            <CheckCircle2 className="h-5 w-5 text-green-500 flex-shrink-0" />
            <div className="min-w-0">
              <p className="text-xs text-gray-500 dark:text-gray-400">Compte actif</p>
              <p className="font-semibold text-sm truncate text-green-700 dark:text-green-400">{activeAccountName}</p>
            </div>
          </div>
          {/* Solde */}
          <div className="card py-3 px-4">
            <p className="text-xs text-gray-500 dark:text-gray-400 flex items-center gap-1"><DollarSign className="h-3 w-3" /> Solde</p>
            <p className="font-bold text-sm mt-0.5">{balance > 0 ? balance.toLocaleString('fr-FR', { maximumFractionDigits: 0 }) + ' $' : '—'}</p>
          </div>
          {/* PnL jour */}
          <div className="card py-3 px-4">
            <p className="text-xs text-gray-500 dark:text-gray-400 flex items-center gap-1">
              {dailyPnl !== null && dailyPnl >= 0 ? <TrendingUp className="h-3 w-3 text-green-500" /> : <TrendingDown className="h-3 w-3 text-red-500" />}
              PnL jour
            </p>
            <p className={`font-bold text-sm mt-0.5 ${dailyPnl === null ? '' : dailyPnl >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
              {dailyPnl !== null ? `${dailyPnl >= 0 ? '+' : ''}${dailyPnl.toLocaleString('fr-FR', { maximumFractionDigits: 0 })} $` : '—'}
            </p>
          </div>
          {/* Instrument actif */}
          <div className="card py-3 px-4">
            <p className="text-xs text-gray-500 dark:text-gray-400 flex items-center gap-1"><Activity className="h-3 w-3" /> Instrument</p>
            <p className="font-bold text-sm mt-0.5">{activeInstrument?.name || '—'}</p>
            {lastPrice > 0 && <p className="text-xs text-gray-400 font-mono">{lastPrice.toFixed(2)}</p>}
          </div>
        </div>
      ) : !agentStatus?.linked ? (
        <div className="flex items-start gap-2 text-sm text-yellow-700 dark:text-yellow-400 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg p-3">
          <Info className="h-4 w-4 flex-shrink-0 mt-0.5" />
          <p>Aucun agent NT8 lié. Allez dans <strong>Paramètres</strong> pour configurer votre agent local NinjaTrader 8.</p>
        </div>
      ) : null}

      {/* ── Positions ouvertes ─────────────────────────────────────────────── */}
      {openPositions.length > 0 && (
        <div className="card space-y-2">
          <h3 className="text-sm font-semibold flex items-center gap-2"><Target className="h-4 w-4 text-blue-500" /> Positions ouvertes</h3>
          {openPositions.map((pos, i) => (
            <div key={i} className={`flex items-center justify-between text-xs rounded-lg px-3 py-2 border ${pos.direction === 'Long' ? 'border-green-400 bg-green-50 dark:bg-green-900/20' : 'border-red-400 bg-red-50 dark:bg-red-900/20'}`}>
              <div className="flex items-center gap-2">
                <span className={`font-bold ${pos.direction === 'Long' ? 'text-green-700 dark:text-green-400' : 'text-red-700 dark:text-red-400'}`}>{pos.direction === 'Long' ? '▲' : '▼'} {pos.instrument}</span>
                <span className="text-gray-500">{pos.quantity} × {pos.avg_price.toFixed(2)}</span>
              </div>
              <span className={`font-bold ${pos.unrealized_pnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                {pos.unrealized_pnl >= 0 ? '+' : ''}{pos.unrealized_pnl.toLocaleString('fr-FR', { maximumFractionDigits: 0 })} $
              </span>
            </div>
          ))}
        </div>
      )}

      {/* ── Formulaire + MM ───────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">

        {/* Formulaire signal (3/5) */}
        <form onSubmit={handleExecute} className="card space-y-4 lg:col-span-3">
          <h2 className="text-base font-semibold flex items-center gap-2"><Zap className="h-4 w-4" /> Signal manuel</h2>

          {/* Direction + Marché */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium mb-1 text-gray-600 dark:text-gray-400">Direction</label>
              <div className="flex gap-2">
                <button type="button"
                  className={`flex-1 py-2 rounded-lg text-sm font-bold border-2 transition-colors ${signalForm.type === 'BUY' ? 'bg-green-600 border-green-600 text-white' : 'border-gray-300 dark:border-gray-600 text-gray-500 hover:border-green-400'}`}
                  onClick={() => setSignalForm({ ...signalForm, type: 'BUY' })}>
                  ▲ BUY
                </button>
                <button type="button"
                  className={`flex-1 py-2 rounded-lg text-sm font-bold border-2 transition-colors ${signalForm.type === 'SELL' ? 'bg-red-600 border-red-600 text-white' : 'border-gray-300 dark:border-gray-600 text-gray-500 hover:border-red-400'}`}
                  onClick={() => setSignalForm({ ...signalForm, type: 'SELL' })}>
                  ▼ SELL
                </button>
              </div>
            </div>
            <div>
              <label className="block text-xs font-medium mb-1 text-gray-600 dark:text-gray-400">Type d'ordre</label>
              <select className="input text-sm" value={signalForm.order_type}
                onChange={(e) => setSignalForm({ ...signalForm, order_type: e.target.value as OrderExecutionType })}>
                <option value="MARKET">Marché</option>
                <option value="LIMIT">Limite</option>
                <option value="LIMIT_THEN_MARKET">Limite → Marché</option>
              </select>
            </div>
          </div>

          {/* Instrument */}
          <div>
            <label className="block text-xs font-medium mb-1 text-gray-600 dark:text-gray-400">
              Instrument NinjaTrader
              {nt8Instruments.length > 0 && <span className="text-green-500 ml-1">✓ {nt8Instruments.length} depuis NT8</span>}
            </label>
            {nt8Instruments.length > 0 ? (
              <select className="input text-sm" value={signalForm.instrument || fallbackMarket?.instrument || ''}
                onChange={(e) => setSignalForm({ ...signalForm, instrument: e.target.value })}>
                {nt8Instruments.map(inst => <option key={inst} value={inst}>{inst}</option>)}
              </select>
            ) : (
              <div className="flex gap-2">
                <select className="input text-sm flex-1" value={signalForm.market}
                  onChange={(e) => {
                    const key = e.target.value
                    setSignalForm({ ...signalForm, market: key, instrument: key === 'custom' ? '' : (NT8_MARKETS_FALLBACK[key]?.instrument ?? '') })
                  }}>
                  {Object.entries(NT8_MARKETS_FALLBACK).filter(([k]) => k !== 'custom').map(([key, m]) => (
                    <option key={key} value={key}>{m.icon} {m.name}</option>
                  ))}
                  <option value="custom">🔍 Autre…</option>
                </select>
                {signalForm.market === 'custom' && (
                  <input type="text" className="input text-sm w-32" placeholder="Ex: MGC" value={signalForm.instrument}
                    onChange={(e) => setSignalForm({ ...signalForm, instrument: e.target.value })} />
                )}
              </div>
            )}
          </div>

          {/* Prix */}
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="block text-xs font-medium mb-1 text-gray-600 dark:text-gray-400">
                Entrée {signalForm.order_type === 'MARKET' ? <span className="text-gray-400">(opt.)</span> : ''}
              </label>
              <input type="number" step="0.01" className="input text-sm"
                placeholder={lastPrice > 0 ? lastPrice.toFixed(2) : '0.00'}
                value={signalForm.entry_price}
                onChange={(e) => setSignalForm({ ...signalForm, entry_price: e.target.value })} />
            </div>
            <div>
              <label className="block text-xs font-medium mb-1 text-gray-600 dark:text-gray-400">
                Stop Loss <span className="text-red-500">*</span>
              </label>
              <input type="number" step="0.01"
                className={`input text-sm ${!signalForm.stop_loss ? 'border-orange-400 dark:border-orange-600' : ''}`}
                placeholder="Requis"
                value={signalForm.stop_loss}
                onChange={(e) => setSignalForm({ ...signalForm, stop_loss: e.target.value })} />
            </div>
            <div>
              <label className="block text-xs font-medium mb-1 text-gray-600 dark:text-gray-400">TP1 <span className="text-gray-400">(opt.)</span></label>
              <input type="number" step="0.01" className="input text-sm" value={signalForm.target_price}
                onChange={(e) => setSignalForm({ ...signalForm, target_price: e.target.value })} />
            </div>
          </div>

          {/* TP2 */}
          <div className="grid grid-cols-3 gap-3">
            <div className="col-start-3">
              <label className="block text-xs font-medium mb-1 text-gray-600 dark:text-gray-400">TP2 <span className="text-gray-400">(opt.)</span></label>
              <input type="number" step="0.01" className="input text-sm" value={signalForm.target_price_2}
                onChange={(e) => setSignalForm({ ...signalForm, target_price_2: e.target.value })} />
            </div>
          </div>

          <button type="submit" disabled={executeMutation.isPending}
            className={`w-full py-3 rounded-lg font-bold text-white flex items-center justify-center gap-2 transition-colors ${signalForm.type === 'BUY' ? 'bg-green-600 hover:bg-green-700' : 'bg-red-600 hover:bg-red-700'} disabled:opacity-50`}>
            <Send className="h-4 w-4" />
            {executeMutation.isPending ? 'Envoi...' : `${signalForm.type} ${mm.qty} contrat${mm.qty > 1 ? 's' : ''} — ${instrumentDisplay}`}
          </button>
        </form>

        {/* Money Management (2/5) */}
        <div className="card space-y-4 lg:col-span-2">
          <h2 className="text-base font-semibold flex items-center gap-2"><Calculator className="h-4 w-4" /> Money Management</h2>

          {/* Mode de sizing */}
          <div className="space-y-1">
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400">Mode de calcul</label>
            <div className="grid grid-cols-3 gap-1">
              {([
                { mode: 'contracts' as SizingMode, label: 'Contrats', icon: '📦' },
                { mode: 'risk_pct' as SizingMode, label: '% Capital', icon: '%' },
                { mode: 'risk_dollar' as SizingMode, label: 'Risque $', icon: '$' },
              ] as const).map(({ mode, label, icon }) => (
                <button key={mode} type="button"
                  className={`py-2 px-1 rounded-lg text-xs font-medium border-2 transition-colors ${sizingMode === mode ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300' : 'border-gray-200 dark:border-gray-700 text-gray-500 hover:border-blue-300'}`}
                  onClick={() => setSizingMode(mode)}>
                  {icon} {label}
                </button>
              ))}
            </div>
          </div>

          {/* Paramètre selon le mode */}
          {sizingMode === 'contracts' && (
            <div>
              <label className="block text-xs font-medium mb-1 text-gray-600 dark:text-gray-400">Nombre de contrats</label>
              <input type="number" min="1" className="input text-sm w-full" value={signalForm.contracts}
                onChange={(e) => setSignalForm({ ...signalForm, contracts: e.target.value })} />
            </div>
          )}
          {sizingMode === 'risk_pct' && (
            <div>
              <label className="block text-xs font-medium mb-1 text-gray-600 dark:text-gray-400">
                Risque (% du capital)
                {balance > 0 && <span className="text-gray-400 ml-1">= {(balance * (parseFloat(signalForm.risk_pct) || 0) / 100).toLocaleString('fr-FR', { maximumFractionDigits: 0 })} $</span>}
              </label>
              <div className="flex items-center gap-2">
                <input type="range" min="0.1" max="5" step="0.1" className="flex-1"
                  value={signalForm.risk_pct}
                  onChange={(e) => setSignalForm({ ...signalForm, risk_pct: e.target.value })} />
                <input type="number" step="0.1" min="0.1" max="10" className="input text-sm w-16"
                  value={signalForm.risk_pct}
                  onChange={(e) => setSignalForm({ ...signalForm, risk_pct: e.target.value })} />
                <span className="text-sm text-gray-500">%</span>
              </div>
              <div className="flex justify-between text-xs text-gray-400 mt-0.5">
                <span>0.1%</span><span>1%</span><span>2%</span><span>5%</span>
              </div>
            </div>
          )}
          {sizingMode === 'risk_dollar' && (
            <div>
              <label className="block text-xs font-medium mb-1 text-gray-600 dark:text-gray-400">
                Risque max ($)
                {balance > 0 && <span className="text-gray-400 ml-1">= {((parseFloat(signalForm.risk_dollar) || 0) / balance * 100).toFixed(2)}% du capital</span>}
              </label>
              <div className="flex items-center gap-2">
                <input type="number" step="10" min="10" className="input text-sm flex-1"
                  value={signalForm.risk_dollar}
                  onChange={(e) => setSignalForm({ ...signalForm, risk_dollar: e.target.value })} />
                <span className="text-sm text-gray-500">$</span>
              </div>
            </div>
          )}

          {/* Résultat MM */}
          <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-3 space-y-2">
            <div className="flex justify-between items-center">
              <span className="text-xs text-gray-500">Contrats calculés</span>
              <span className="text-2xl font-bold text-blue-600 dark:text-blue-400">{mm.qty}</span>
            </div>
            {mm.riskPerContract > 0 && (
              <div className="flex justify-between text-xs">
                <span className="text-gray-500">Risque / contrat</span>
                <span className="font-mono">{mm.riskPerContract.toLocaleString('fr-FR', { maximumFractionDigits: 0 })} $</span>
              </div>
            )}
            {mm.totalRisk > 0 && (
              <div className="flex justify-between text-xs">
                <span className="text-gray-500">Risque total</span>
                <span className={`font-bold ${balance > 0 && mm.totalRisk / balance > 0.03 ? 'text-red-600' : 'text-orange-600 dark:text-orange-400'}`}>
                  {mm.totalRisk.toLocaleString('fr-FR', { maximumFractionDigits: 0 })} $
                  {balance > 0 && <span className="font-normal text-gray-400 ml-1">({(mm.totalRisk / balance * 100).toFixed(2)}%)</span>}
                </span>
              </div>
            )}
            {rrRatio !== null && (
              <div className="flex justify-between text-xs border-t border-gray-200 dark:border-gray-700 pt-2 mt-1">
                <span className="text-gray-500">Ratio R:R</span>
                <span className={`font-bold ${rrRatio >= 2 ? 'text-green-600' : rrRatio >= 1 ? 'text-yellow-600' : 'text-red-600'}`}>
                  1 : {rrRatio.toFixed(2)}
                  {rrRatio >= 2 ? ' ✅' : rrRatio >= 1 ? ' ⚠️' : ' ❌'}
                </span>
              </div>
            )}
            {mm.totalRisk > 0 && tp > 0 && rrRatio !== null && (
              <div className="flex justify-between text-xs">
                <span className="text-gray-500">Gain potentiel</span>
                <span className="font-bold text-green-600 dark:text-green-400">
                  +{(mm.totalRisk * rrRatio).toLocaleString('fr-FR', { maximumFractionDigits: 0 })} $
                </span>
              </div>
            )}
          </div>

          {/* Infos instrument */}
          {(pointValue > 0 || tickSize > 0) && (
            <div className="text-xs text-gray-400 dark:text-gray-500 space-y-0.5 border-t border-gray-200 dark:border-gray-700 pt-2">
              <p className="font-medium text-gray-500 dark:text-gray-400">Spécifications {instrumentDisplay}</p>
              {tickSize > 0 && <p>Tick size : {tickSize}</p>}
              {pointValue > 0 && <p>Point value : {pointValue} $ / point</p>}
              {lastPrice > 0 && <p>Dernier prix : {lastPrice.toFixed(2)}</p>}
              {nt8Instruments.length === 0 && <p className="text-orange-400">⚠️ Valeurs estimées — connectez NT8 pour les valeurs réelles</p>}
            </div>
          )}

          {/* Comptes disponibles */}
          {agentStatus?.linked && accountsStatus?.accounts && accountsStatus.accounts.length > 1 && (
            <div className="border-t border-gray-200 dark:border-gray-700 pt-3 space-y-1.5">
              <p className="text-xs font-medium text-gray-500 dark:text-gray-400 flex items-center gap-1"><Landmark className="h-3 w-3" /> Comptes</p>
              {accountsStatus.accounts.map(acc => {
                const isActive = acc.name === activeAccountName
                return (
                  <div key={acc.name} className={`flex items-center justify-between text-xs rounded px-2 py-1.5 ${isActive ? 'bg-green-50 dark:bg-green-900/20 text-green-800 dark:text-green-300 font-semibold' : 'text-gray-600 dark:text-gray-400'}`}>
                    <span>{isActive ? '✓ ' : ''}{acc.name}</span>
                    {acc.balance != null && <span className="font-mono">{acc.balance.toLocaleString('fr-FR', { maximumFractionDigits: 0 })} $</span>}
                  </div>
                )
              })}
              <p className="text-xs text-gray-400">Changer de compte → <strong>Paramètres</strong></p>
            </div>
          )}
        </div>
      </div>

      {/* ── Historique ─────────────────────────────────────────────────────── */}
      <div className="card">
        <button className="flex items-center justify-between w-full" onClick={() => setShowHistory(!showHistory)}>
          <h2 className="text-base font-semibold flex items-center gap-2">
            <History className="h-4 w-4" /> Historique des trades
          </h2>
          {showHistory ? <ChevronUp className="h-4 w-4 text-gray-400" /> : <ChevronDown className="h-4 w-4 text-gray-400" />}
        </button>
        {showHistory && (
          <div className="mt-4">
            {historyLoading ? (
              <p className="text-sm text-gray-500">Chargement...</p>
            ) : !history || history.length === 0 ? (
              <p className="text-sm text-gray-500">Aucun trade exécuté pour le moment.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs text-gray-500 border-b border-gray-200 dark:border-gray-700">
                      <th className="py-2 pr-3">Type</th>
                      <th className="py-2 pr-3">Instrument</th>
                      <th className="py-2 pr-3">Entrée</th>
                      <th className="py-2 pr-3">Qté</th>
                      <th className="py-2 pr-3">Statut</th>
                      <th className="py-2">Date</th>
                    </tr>
                  </thead>
                  <tbody>
                    {history.map((t: any, i: number) => (
                      <tr key={t.id ?? i} className="border-b border-gray-100 dark:border-gray-800 text-xs">
                        <td className="py-2 pr-3">
                          <span className={t.type === 'BUY' ? 'badge-success' : 'badge-danger'}>{t.type}</span>
                        </td>
                        <td className="py-2 pr-3">{MARKETS[t.market as keyof typeof MARKETS]?.icon ?? '🔍'} {t.market}</td>
                        <td className="py-2 pr-3 font-mono">{t.entry_price}</td>
                        <td className="py-2 pr-3">{t.quantity}</td>
                        <td className="py-2 pr-3">{t.status ?? '-'}</td>
                        <td className="py-2 text-gray-400">{t.date ? new Date(t.date).toLocaleString('fr-FR') : '-'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

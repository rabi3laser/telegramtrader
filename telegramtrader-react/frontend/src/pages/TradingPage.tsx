import { useState, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import {
  Send, Zap, Info, History, AlertCircle, CheckCircle2, Landmark,
  TrendingUp, TrendingDown, DollarSign, Calculator, Target,
  ChevronDown, ChevronUp, Activity, Plug, PlugZap, RefreshCw,
} from 'lucide-react'
import { nt8AgentService } from '../services/nt8AgentService'
import { useConnectorWS } from '../hooks/useConnectorWS'
import { tradingService } from '../services/tradingService'
import { MARKETS, type SignalType, type OrderExecutionType, type Signal } from '../types'

// ── Types ──────────────────────────────────────────────────────────────────
type SizingMode = 'contracts' | 'risk_pct' | 'risk_dollar' | 'risk_ticks' | 'risk_points' | 'risk_pips'

// ── Marchés NT8 connus (fallback si NT8 ne remonte pas la liste) ───────────
const NT8_MARKETS_FALLBACK: Record<string, {
  name: string; icon: string; instrument: string
  tickSize: number; pointValue: number; pipSize?: number
}> = {
  gold_mgc:   { name: 'Gold (MGC)',      icon: '🥇', instrument: 'MGC',  tickSize: 0.1,  pointValue: 10,   pipSize: 0.1  },
  mnq_nasdaq: { name: 'Nasdaq (MNQ)',    icon: '📊', instrument: 'MNQ',  tickSize: 0.25, pointValue: 2,    pipSize: 1    },
  mcl_crude:  { name: 'Crude Oil (MCL)', icon: '🛢️', instrument: 'MCL',  tickSize: 0.01, pointValue: 100,  pipSize: 0.01 },
  mes_sp500:  { name: 'S&P 500 (MES)',   icon: '📈', instrument: 'MES',  tickSize: 0.25, pointValue: 5,    pipSize: 1    },
  es_sp500:   { name: 'S&P 500 (ES)',    icon: '📈', instrument: 'ES',   tickSize: 0.25, pointValue: 50,   pipSize: 1    },
  nq_nasdaq:  { name: 'Nasdaq (NQ)',     icon: '📊', instrument: 'NQ',   tickSize: 0.25, pointValue: 20,   pipSize: 1    },
  gc_gold:    { name: 'Gold (GC)',       icon: '🥇', instrument: 'GC',   tickSize: 0.1,  pointValue: 100,  pipSize: 0.1  },
  cl_crude:   { name: 'Crude Oil (CL)',  icon: '🛢️', instrument: 'CL',   tickSize: 0.01, pointValue: 1000, pipSize: 0.01 },
  custom:     { name: 'Personnalisé',    icon: '🔍', instrument: '',     tickSize: 0,    pointValue: 0     },
}

// ── Calcul MM complet ──────────────────────────────────────────────────────
function calcMM(
  mode: SizingMode,
  contracts: number,
  riskPct: number,
  riskDollar: number,
  riskTicks: number,
  riskPoints: number,
  riskPips: number,
  balance: number,
  entry: number,
  sl: number,
  pointValue: number,
  tickSize: number,
  pipSize: number,
): { qty: number; riskPerContract: number; totalRisk: number; slDistance: number; slTicks: number; slPoints: number; slPips: number } {
  const slDistance = Math.abs(entry - sl)
  const slTicks    = tickSize > 0 ? slDistance / tickSize : 0
  const slPoints   = slDistance
  const slPips     = pipSize > 0 ? slDistance / pipSize : 0
  const riskPerContract = slDistance * pointValue

  let qty = contracts
  let maxRisk = 0

  if (mode === 'contracts') {
    qty = contracts
  } else if (mode === 'risk_pct' && balance > 0) {
    maxRisk = balance * riskPct / 100
    qty = riskPerContract > 0 ? Math.max(1, Math.floor(maxRisk / riskPerContract)) : 1
  } else if (mode === 'risk_dollar') {
    maxRisk = riskDollar
    qty = riskPerContract > 0 ? Math.max(1, Math.floor(maxRisk / riskPerContract)) : 1
  } else if (mode === 'risk_ticks') {
    // L'utilisateur veut risquer N ticks → on calcule le risque $ correspondant
    maxRisk = riskTicks * tickSize * pointValue
    qty = riskPerContract > 0 ? Math.max(1, Math.floor(maxRisk / riskPerContract)) : 1
  } else if (mode === 'risk_points') {
    maxRisk = riskPoints * pointValue
    qty = riskPerContract > 0 ? Math.max(1, Math.floor(maxRisk / riskPerContract)) : 1
  } else if (mode === 'risk_pips') {
    maxRisk = riskPips * pipSize * pointValue
    qty = riskPerContract > 0 ? Math.max(1, Math.floor(maxRisk / riskPerContract)) : 1
  }

  const totalRisk = qty * riskPerContract
  return { qty, riskPerContract, totalRisk, slDistance, slTicks, slPoints, slPips }
}

// ── Composant visuel des niveaux (style TradingView) ──────────────────────
function LevelVisualizer({
  entry, sl, tp, tp2, type, lastPrice
}: { entry: number; sl: number; tp: number; tp2: number; type: SignalType; lastPrice: number }) {
  if (!entry && !sl && !tp) return null

  const prices = [entry, sl, tp, tp2, lastPrice].filter(p => p > 0)
  if (prices.length < 2) return null

  const min = Math.min(...prices) * 0.9995
  const max = Math.max(...prices) * 1.0005
  const range = max - min
  if (range <= 0) return null

  const pct = (p: number) => ((p - min) / range * 100)

  const levels = [
    tp2 > 0 && { price: tp2, label: 'TP2', color: 'bg-green-400', textColor: 'text-green-700 dark:text-green-300', pct: pct(tp2) },
    tp > 0  && { price: tp,  label: 'TP1', color: 'bg-green-500', textColor: 'text-green-700 dark:text-green-300', pct: pct(tp) },
    entry > 0 && { price: entry, label: 'Entrée', color: type === 'BUY' ? 'bg-blue-500' : 'bg-orange-500', textColor: 'text-blue-700 dark:text-blue-300', pct: pct(entry) },
    lastPrice > 0 && lastPrice !== entry && { price: lastPrice, label: 'Prix', color: 'bg-gray-400', textColor: 'text-gray-500', pct: pct(lastPrice) },
    sl > 0  && { price: sl,  label: 'SL',  color: 'bg-red-500',   textColor: 'text-red-700 dark:text-red-300',   pct: pct(sl) },
  ].filter(Boolean) as { price: number; label: string; color: string; textColor: string; pct: number }[]

  // Trier par prix décroissant pour affichage vertical
  levels.sort((a, b) => b.price - a.price)

  return (
    <div className="relative h-48 bg-gray-50 dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
      {/* Zone profit */}
      {entry > 0 && tp > 0 && (
        <div
          className="absolute left-0 right-0 bg-green-100 dark:bg-green-900/20"
          style={{
            bottom: `${Math.min(pct(entry), pct(tp))}%`,
            height: `${Math.abs(pct(tp) - pct(entry))}%`,
          }}
        />
      )}
      {/* Zone perte */}
      {entry > 0 && sl > 0 && (
        <div
          className="absolute left-0 right-0 bg-red-100 dark:bg-red-900/20"
          style={{
            bottom: `${Math.min(pct(entry), pct(sl))}%`,
            height: `${Math.abs(pct(sl) - pct(entry))}%`,
          }}
        />
      )}
      {/* Lignes de prix */}
      {levels.map((lvl) => (
        <div
          key={lvl.label}
          className="absolute left-0 right-0 flex items-center"
          style={{ bottom: `${lvl.pct}%`, transform: 'translateY(50%)' }}
        >
          <div className={`h-0.5 flex-1 ${lvl.color} opacity-70`} />
          <div className={`flex items-center gap-1 px-2 text-xs font-mono ${lvl.textColor} bg-white dark:bg-gray-900 rounded px-1.5 py-0.5 border border-gray-200 dark:border-gray-700 ml-1 flex-shrink-0`}>
            <span className="font-semibold">{lvl.label}</span>
            <span>{lvl.price.toFixed(2)}</span>
          </div>
        </div>
      ))}
      <p className="absolute bottom-1 left-2 text-xs text-gray-400">Visualisation des niveaux</p>
    </div>
  )
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
    risk_ticks: '10',
    risk_points: '5',
    risk_pips: '10',
  })
  const [sizingMode, setSizingMode] = useState<SizingMode>('contracts')
  const [showConfirm, setShowConfirm] = useState(false)
  const [showHistory, setShowHistory] = useState(false)
  const [showAccounts, setShowAccounts] = useState(true)

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
  const wsConnected = ws.accounts?.connected ?? false

  // Fallback : si l'Add-On n'est pas installé, on utilise les données de health.nt8
  // (remontées par la stratégie V3 via nt8_current_price.json)
  const nt8Health = ws.health?.nt8 ?? null

  const activeAccountName = accountsStatus?.selected_account ?? nt8Health?.selected_account ?? null
  const activeAccount = accountsStatus?.accounts?.find(a => a.name === activeAccountName) ?? null
  const balance = activeAccount?.balance ?? nt8Health?.balance ?? 0
  const dailyPnl = activeAccount?.daily_pnl ?? nt8Health?.daily_pnl ?? null
  const openPositions = activeAccount?.positions ?? []

  // ── Instruments depuis NT8 ─────────────────────────────────────────────
  const nt8Instruments: string[] = accountsStatus?.instruments ?? []
  const activeInstrument = accountsStatus?.active_instrument ?? null

  // ── État de l'Add-On ──────────────────────────────────────────────────
  const hasAddOnData = !!(accountsStatus?.accounts || accountsStatus?.connections)
  const agentConnected = wsConnected || ws.wsConnected

  // ── Point value / tick size / pip size ────────────────────────────────
  const fallbackMarket = NT8_MARKETS_FALLBACK[signalForm.market]
  const pointValue = activeInstrument?.point_value && activeInstrument.point_value > 0
    ? activeInstrument.point_value : (fallbackMarket?.pointValue ?? 0)
  const tickSize = activeInstrument?.tick_size && activeInstrument.tick_size > 0
    ? activeInstrument.tick_size : (fallbackMarket?.tickSize ?? 0)
  const pipSize = fallbackMarket?.pipSize ?? tickSize
  const lastPrice = activeInstrument?.last_price ?? 0

  // ── Calcul MM en temps réel ────────────────────────────────────────────
  const entry = parseFloat(signalForm.entry_price) || lastPrice || 0
  const sl = parseFloat(signalForm.stop_loss) || 0
  const tp = parseFloat(signalForm.target_price) || 0
  const tp2 = parseFloat(signalForm.target_price_2) || 0

  const mm = useMemo(() => calcMM(
    sizingMode,
    parseInt(signalForm.contracts, 10) || 1,
    parseFloat(signalForm.risk_pct) || 1,
    parseFloat(signalForm.risk_dollar) || 100,
    parseFloat(signalForm.risk_ticks) || 10,
    parseFloat(signalForm.risk_points) || 5,
    parseFloat(signalForm.risk_pips) || 10,
    balance, entry, sl, pointValue, tickSize, pipSize,
  ), [sizingMode, signalForm, balance, entry, sl, pointValue, tickSize, pipSize])

  const rrRatio = useMemo(() => {
    if (!entry || !sl || !tp) return null
    const risk = Math.abs(entry - sl)
    const reward = Math.abs(tp - entry)
    return risk > 0 ? reward / risk : null
  }, [entry, sl, tp])

  // ── Mutations comptes ──────────────────────────────────────────────────
  const selectAccountMutation = useMutation({
    mutationFn: (name: string) => nt8AgentService.selectAccount(name),
    onSuccess: (_, name) => toast.success(`Compte ${name} activé`),
    onError: () => toast.error('Erreur lors du changement de compte'),
  })

  const toggleConnectionMutation = useMutation({
    mutationFn: ({ name, connect }: { name: string; connect: boolean }) =>
      nt8AgentService.toggleConnection(name, connect),
    onSuccess: (_, { name, connect }) =>
      toast.success(`${connect ? 'Connexion' : 'Déconnexion'} de ${name} envoyée`),
    onError: () => toast.error('Erreur lors de la commande de connexion'),
  })

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
        || fallbackMarket?.instrument || signalForm.market
      const signal = {
        id: `manual-${Date.now()}`,
        type: signalForm.type,
        entry_price: entry || 0,
        target_price: tp || undefined,
        target_price_2: tp2 || undefined,
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
      toast.error("Veuillez saisir un prix d'entrée pour un ordre limite"); return
    }
    if (!signalForm.stop_loss || sl <= 0) {
      toast.error('⛔ Stop Loss obligatoire'); return
    }
    if (signalForm.type === 'BUY' && entry > 0 && sl >= entry) {
      toast.error('⛔ SL invalide : pour un BUY, le SL doit être < entrée'); return
    }
    if (signalForm.type === 'SELL' && entry > 0 && sl <= entry) {
      toast.error('⛔ SL invalide : pour un SELL, le SL doit être > entrée'); return
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
                <p className="text-sm text-gray-500 mt-0.5">Ordre réel sur NinjaTrader 8</p>
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
                <span className="font-bold text-red-600">
                  {mm.totalRisk > 0 ? `${mm.totalRisk.toLocaleString('fr-FR', { maximumFractionDigits: 0 })} $` : '—'}
                  {balance > 0 && mm.totalRisk > 0 && <span className="font-normal text-gray-400 ml-1">({(mm.totalRisk / balance * 100).toFixed(2)}%)</span>}
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
              <button
                className={`text-sm px-4 py-2 rounded-lg font-semibold text-white flex items-center gap-2 ${signalForm.type === 'BUY' ? 'bg-green-600 hover:bg-green-700' : 'bg-red-600 hover:bg-red-700'}`}
                onClick={() => { setShowConfirm(false); executeMutation.mutate() }}>
                <Send className="h-4 w-4" /> Confirmer {signalForm.type}
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
          <div className="card py-3 px-4 flex items-center gap-3 col-span-2 sm:col-span-1">
            <CheckCircle2 className="h-5 w-5 text-green-500 flex-shrink-0" />
            <div className="min-w-0">
              <p className="text-xs text-gray-500">Compte actif</p>
              <p className="font-semibold text-sm truncate text-green-700 dark:text-green-400">{activeAccountName}</p>
            </div>
          </div>
          <div className="card py-3 px-4">
            <p className="text-xs text-gray-500 flex items-center gap-1"><DollarSign className="h-3 w-3" /> Solde</p>
            <p className="font-bold text-sm mt-0.5">{balance > 0 ? balance.toLocaleString('fr-FR', { maximumFractionDigits: 0 }) + ' $' : '—'}</p>
          </div>
          <div className="card py-3 px-4">
            <p className="text-xs text-gray-500 flex items-center gap-1">
              {dailyPnl !== null && dailyPnl >= 0 ? <TrendingUp className="h-3 w-3 text-green-500" /> : <TrendingDown className="h-3 w-3 text-red-500" />}
              PnL jour
            </p>
            <p className={`font-bold text-sm mt-0.5 ${dailyPnl === null ? '' : dailyPnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              {dailyPnl !== null ? `${dailyPnl >= 0 ? '+' : ''}${dailyPnl.toLocaleString('fr-FR', { maximumFractionDigits: 0 })} $` : '—'}
            </p>
          </div>
          <div className="card py-3 px-4">
            <p className="text-xs text-gray-500 flex items-center gap-1"><Activity className="h-3 w-3" /> Instrument</p>
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
                <span className={`font-bold ${pos.direction === 'Long' ? 'text-green-700 dark:text-green-400' : 'text-red-700 dark:text-red-400'}`}>
                  {pos.direction === 'Long' ? '▲' : '▼'} {pos.instrument}
                </span>
                <span className="text-gray-500">{pos.quantity} × {pos.avg_price.toFixed(2)}</span>
              </div>
              <span className={`font-bold ${pos.unrealized_pnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                {pos.unrealized_pnl >= 0 ? '+' : ''}{pos.unrealized_pnl.toLocaleString('fr-FR', { maximumFractionDigits: 0 })} $
              </span>
            </div>
          ))}
        </div>
      )}

      {/* ── Gestion des comptes & connexions ──────────────────────────────── */}
      {agentStatus?.linked && (
        <div className="card">
          <button className="flex items-center justify-between w-full" onClick={() => setShowAccounts(!showAccounts)}>
            <h2 className="text-sm font-semibold flex items-center gap-2">
              <Landmark className="h-4 w-4" /> Comptes & connexions NinjaTrader
              {activeAccountName && <span className="text-xs font-normal text-green-600 dark:text-green-400">— {activeAccountName}</span>}
            </h2>
            {showAccounts ? <ChevronUp className="h-4 w-4 text-gray-400" /> : <ChevronDown className="h-4 w-4 text-gray-400" />}
          </button>

          {showAccounts && (
            <div className="mt-3 space-y-3">
              {/* Comptes */}
              {accountsStatus?.accounts && accountsStatus.accounts.length > 0 && (
                <div>
                  <p className="text-xs font-medium text-gray-500 mb-2">Comptes disponibles</p>
                  <div className="space-y-1.5">
                    {accountsStatus.accounts.map(acc => {
                      const isActive = acc.name === activeAccountName
                      return (
                        <div key={acc.name} className={`flex items-center justify-between text-xs rounded-lg px-3 py-2 border transition-colors ${isActive ? 'border-green-400 bg-green-50 dark:bg-green-900/20' : 'border-gray-200 dark:border-gray-700 hover:border-blue-300'}`}>
                          <div className="flex items-center gap-2 min-w-0">
                            {isActive ? <CheckCircle2 className="h-3.5 w-3.5 text-green-600 flex-shrink-0" /> : <Landmark className="h-3.5 w-3.5 text-gray-400 flex-shrink-0" />}
                            <div className="min-w-0">
                              <span className={`font-medium truncate ${isActive ? 'text-green-800 dark:text-green-300' : ''}`}>{acc.name}</span>
                              <div className="flex gap-3 text-gray-400 mt-0.5">
                                {acc.balance != null && <span>Solde : {acc.balance.toLocaleString('fr-FR', { maximumFractionDigits: 0 })} $</span>}
                                {acc.daily_pnl != null && <span className={acc.daily_pnl >= 0 ? 'text-green-600' : 'text-red-600'}>{acc.daily_pnl >= 0 ? '+' : ''}{acc.daily_pnl.toLocaleString('fr-FR', { maximumFractionDigits: 0 })} $ jour</span>}
                              </div>
                            </div>
                          </div>
                          {isActive ? (
                            <span className="text-xs font-semibold text-green-700 dark:text-green-400 bg-green-100 dark:bg-green-900/40 px-2 py-0.5 rounded-full flex-shrink-0">✓ Actif</span>
                          ) : (
                            <button
                              className="btn-primary text-xs px-2 py-1 flex-shrink-0"
                              onClick={() => selectAccountMutation.mutate(acc.name)}
                              disabled={selectAccountMutation.isPending}>
                              {selectAccountMutation.isPending ? '...' : 'Activer'}
                            </button>
                          )}
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}

              {/* Connexions */}
              {accountsStatus?.connections && accountsStatus.connections.length > 0 && (
                <div>
                  <p className="text-xs font-medium text-gray-500 mb-2">Connexions</p>
                  <div className="space-y-1.5">
                    {accountsStatus.connections.map(conn => (
                      <div key={conn.name} className={`flex items-center justify-between text-xs rounded-lg px-3 py-2 border ${conn.connected ? 'border-green-400 bg-green-50 dark:bg-green-900/20' : 'border-gray-200 dark:border-gray-700'}`}>
                        <div className="flex items-center gap-2 min-w-0">
                          {conn.connected
                            ? <PlugZap className="h-3.5 w-3.5 text-green-600 flex-shrink-0" />
                            : <Plug className="h-3.5 w-3.5 text-gray-400 flex-shrink-0" />}
                          <div className="min-w-0">
                            <span className="font-medium truncate">{conn.name}</span>
                            <p className="text-gray-400">{conn.status}</p>
                          </div>
                        </div>
                        <button
                          className={`text-xs px-2 py-1 rounded flex-shrink-0 ${conn.connected ? 'btn-danger' : 'btn-primary'}`}
                          onClick={() => toggleConnectionMutation.mutate({ name: conn.name, connect: !conn.connected })}
                          disabled={toggleConnectionMutation.isPending}>
                          {toggleConnectionMutation.isPending ? '...' : conn.connected ? 'Déconnecter' : 'Connecter'}
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}

      {!hasAddOnData && (
                <div className="space-y-2">
                  <p className="text-xs text-gray-500 flex items-center gap-1">
                    <RefreshCw className="h-3 w-3 animate-spin" />
                    {agentConnected
                      ? "Agent connecté — en attente des données NinjaTrader…"
                      : "En attente de la connexion de l'agent…"}
                  </p>
                  {agentConnected && (
                    <div className="text-xs text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/20 rounded-lg p-2 space-y-1">
                      <p className="font-medium">Pour voir vos comptes ici :</p>
                      <p>1. Installez <strong>TelegramTraderAddOn.cs</strong> dans NinjaTrader (AddOns\)</p>
                      <p>2. Compilez (F5) et ouvrez le panneau "TelegramTrader Manager"</p>
                      <p className="text-gray-400">Sans l'Add-On, seule la stratégie V3 (1 compte) est disponible.</p>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* ── Formulaire + MM + Visualisation ───────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">

        {/* Formulaire signal (3/5) */}
        <form onSubmit={handleExecute} className="card space-y-4 lg:col-span-3">
          <h2 className="text-base font-semibold flex items-center gap-2"><Zap className="h-4 w-4" /> Signal manuel</h2>

          {/* Direction */}
          <div>
            <label className="block text-xs font-medium mb-1 text-gray-600 dark:text-gray-400">Direction</label>
            <div className="flex gap-2">
              <button type="button"
                className={`flex-1 py-2.5 rounded-lg text-sm font-bold border-2 transition-colors ${signalForm.type === 'BUY' ? 'bg-green-600 border-green-600 text-white' : 'border-gray-300 dark:border-gray-600 text-gray-500 hover:border-green-400'}`}
                onClick={() => setSignalForm({ ...signalForm, type: 'BUY' })}>▲ BUY</button>
              <button type="button"
                className={`flex-1 py-2.5 rounded-lg text-sm font-bold border-2 transition-colors ${signalForm.type === 'SELL' ? 'bg-red-600 border-red-600 text-white' : 'border-gray-300 dark:border-gray-600 text-gray-500 hover:border-red-400'}`}
                onClick={() => setSignalForm({ ...signalForm, type: 'SELL' })}>▼ SELL</button>
            </div>
          </div>

          {/* Instrument + Type d'ordre */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium mb-1 text-gray-600 dark:text-gray-400">
                Instrument
                {nt8Instruments.length > 0 && <span className="text-green-500 ml-1">✓ NT8</span>}
              </label>
              {nt8Instruments.length > 0 ? (
                <select className="input text-sm" value={signalForm.instrument || ''}
                  onChange={(e) => setSignalForm({ ...signalForm, instrument: e.target.value })}>
                  {nt8Instruments.map(inst => <option key={inst} value={inst}>{inst}</option>)}
                </select>
              ) : (
                <select className="input text-sm" value={signalForm.market}
                  onChange={(e) => {
                    const key = e.target.value
                    setSignalForm({ ...signalForm, market: key, instrument: key === 'custom' ? '' : (NT8_MARKETS_FALLBACK[key]?.instrument ?? '') })
                  }}>
                  {Object.entries(NT8_MARKETS_FALLBACK).filter(([k]) => k !== 'custom').map(([key, m]) => (
                    <option key={key} value={key}>{m.icon} {m.name}</option>
                  ))}
                  <option value="custom">🔍 Autre…</option>
                </select>
              )}
              {(signalForm.market === 'custom' || nt8Instruments.length === 0) && (
                <input type="text" className="input text-sm mt-1" placeholder="Ex: MGC AUG26"
                  value={signalForm.instrument}
                  onChange={(e) => setSignalForm({ ...signalForm, instrument: e.target.value })} />
              )}
            </div>
            <div>
              <label className="block text-xs font-medium mb-1 text-gray-600 dark:text-gray-400">Type d'ordre</label>
              <select className="input text-sm" value={signalForm.order_type}
                onChange={(e) => setSignalForm({ ...signalForm, order_type: e.target.value as OrderExecutionType })}>
                <option value="MARKET">Marché (immédiat)</option>
                <option value="LIMIT">Limite (au prix)</option>
                <option value="LIMIT_THEN_MARKET">Limite → Marché</option>
              </select>
            </div>
          </div>

          {/* Prix : Entrée / SL / TP1 / TP2 */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium mb-1 text-gray-600 dark:text-gray-400">
                Entrée {signalForm.order_type === 'MARKET' && <span className="text-gray-400">(opt.)</span>}
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
            <div>
              <label className="block text-xs font-medium mb-1 text-gray-600 dark:text-gray-400">TP2 <span className="text-gray-400">(opt.)</span></label>
              <input type="number" step="0.01" className="input text-sm" value={signalForm.target_price_2}
                onChange={(e) => setSignalForm({ ...signalForm, target_price_2: e.target.value })} />
            </div>
          </div>

          {/* Visualisation des niveaux (style TradingView) */}
          <LevelVisualizer entry={entry} sl={sl} tp={tp} tp2={tp2} type={signalForm.type} lastPrice={lastPrice} />

          {/* Bouton d'envoi */}
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
          <div>
            <label className="block text-xs font-medium mb-1 text-gray-600 dark:text-gray-400">Mode de calcul de la taille</label>
            <div className="grid grid-cols-3 gap-1">
              {([
                { mode: 'contracts'   as SizingMode, label: 'Contrats', icon: '📦' },
                { mode: 'risk_pct'    as SizingMode, label: '% Capital', icon: '%' },
                { mode: 'risk_dollar' as SizingMode, label: 'Risque $', icon: '$' },
                { mode: 'risk_ticks'  as SizingMode, label: 'Ticks', icon: '⬛' },
                { mode: 'risk_points' as SizingMode, label: 'Points', icon: '📐' },
                { mode: 'risk_pips'   as SizingMode, label: 'Pips', icon: '🔹' },
              ] as const).map(({ mode, label, icon }) => (
                <button key={mode} type="button"
                  className={`py-1.5 px-1 rounded-lg text-xs font-medium border-2 transition-colors ${sizingMode === mode ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300' : 'border-gray-200 dark:border-gray-700 text-gray-500 hover:border-blue-300'}`}
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
                % du capital à risquer
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
              <div className="flex justify-between text-xs text-gray-400 mt-0.5 px-1">
                <span>0.1%</span><span>1%</span><span>2%</span><span>5%</span>
              </div>
            </div>
          )}
          {sizingMode === 'risk_dollar' && (
            <div>
              <label className="block text-xs font-medium mb-1 text-gray-600 dark:text-gray-400">
                Risque max en dollars
                {balance > 0 && <span className="text-gray-400 ml-1">= {((parseFloat(signalForm.risk_dollar) || 0) / balance * 100).toFixed(2)}%</span>}
              </label>
              <div className="flex items-center gap-2">
                <input type="number" step="10" min="10" className="input text-sm flex-1"
                  value={signalForm.risk_dollar}
                  onChange={(e) => setSignalForm({ ...signalForm, risk_dollar: e.target.value })} />
                <span className="text-sm text-gray-500">$</span>
              </div>
            </div>
          )}
          {sizingMode === 'risk_ticks' && (
            <div>
              <label className="block text-xs font-medium mb-1 text-gray-600 dark:text-gray-400">
                Risque en ticks
                {tickSize > 0 && <span className="text-gray-400 ml-1">(1 tick = {tickSize})</span>}
              </label>
              <div className="flex items-center gap-2">
                <input type="number" step="1" min="1" className="input text-sm flex-1"
                  value={signalForm.risk_ticks}
                  onChange={(e) => setSignalForm({ ...signalForm, risk_ticks: e.target.value })} />
                <span className="text-sm text-gray-500">ticks</span>
              </div>
              {tickSize > 0 && pointValue > 0 && (
                <p className="text-xs text-gray-400 mt-1">
                  = {(parseFloat(signalForm.risk_ticks) * tickSize * pointValue).toLocaleString('fr-FR', { maximumFractionDigits: 0 })} $ / contrat
                </p>
              )}
            </div>
          )}
          {sizingMode === 'risk_points' && (
            <div>
              <label className="block text-xs font-medium mb-1 text-gray-600 dark:text-gray-400">
                Risque en points
                {pointValue > 0 && <span className="text-gray-400 ml-1">(1 pt = {pointValue} $)</span>}
              </label>
              <div className="flex items-center gap-2">
                <input type="number" step="0.5" min="0.5" className="input text-sm flex-1"
                  value={signalForm.risk_points}
                  onChange={(e) => setSignalForm({ ...signalForm, risk_points: e.target.value })} />
                <span className="text-sm text-gray-500">pts</span>
              </div>
              {pointValue > 0 && (
                <p className="text-xs text-gray-400 mt-1">
                  = {(parseFloat(signalForm.risk_points) * pointValue).toLocaleString('fr-FR', { maximumFractionDigits: 0 })} $ / contrat
                </p>
              )}
            </div>
          )}
          {sizingMode === 'risk_pips' && (
            <div>
              <label className="block text-xs font-medium mb-1 text-gray-600 dark:text-gray-400">
                Risque en pips
                {pipSize > 0 && <span className="text-gray-400 ml-1">(1 pip = {pipSize})</span>}
              </label>
              <div className="flex items-center gap-2">
                <input type="number" step="1" min="1" className="input text-sm flex-1"
                  value={signalForm.risk_pips}
                  onChange={(e) => setSignalForm({ ...signalForm, risk_pips: e.target.value })} />
                <span className="text-sm text-gray-500">pips</span>
              </div>
              {pipSize > 0 && pointValue > 0 && (
                <p className="text-xs text-gray-400 mt-1">
                  = {(parseFloat(signalForm.risk_pips) * pipSize * pointValue).toLocaleString('fr-FR', { maximumFractionDigits: 0 })} $ / contrat
                </p>
              )}
            </div>
          )}

          {/* Résultat MM */}
          <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-3 space-y-2">
            <div className="flex justify-between items-center">
              <span className="text-xs text-gray-500">Contrats calculés</span>
              <span className="text-3xl font-bold text-blue-600 dark:text-blue-400">{mm.qty}</span>
            </div>
            {mm.slDistance > 0 && (
              <div className="grid grid-cols-3 gap-1 text-xs text-center border-t border-gray-200 dark:border-gray-700 pt-2">
                <div>
                  <p className="text-gray-400">Distance SL</p>
                  <p className="font-mono font-semibold">{mm.slDistance.toFixed(2)}</p>
                </div>
                {tickSize > 0 && <div>
                  <p className="text-gray-400">Ticks</p>
                  <p className="font-mono font-semibold">{mm.slTicks.toFixed(1)}</p>
                </div>}
                {pipSize > 0 && <div>
                  <p className="text-gray-400">Pips</p>
                  <p className="font-mono font-semibold">{mm.slPips.toFixed(1)}</p>
                </div>}
              </div>
            )}
            {mm.riskPerContract > 0 && (
              <div className="flex justify-between text-xs border-t border-gray-200 dark:border-gray-700 pt-2">
                <span className="text-gray-500">Risque / contrat</span>
                <span className="font-mono font-semibold">{mm.riskPerContract.toLocaleString('fr-FR', { maximumFractionDigits: 0 })} $</span>
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
              <div className="flex justify-between text-xs border-t border-gray-200 dark:border-gray-700 pt-2">
                <span className="text-gray-500">Ratio R:R</span>
                <span className={`font-bold ${rrRatio >= 2 ? 'text-green-600' : rrRatio >= 1 ? 'text-yellow-600' : 'text-red-600'}`}>
                  1 : {rrRatio.toFixed(2)} {rrRatio >= 2 ? '✅' : rrRatio >= 1 ? '⚠️' : '❌'}
                </span>
              </div>
            )}
            {mm.totalRisk > 0 && rrRatio !== null && (
              <div className="flex justify-between text-xs">
                <span className="text-gray-500">Gain potentiel</span>
                <span className="font-bold text-green-600 dark:text-green-400">
                  +{(mm.totalRisk * rrRatio).toLocaleString('fr-FR', { maximumFractionDigits: 0 })} $
                </span>
              </div>
            )}
          </div>

          {/* Spécifications instrument */}
          {(pointValue > 0 || tickSize > 0) && (
            <div className="text-xs text-gray-400 space-y-0.5 border-t border-gray-200 dark:border-gray-700 pt-2">
              <p className="font-medium text-gray-500">Spécifications {instrumentDisplay}</p>
              {tickSize > 0 && <p>Tick size : {tickSize} · Valeur tick : {(tickSize * pointValue).toFixed(2)} $</p>}
              {pointValue > 0 && <p>Point value : {pointValue} $ / point</p>}
              {pipSize > 0 && pipSize !== tickSize && <p>Pip size : {pipSize}</p>}
              {lastPrice > 0 && <p>Dernier prix : {lastPrice.toFixed(2)}</p>}
              {nt8Instruments.length === 0 && <p className="text-orange-400">⚠️ Valeurs estimées — connectez NT8 pour les valeurs réelles</p>}
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

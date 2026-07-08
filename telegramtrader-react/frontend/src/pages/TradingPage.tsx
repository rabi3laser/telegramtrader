import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { Send, Zap, Info, History, Target, Percent, AlertCircle } from 'lucide-react'
import { tradingService } from '../services/tradingService'
import { MARKETS, type MarketType, type SignalType, type OrderExecutionType, type Signal } from '../types'

type SizingMode = 'quantity' | 'risk'

export default function TradingPage() {
  const queryClient = useQueryClient()

  const [signalForm, setSignalForm] = useState({
    type: 'BUY' as SignalType,
    market: 'gold_mgc' as MarketType,
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

  const { data: history, isLoading: historyLoading, isError: historyError } = useQuery({
    queryKey: ['trading', 'history'],
    queryFn: () => tradingService.getTradeHistory(50),
    // Retry limité pour ne pas bloquer l'UI trop longtemps si le backend est down
    retry: 2,
  })

  const { data: positions, isError: positionsError } = useQuery({
    queryKey: ['trading', 'positions'],
    queryFn: tradingService.getPositions,
    retry: 2,
  })

  const executeMutation = useMutation({
    mutationFn: () => {
      const signal: Signal = {
        id: `manual-${Date.now()}`,
        type: signalForm.type,
        entry_price: parseFloat(signalForm.entry_price) || 0,
        target_price: signalForm.target_price ? parseFloat(signalForm.target_price) : undefined,
        target_price_2: signalForm.target_price_2 ? parseFloat(signalForm.target_price_2) : undefined,
        stop_loss: signalForm.stop_loss ? parseFloat(signalForm.stop_loss) : undefined,
        market: signalForm.market,
        source_channel: 'manuel',
        date: new Date().toISOString(),
        order_type: signalForm.order_type,
        quantity: sizingMode === 'quantity' ? parseInt(signalForm.quantity, 10) || 1 : undefined,
        risk_pct: sizingMode === 'risk' ? parseFloat(signalForm.risk_pct) || undefined : undefined,
      }
      return tradingService.executeSignal(signal, 'nt8')
    },
    onSuccess: (res) => {
      if (res.success) {
        toast.success(res.message || 'Signal envoyé à NinjaTrader 8')
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
    if (sizingMode === 'risk' && (!signalForm.risk_pct || parseFloat(signalForm.risk_pct) <= 0)) {
      toast.error('Veuillez saisir un pourcentage de risque valide')
      return
    }
    // Afficher la modal de confirmation avant d'envoyer l'ordre
    setShowConfirm(true)
  }

  const handleConfirmExecute = () => {
    setShowConfirm(false)
    executeMutation.mutate()
  }

  const market = MARKETS[signalForm.market as keyof typeof MARKETS]

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
              <div className="flex justify-between">
                <span className="text-gray-500 dark:text-gray-400">Direction</span>
                <span className={`font-semibold ${signalForm.type === 'BUY' ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                  {signalForm.type}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500 dark:text-gray-400">Marché</span>
                <span className="font-medium">{market?.icon} {market?.name ?? signalForm.market}</span>
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

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <form onSubmit={handleExecute} className="card space-y-4">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <Zap className="h-5 w-5" /> Exécuter un signal manuel
          </h2>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium mb-1">Type</label>
              <select
                className="input"
                value={signalForm.type}
                onChange={(e) => setSignalForm({ ...signalForm, type: e.target.value as SignalType })}
              >
                <option value="BUY">BUY</option>
                <option value="SELL">SELL</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Marché</label>
              <select
                className="input"
                value={signalForm.market}
                onChange={(e) => setSignalForm({ ...signalForm, market: e.target.value as MarketType })}
              >
                {Object.entries(MARKETS)
                  .filter(([key]) => key !== 'custom')
                  .map(([key, m]) => (
                    <option key={key} value={key}>
                      {m.icon} {m.name}
                    </option>
                  ))}
              </select>
            </div>
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
            <label className="block text-sm font-medium mb-1">SL (optionnel)</label>
            <input
              type="number"
              step="0.01"
              className="input w-40"
              value={signalForm.stop_loss}
              onChange={(e) => setSignalForm({ ...signalForm, stop_loss: e.target.value })}
            />
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
            // Erreur API positions : afficher un message explicite plutôt que rien
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
        </div>
      </div>

      <div className="card">
        <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <History className="h-5 w-5" /> Historique des trades
        </h2>
        {historyLoading ? (
          <p className="text-sm text-gray-500 dark:text-gray-400">Chargement...</p>
        ) : historyError ? (
          // Erreur API historique : message explicite pour ne pas laisser l'UI vide
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
                  <th className="py-2 pr-4">Marché</th>
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
                    <td className="py-2 pr-4">{MARKETS[t.market as keyof typeof MARKETS]?.icon} {t.market}</td>
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

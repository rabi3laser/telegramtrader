/**
 * Hook React — WebSocket temps réel pour le dashboard du connecteur NT8.
 *
 * Remplace le polling HTTP toutes les 5s par une connexion WebSocket persistante.
 * Le serveur push automatiquement les mises à jour toutes les 3s (ou dès qu'un
 * changement est détecté côté backend).
 *
 * Usage :
 *   const { health, accounts, killSwitch, actionLog, connected, error } = useConnectorWS()
 *
 * Reconnexion automatique :
 *   - Backoff exponentiel : 1s → 2s → 4s → 8s → 16s → 30s (max)
 *   - Arrêt si le composant est démonté ou si l'utilisateur n'est pas authentifié
 *   - Reprise immédiate si la fenêtre reprend le focus (visibilitychange)
 */
import { useEffect, useRef, useState, useCallback } from 'react'
import { useAuthStore } from '../store/authStore'
import type {
  ConnectorHealth,
  AccountsStatusResponse,
  KillSwitchState,
  ActionLogEntry,
} from '../services/nt8AgentService'

// URL de base WebSocket — déduite de l'URL de l'API HTTP
function getWsBaseUrl(): string {
  const apiBase = import.meta.env.VITE_API_URL || 'http://localhost:8000/api'
  // Remplacer http(s):// par ws(s):// et retirer le /api final
  return apiBase
    .replace(/^https:\/\//, 'wss://')
    .replace(/^http:\/\//, 'ws://')
    .replace(/\/api\/?$/, '')
}

// Backoff exponentiel : 1s, 2s, 4s, 8s, 16s, 30s max
const BACKOFF_DELAYS = [1000, 2000, 4000, 8000, 16000, 30000]

export interface ConnectorWSState {
  /** Données de santé du connecteur (Backend / Agent / NT8) */
  health: ConnectorHealth | null
  /** Comptes & connexions NinjaTrader */
  accounts: AccountsStatusResponse | null
  /** État du kill switch */
  killSwitch: KillSwitchState | null
  /** 5 dernières actions */
  actionLog: ActionLogEntry[]
  /** Timestamp du dernier message reçu */
  lastUpdate: number | null
  /** WebSocket connecté au serveur */
  wsConnected: boolean
  /** Message d'erreur si la connexion a échoué */
  error: string | null
  /** Nombre de tentatives de reconnexion */
  reconnectAttempts: number
}

const INITIAL_STATE: ConnectorWSState = {
  health: null,
  accounts: null,
  killSwitch: null,
  actionLog: [],
  lastUpdate: null,
  wsConnected: false,
  error: null,
  reconnectAttempts: 0,
}

export function useConnectorWS(enabled = true): ConnectorWSState {
  const { sessionString, isAuthenticated } = useAuthStore()
  const [state, setState] = useState<ConnectorWSState>(INITIAL_STATE)

  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const attemptRef = useRef(0)
  const mountedRef = useRef(true)

  const connect = useCallback(() => {
    if (!mountedRef.current) return
    if (!isAuthenticated || !sessionString || !enabled) return

    // Fermer la connexion précédente si elle existe
    if (wsRef.current) {
      wsRef.current.onclose = null // éviter la reconnexion automatique
      wsRef.current.close()
      wsRef.current = null
    }

    // Encoder le session_string en base64 pour le passer en query param
    // (les WebSockets navigateur ne supportent pas les headers Authorization)
    const tokenB64 = btoa(sessionString)
    const wsUrl = `${getWsBaseUrl()}/ws/connector?token=${encodeURIComponent(tokenB64)}`

    let ws: WebSocket
    try {
      ws = new WebSocket(wsUrl)
    } catch (err) {
      if (mountedRef.current) {
        setState(prev => ({ ...prev, error: 'Impossible de créer la connexion WebSocket', wsConnected: false }))
      }
      return
    }

    wsRef.current = ws

    ws.onopen = () => {
      if (!mountedRef.current) return
      attemptRef.current = 0
      setState(prev => ({
        ...prev,
        wsConnected: true,
        error: null,
        reconnectAttempts: 0,
      }))
    }

    ws.onmessage = (event) => {
      if (!mountedRef.current) return
      try {
        const msg = JSON.parse(event.data)

        if (msg.type === 'update') {
          setState(prev => ({
            ...prev,
            health: msg.health ?? prev.health,
            accounts: msg.accounts ?? prev.accounts,
            killSwitch: msg.kill_switch ?? prev.killSwitch,
            actionLog: msg.action_log ?? prev.actionLog,
            lastUpdate: msg.ts ?? Date.now() / 1000,
            wsConnected: true,
            error: null,
          }))
        } else if (msg.type === 'error') {
          setState(prev => ({
            ...prev,
            error: msg.message || 'Erreur WebSocket',
            wsConnected: false,
          }))
        }
        // 'pong' → on ignore (juste un keepalive)
      } catch {
        // Message non-JSON → on ignore
      }
    }

    ws.onerror = () => {
      if (!mountedRef.current) return
      setState(prev => ({ ...prev, wsConnected: false }))
    }

    ws.onclose = (event) => {
      if (!mountedRef.current) return

      setState(prev => ({ ...prev, wsConnected: false }))

      // Ne pas reconnecter si fermeture intentionnelle (code 4001 = auth error)
      if (event.code === 4001) {
        setState(prev => ({ ...prev, error: 'Authentification WebSocket échouée' }))
        return
      }

      // Reconnexion automatique avec backoff exponentiel
      const delay = BACKOFF_DELAYS[Math.min(attemptRef.current, BACKOFF_DELAYS.length - 1)]
      attemptRef.current += 1

      setState(prev => ({ ...prev, reconnectAttempts: attemptRef.current }))

      reconnectTimerRef.current = setTimeout(() => {
        if (mountedRef.current) connect()
      }, delay)
    }
  }, [sessionString, isAuthenticated, enabled])

  useEffect(() => {
    mountedRef.current = true
    connect()

    // Reconnecter quand la fenêtre reprend le focus (onglet redevenu actif)
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        const ws = wsRef.current
        if (!ws || ws.readyState === WebSocket.CLOSED || ws.readyState === WebSocket.CLOSING) {
          attemptRef.current = 0 // reset backoff pour reconnexion immédiate
          connect()
        }
      }
    }
    document.addEventListener('visibilitychange', handleVisibilityChange)

    return () => {
      mountedRef.current = false
      document.removeEventListener('visibilitychange', handleVisibilityChange)

      // Annuler le timer de reconnexion
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current)
        reconnectTimerRef.current = null
      }

      // Fermer la connexion WebSocket proprement
      if (wsRef.current) {
        wsRef.current.onclose = null // éviter la reconnexion automatique
        wsRef.current.close()
        wsRef.current = null
      }
    }
  }, [connect])

  return state
}

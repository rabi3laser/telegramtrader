import api from './api'

export interface NT8AgentStatus {
  linked: boolean
  connected: boolean
  account_name?: string
  last_heartbeat?: number | null
  last_price?: Record<string, any> | null
  token_masked?: string
  token?: string
}

export interface PairingCodeResponse {
  code: string
  expires_at: number
  ttl_seconds: number
}

export interface NT8Account {
  name: string
  balance: number
}

export interface NT8Connection {
  name: string
  status: string
  connected: boolean
}

export interface AccountsStatus {
  timestamp?: string
  selected_account?: string
  accounts?: NT8Account[]
  connections?: NT8Connection[]
}

export interface AccountsStatusResponse {
  linked: boolean
  connected: boolean
  accounts_status: AccountsStatus | null
}

// ── Dashboard de santé du connecteur (amélioration A) ──────────────────

export interface BackendHealth {
  ok: boolean
  message: string
}

export interface AgentHealth {
  ok: boolean
  linked: boolean
  connected: boolean
  last_heartbeat_age_sec: number | null
  message: string
}

export interface NT8Health {
  ok: boolean
  active: boolean
  selected_account?: string | null
  trading_blocked: boolean
  position_open: boolean
  balance?: number | null
  daily_pnl?: number | null
  message: string
}

export interface QueueSizes {
  signal_queue: number
  command_queue: number
}

export interface ConnectorHealth {
  backend: BackendHealth
  agent: AgentHealth
  nt8: NT8Health
  queues: QueueSizes
  overall_ok: boolean
}


export const nt8AgentService = {
  // Générer (ou régénérer) le token de l'agent local
  async generateToken(accountName?: string): Promise<NT8AgentStatus> {
    const response = await api.post('/nt8-agent/token', { account_name: accountName })
    return response.data
  },

  // Récupérer le statut de liaison / connexion en temps réel
  async getStatus(): Promise<NT8AgentStatus> {
    const response = await api.get('/nt8-agent/status')
    return response.data
  },

  // Révoquer le token (déconnecter l'agent)
  async revokeToken(): Promise<{ success: boolean }> {
    const response = await api.delete('/nt8-agent/token')
    return response.data
  },

  // Télécharger le script agent pré-configuré (déclenche un téléchargement navigateur)
  // — méthode "historique", conservée en secours si le .exe est bloqué par un antivirus
  // ou si l'utilisateur préfère une solution 100% transparente/auditable.
  async downloadScript(): Promise<void> {
    const response = await api.get('/nt8-agent/download-script', {
      responseType: 'blob',
    })
    const blob = new Blob([response.data], { type: 'text/x-python' })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'telegramtrader_nt8_agent.py'
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(url)
  },

  // Télécharger l'exécutable universel (.exe) — flux recommandé "3 clics" :
  // aucun Python requis, systray, démarrage auto, appairage par code.
  async downloadExe(): Promise<void> {
    const response = await api.get('/nt8-agent/download-exe', {
      responseType: 'blob',
    })
    const blob = new Blob([response.data], { type: 'application/vnd.microsoft.portable-executable' })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'TelegramTraderAgent.exe'
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(url)
  },

  // Télécharger le fichier NinjaScript TelegramSignalStrategyV3.cs (stratégie
  // de trading + panneau de calibration) à installer/compiler dans NinjaTrader 8.
  // Étape PRÉALABLE indispensable avant que l'agent puisse exécuter un signal.
  async downloadStrategy(): Promise<void> {
    const response = await api.get('/nt8-agent/download-strategy', {
      responseType: 'blob',
    })
    const blob = new Blob([response.data], { type: 'text/plain' })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'TelegramSignalStrategyV3.cs'
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(url)
  },

  // Générer un code d'appairage court (façon WhatsApp Web) à saisir UNE SEULE
  // FOIS dans l'agent .exe — évite de manipuler le token brut.
  async generatePairingCode(accountName?: string): Promise<PairingCodeResponse> {

    const response = await api.post('/nt8-agent/pairing-code', { account_name: accountName })
    return response.data
  },

  // Pousser un signal manuellement vers l'agent (tests / usage interne)
  async pushSignal(signal: Record<string, any>): Promise<{ success: boolean }> {
    const response = await api.post('/nt8-agent/push-signal', { signal })
    return response.data
  },

  // Récupérer le dernier instantané connu des comptes/connexions NinjaTrader
  // (remonté via le heartbeat de l'agent local), pour affichage dans Paramètres.
  async getAccountsStatus(): Promise<AccountsStatusResponse> {
    const response = await api.get('/nt8-agent/accounts')
    return response.data
  },

  // Sélectionner le compte NinjaTrader actif à distance (piloté via l'agent local)
  async selectAccount(accountName: string): Promise<{ success: boolean }> {
    const response = await api.post('/nt8-agent/command', {
      action: 'select_account',
      account_name: accountName,
    })
    return response.data
  },

  // Connecter / déconnecter une connexion NinjaTrader (Rithmic, Tradovate, etc.) à distance
  async toggleConnection(connectionName: string, connect: boolean): Promise<{ success: boolean }> {
    const response = await api.post('/nt8-agent/command', {
      action: connect ? 'connect_connection' : 'disconnect_connection',
      connection_name: connectionName,
    })
    return response.data
  },

  // Récupérer l'état de santé complet du connecteur NT8 (dashboard de santé)
  async getConnectorHealth(): Promise<ConnectorHealth> {
    const response = await api.get('/nt8-agent/health')
    return response.data
  },
}



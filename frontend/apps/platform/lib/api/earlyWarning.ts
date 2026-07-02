import { api } from './client'

// Espelha services/gateway/routers/early_warning.py (prefix /api/v1/early-warning).
export interface Gatilho {
  tipo: 'SURTO_VOLUME' | 'PICO_CONGESTIONAMENTO'
  severidade: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW'
  z_score?: number
  variacao_pct?: number
  valor_atual?: number
  media_historica?: number
  taxa_congestionamento?: number
}

export interface EarlyWarningResponse {
  tribunal: string
  classe_tpu: string | null
  assunto_tpu: string | null
  n_gatilhos: number
  tem_alerta: boolean
  gatilhos: Gatilho[]
  disclaimer: string
}

export interface EarlyWarningFiltros {
  tribunal: string
  classe?: string
  assunto?: string
}

export const earlyWarningApi = {
  evaluate: ({ tribunal, classe, assunto }: EarlyWarningFiltros) => {
    const q = new URLSearchParams({ tribunal })
    if (classe) q.set('classe', classe)
    if (assunto) q.set('assunto', assunto)
    return api.get<EarlyWarningResponse>(`/api/v1/early-warning/evaluate?${q.toString()}`)
  },
}

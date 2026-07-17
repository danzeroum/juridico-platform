import { api } from './client'

// Espelha services/gateway/routers/jurimetria.py (prefix /api/v1/jurimetria).
export interface IndicadorRow {
  tribunal: string
  classe_tpu: string
  assunto_tpu: string
  periodo: string
  fonte: string
  n_processos: number
  duracao_mediana_dias: number | null
  duracao_p25_dias: number | null
  duracao_p75_dias: number | null
  taxa_congestionamento: number | null
  taxa_litigiosidade: number | null
  pct_provimento: number | null
}

export interface IndicadoresResponse {
  count: number
  results: IndicadorRow[]
  limit: number
  offset: number
}

export interface MarketIntelSegmento {
  classe_tpu: string
  assunto_tpu: string
  total_processos: number
  congestionamento_medio: number | null
  duracao_mediana_tipica: number | null
  provimento_medio: number | null
}

export interface MarketIntelResponse {
  request_id: string
  tribunal: string
  ramo: string | null
  total_processos: number
  segmentos: MarketIntelSegmento[]
  n_segmentos: number
}

export interface JurimetriaFiltros {
  tribunal?: string
  classe?: string
  assunto?: string
  periodo?: string
  fonte?: string
  limit?: number
  offset?: number
}

function toQuery(params: JurimetriaFiltros): string {
  const q = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== '') q.set(k, String(v))
  }
  const s = q.toString()
  return s ? `?${s}` : ''
}

export const jurimetriaApi = {
  indicadores: (filtros: JurimetriaFiltros = {}) =>
    api.get<IndicadoresResponse>(`/api/v1/jurimetria/indicators${toQuery(filtros)}`),

  marketIntelligence: (tribunal?: string, ramo?: string) =>
    api.post<MarketIntelResponse>('/api/v1/jurimetria/market-intelligence', { tribunal, ramo }),
}

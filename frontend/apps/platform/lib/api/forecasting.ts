import { api } from './client'

// Espelha services/gateway/routers/forecasting.py (prefix /api/v1/forecasting).
export interface ProjecaoPasso {
  passo: number
  valor: number
  intervalo: [number, number]
}

export interface ForecastOk {
  status: 'ok'
  tribunal: string
  classe_tpu: string | null
  assunto_tpu: string | null
  periodos_historicos: string[]
  tendencia: 'CRESCENTE' | 'ESTAVEL' | 'DECRESCENTE'
  inclinacao: number
  ultimo_valor: number
  projecoes: ProjecaoPasso[]
  disclaimer: string
}

export interface ForecastInsuficiente {
  status: 'insuficiente'
  tribunal: string
  classe_tpu: string | null
  assunto_tpu: string | null
  periodos_historicos: string[]
  min_periodos: number
  n: number
}

export type ForecastResponse = ForecastOk | ForecastInsuficiente

export interface ForecastingFiltros {
  tribunal: string
  classe?: string
  assunto?: string
  horizonte?: number
}

export const forecastingApi = {
  demand: ({ tribunal, classe, assunto, horizonte = 3 }: ForecastingFiltros) => {
    const q = new URLSearchParams({ tribunal, horizonte: String(horizonte) })
    if (classe) q.set('classe', classe)
    if (assunto) q.set('assunto', assunto)
    return api.get<ForecastResponse>(`/api/v1/forecasting/demand?${q.toString()}`)
  },
}

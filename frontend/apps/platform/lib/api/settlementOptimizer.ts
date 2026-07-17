import { api } from './client'

// Espelha services/gateway/routers/settlement_optimizer.py (prefix /api/v1/settlement-optimizer).
export interface SettlementRequest {
  valor_causa: number
  prob_favorable?: number
  pct_provimento?: number
  custo_autor?: number
  custo_reu?: number
}

export interface SettlementResponse {
  request_id: string
  prob_procedencia: number
  valor_esperado_autor: number
  valor_esperado_reu: number
  tem_zopa: boolean
  faixa_acordo: [number, number] | null
  acordo_sugerido: number | null
  recomendacao: 'ACORDAR' | 'LITIGAR'
  disclaimer: string
}

export const settlementOptimizerApi = {
  optimize: (body: SettlementRequest) =>
    api.post<SettlementResponse>('/api/v1/settlement-optimizer/optimize', body),
}

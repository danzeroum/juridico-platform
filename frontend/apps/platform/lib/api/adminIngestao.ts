import { api } from './client'

// ATENÇÃO: services/ingest/ ainda não expõe um router HTTP no gateway
// (services/gateway/main.py) — não existe /api/v1/admin/ingestao/* hoje.
// Este client segue o contrato desenhado em api-contracts.md (§IG) para quando
// o backend for exposto; até lá, a página serve fixtures em demoMode e mostra
// um estado de indisponibilidade fora do demo (503).
export type CircuitBreakerState = 'CLOSED' | 'HALF_OPEN' | 'OPEN'

export interface FonteIngestao {
  fonte: string
  lag_dias: number
  circuit_breaker: CircuitBreakerState
  records_in: number
  records_out: number
  perda_pct: number
  ultimo_run_iso: string
}

export interface FontesResponse {
  fontes: FonteIngestao[]
}

export const adminIngestaoApi = {
  fontes: () => api.get<FontesResponse>('/api/v1/admin/ingestao/fontes'),

  run: (fonte: string) =>
    api.post<{ job_id: string }>(`/api/v1/admin/ingestao/fontes/${encodeURIComponent(fonte)}/run`, {}),
}

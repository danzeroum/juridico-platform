import { api } from './client'

// Espelha services/gateway/routers/second_opinion.py (prefix /api/v1/second-opinion).
export interface SecondOpinionRequest {
  legalscore?: number // 0–1000
  taxpredict_prob?: number // 0–1
  pct_provimento?: number // 0–1
}

export interface SecondOpinionOk {
  status: 'ok'
  request_id: string
  favorabilidade: number
  veredito: 'FAVORAVEL' | 'INCERTO' | 'DESFAVORAVEL'
  concordancia: number | null
  nivel_concordancia: 'ALTA' | 'MEDIA' | 'BAIXA' | 'UNICO_SINAL'
  sinais: Record<string, number>
  n_sinais: number
  disclaimer: string
}

export interface SecondOpinionSemSinais {
  status: 'sem_sinais'
  request_id: string
}

export type SecondOpinionResponse = SecondOpinionOk | SecondOpinionSemSinais

export const secondOpinionApi = {
  opinion: (body: SecondOpinionRequest) =>
    api.post<SecondOpinionResponse>('/api/v1/second-opinion/opinion', body),
}

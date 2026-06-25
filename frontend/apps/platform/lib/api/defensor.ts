import { api } from './client'
import type { PetiSection } from './petibot'

export interface EventoAgente {
  ts: string
  evento: string
  detalhe: string
  status: 'ok' | 'running' | 'pending'
}

export interface DefensorResult {
  classificacao: string
  canal: string
  eventos: EventoAgente[]
  secoes: PetiSection[]
  precedentes_encontrados: number
  casos_anteriores: number
  subsidios: string[]
  proximo_responsavel: string
  status: string
  computed_at: string
  contract_version: string
}

export interface DefensorInput {
  descricao: string
  canal: string
  tipo_caso: string
  reclamante: string
  reclamada: string
  cnpj_reclamada?: string
  valor?: number
}

export interface ReputacaoResult {
  termo: string
  encontrado: boolean
  reputacao: {
    empresa?: string
    total?: number
    respondidas?: number
    resolvidas?: number
    pct_resposta?: number
    pct_resolucao?: number
    nota_media?: number | null
  }
  source: string
  contract_version: string
}

export const defensorApi = {
  run: (input: DefensorInput) =>
    api.post<DefensorResult>('/api/v1/defensor/run', input),

  reputacao: (termo: string) =>
    api.get<ReputacaoResult>(`/api/v1/defensor/reputacao/${encodeURIComponent(termo)}`),
}

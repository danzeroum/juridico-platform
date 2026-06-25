import { api } from './client'

export interface PetiSection {
  titulo: string
  conteudo: string
  precedentes: string[]
}

export interface PetiResult {
  tipo_acao: string
  polo_ativo: string
  polo_passivo: string
  secoes: PetiSection[]
  precedentes_encontrados: number
  risk_score?: number | null
  probability_favorable?: number | null
  computed_at: string
  contract_version: string
}

export interface PetiInput {
  descricao: string
  tipo_acao: string
  polo_ativo: string
  polo_passivo: string
  valor_causa?: number
  cnpj_parte?: string
}

export const petibotApi = {
  assemble: (input: PetiInput) =>
    api.post<PetiResult>('/api/v1/petibot/assemble', input),
}

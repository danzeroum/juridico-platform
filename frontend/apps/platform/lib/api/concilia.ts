import { api } from './client'

export interface ConciliaFator {
  nome: string
  impacto: number
  descricao: string
}

export interface ConciliaResult {
  valor_minimo: number
  valor_sugerido: number
  valor_maximo: number
  percentual_causa: number // 0–1
  fatores: ConciliaFator[]
  risco_reu?: number | null
  probabilidade_procedencia?: number | null
  computed_at: string
  contract_version: string
}

export interface ConciliaInput {
  descricao: string
  valor_causa: number
  tipo_acao: string
  cnpj_reu?: string
  cnpj_autor?: string
}

export const conciliaApi = {
  recommend: (input: ConciliaInput) =>
    api.post<ConciliaResult>('/api/v1/concilia/recommend', input),
}

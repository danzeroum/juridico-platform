import { api } from './client'

export interface JurisprudenciaHit {
  doc_id: string
  similarity: number
  ementa: string
  decisao: 'FAVORAVEL' | 'DESFAVORAVEL' | 'PARCIAL' | 'DESCONHECIDO'
  tribunal?: string | null
  ano?: number | null
}

export interface TaxPredictResult {
  materia: string
  probability: number
  ci_lower: number
  ci_upper: number
  rag_hits: number
  jurisprudencias: JurisprudenciaHit[]
  features_used: Record<string, number>
  computed_at: string
  model_version: string
  is_fallback: boolean
  contract_version: string
}

export interface TaxPredictInput {
  descricao: string
  materia: string
  valor?: number
  orgao_autuante?: string
  ano_autuacao?: number
}

export interface IpcaMensal {
  periodo: string
  valor: number
}

export interface MacroResult {
  ipca: {
    acumulado_12m?: number
    referencia?: string
    mensal?: IpcaMensal[]
  }
  source: string
  contract_version: string
}

export const taxpredictApi = {
  predict: (input: TaxPredictInput) =>
    api.post<TaxPredictResult>('/api/v1/taxpredict/predict', input),

  macro: () => api.get<MacroResult>('/api/v1/taxpredict/macro'),
}

import { api } from './client'

export interface ComplianceEvaluation {
  cod_ibge: string
  evaluated_at: string
  rules_fired: number
  envelopes: unknown[]
  contract_version: string
}

export interface Municipio {
  cod_ibge: string
  municipio: string
  uf: string
}

export interface MunicipiosResponse {
  uf: string
  total: number
  municipios: Municipio[]
  source: string
  contract_version: string
}

export interface PopulacaoResponse {
  cod_ibge: string
  populacao: number | null
  ano: string | null
  source: string
  contract_version: string
}

export const complianceApi = {
  evaluate: (ibgeCode: string) =>
    api.post<ComplianceEvaluation>(`/api/v1/compliance/municipality/${ibgeCode}/evaluate`, {}),

  // Coleta ao vivo do IBGE
  municipios: (uf: string) =>
    api.get<MunicipiosResponse>(`/api/v1/compliance/uf/${uf}/municipios`),

  populacao: (codIbge: string) =>
    api.get<PopulacaoResponse>(`/api/v1/compliance/municipio/${codIbge}/populacao`),
}

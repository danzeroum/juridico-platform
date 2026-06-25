import { api } from './client'

export interface ComplianceEvaluation {
  cod_ibge: string
  evaluated_at: string
  rules_fired: number
  envelopes: unknown[]
  contract_version: string
}

export const complianceApi = {
  evaluate: (ibgeCode: string) =>
    api.post<ComplianceEvaluation>(`/api/v1/compliance/municipality/${ibgeCode}/evaluate`, {}),
}

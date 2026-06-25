import { api } from './client'

export interface LicitaIndicadores {
  pct_mesmo_vencedor: number
  pct_dispensa: number
  pct_unico_proponente: number
  pct_prazo_curto: number
}

export interface LicitaEvaluation {
  cnpj_orgao: string
  referencia: string
  total_contratos: number
  indicadores: LicitaIndicadores
  alertas: number
  envelopes: unknown[]
  contract_version: string
}

export const licitawatchApi = {
  evaluate: (cnpjOrgao: string, referencia: string) =>
    api.post<LicitaEvaluation>(
      `/api/v1/licitawatch/orgao/${cnpjOrgao}/evaluate?referencia=${encodeURIComponent(referencia)}`,
      {},
    ),
}

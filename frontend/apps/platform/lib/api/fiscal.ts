import { api } from './client'

// Espelha services/gateway/routers/fiscal.py (prefix /api/v1/fiscal) +
// services/shared/contracts/fiscal.py.
export type UF =
  | 'AC' | 'AL' | 'AP' | 'AM' | 'BA' | 'CE' | 'DF' | 'ES' | 'GO' | 'MA' | 'MT' | 'MS' | 'MG'
  | 'PA' | 'PB' | 'PR' | 'PE' | 'PI' | 'RJ' | 'RN' | 'RS' | 'RO' | 'RR' | 'SC' | 'SP' | 'SE' | 'TO'

export interface NcmTriageRequest {
  descricao: string
  uf_origem: UF
  uf_destino: UF
  data?: string
  ncm_hint?: string
  importado?: boolean
  conteudo_importacao_pct?: number
}

export interface NcmCandidate {
  ncm_codigo: string
  descricao: string
  confidence: number
  fonte_regra: 'TIPI' | 'SENADO' | 'CONFAZ' | 'SEFAZ' | 'FUZZY' | 'RAG'
}

export interface IcmsResolution {
  interna_pct: number | null
  fcp_pct: number | null
  interna_efetiva_pct: number | null
  interestadual_pct: number | null
  difal_pct: number | null
  fundamento_legal: string | null
}

export interface NcmTriageResult {
  sku_descricao: string
  suggested_ncm: NcmCandidate | null
  icms: IcmsResolution
  categoria: string | null
  conflito_detectado: boolean
  observacoes: string[]
  decision_proof: string | null
  contract_version: string
}

export interface SpreadsheetJobResponse {
  job_id: string
  status_url: string
  submitted_at: string
  expected_completion?: string
  contract_version: string
}

export interface FiscalJobRow {
  item: string
  ncm?: string
  confianca?: number
  status: 'ok' | 'rever'
}

export interface FiscalJobStatus {
  job_id?: string
  status: 'queued' | 'running' | 'done' | 'failed'
  progress: number
  total: number
  download_url?: string
  rows?: FiscalJobRow[]
}

export const fiscalApi = {
  triage: (body: NcmTriageRequest) =>
    api.post<NcmTriageResult>('/api/v1/fiscal/ncm/triage', body),

  enrichSpreadsheet: (file: File, ufOrigem: UF) => {
    const form = new FormData()
    form.append('file', file)
    return api.postForm<SpreadsheetJobResponse>(
      `/api/v1/fiscal/spreadsheet/enrich?uf_origem=${ufOrigem}`,
      form,
    )
  },

  jobStatus: (jobId: string) =>
    api.get<FiscalJobStatus>(`/api/v1/fiscal/jobs/${jobId}`),

  audit: (requestId: string) =>
    api.get<{ request_id: string; proof: unknown }>(`/api/v1/fiscal/audit/${requestId}`),
}

import { api } from './client'

export interface AuditFinding {
  rule: string
  severity: 'CRITICO' | 'ALTO' | 'MEDIO'
  description: string
  detail: string
}

export interface AuditReport {
  report_id: string
  generated_at: string
  cnpj?: string | null
  filename?: string | null
  status: string
  summary: Record<string, number>
  total_findings: number
  findings: AuditFinding[]
  fields_analyzed: string[]
  data_lag_note: string
  contract_version: string
}

export const contabiliaApi = {
  upload: (file: File, cnpj?: string) => {
    const form = new FormData()
    form.append('file', file)
    const qs = cnpj ? `?cnpj=${encodeURIComponent(cnpj)}` : ''
    return api.postForm<AuditReport>(`/api/v1/contabilia/audit/upload${qs}`, form)
  },
}

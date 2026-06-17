import { api } from './client'

export interface LegalScoreBreakdownFactor {
  name: string
  label: string
  value: number // 0–1, 1 = healthy
  description?: string
}

export interface LegalScoreResult {
  score: number
  risk_level: 'BAIXO' | 'MODERADO' | 'ALTO' | 'CRITICO'
  confidence_interval: [number, number]
  breakdown: LegalScoreBreakdownFactor[]
  engine: 'python' | 'rust'
  disclaimer: string
  source_date: string
  lag_days: number
  request_id: string
  leaf_hash?: string
  merkle_root?: string
  is_partial?: boolean
}

export interface ModelMetrics {
  status: 'heuristica' | 'calibrado'
  auc: number
  auc_target: number
  brier: number
  brier_target: number
  ks: number
  sample_size: number
}

export interface BatchJob {
  job_id: string
  status: 'queued' | 'running' | 'done' | 'failed'
  progress: number
  total: number
  created_at: string
  download_url?: string
}

export const legalscoreApi = {
  score: (cnpj: string) =>
    api.post<LegalScoreResult>('/api/v1/legalscore/score', { cnpj }),

  modelMetrics: () =>
    api.get<ModelMetrics>('/api/v1/legalscore/model/metrics'),

  audit: (requestId: string) =>
    api.get<{ request_id: string; leaf_hash: string; merkle_root: string; proof: Array<{ position: 'L' | 'R'; hash: string }> }>(
      `/api/v1/legalscore/audit/${requestId}`,
    ),

  batchUpload: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return api.postForm<{ job_id: string }>('/api/v1/legalscore/batch', form)
  },

  batchStatus: (jobId: string) =>
    api.get<BatchJob>(`/api/v1/legalscore/batch/${jobId}`),

  listJobs: () =>
    api.get<BatchJob[]>('/api/v1/legalscore/batch'),
}

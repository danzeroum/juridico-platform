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

// Espelha a resposta de GET /api/v1/legalscore/model-metrics (services/scoring/validation).
export interface ModelMetrics {
  model_type: 'heuristica' | 'calibrado'
  validation_status: 'pending' | 'validated'
  auc: number | null
  brier_score: number | null
  calibration_r2: number | null
  n_validation_samples: number
  validation_note: string
  last_calibrated: string | null
  target_auc: number
  target_brier: number
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
    api.get<ModelMetrics>('/api/v1/legalscore/model-metrics'),

  audit: (requestId: string) =>
    api.get<{ request_id: string; leaf_hash: string; merkle_root: string; proof: Array<{ position: 'L' | 'R'; hash: string }> }>(
      `/api/v1/legalscore/audit/${requestId}`,
    ),

  // POST /batch recebe JSON { cnpjs: [...] } (não upload de arquivo) e devolve 202.
  batchScore: (cnpjs: string[]) =>
    api.post<{ job_id: string; total: number; status: string }>(
      '/api/v1/legalscore/batch',
      { cnpjs },
    ),

  batchStatus: (jobId: string) =>
    api.get<BatchJob>(`/api/v1/legalscore/batch/${jobId}`),
  // Obs.: o gateway não expõe GET /batch (listagem de jobs). Acompanhe via batchStatus(jobId).
}

export const RISK_LEVELS = ['BAIXO', 'MODERADO', 'ALTO', 'CRITICO'] as const
export type RiskLevel = (typeof RISK_LEVELS)[number]

export const FRESHNESS_BANDS = ['fresh', 'stale', 'very_stale'] as const
export type FreshnessBand = (typeof FRESHNESS_BANDS)[number]

export const DATA_CLASSES = ['publico', 'pessoal', 'sensivel'] as const
export type DataClass = (typeof DATA_CLASSES)[number]

export const DELIVERY_STATUSES = ['pending', 'claimed', 'done', 'failed'] as const
export type DeliveryStatus = (typeof DELIVERY_STATUSES)[number]

export const ALERT_CHANNELS = ['webhook', 'email', 'slack', 'whatsapp'] as const
export type AlertChannel = (typeof ALERT_CHANNELS)[number]

export const ALERT_SEVERITIES = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'] as const
export type AlertSeverity = (typeof ALERT_SEVERITIES)[number]

export const RBAC_ROLES = ['admin', 'analyst', 'viewer'] as const
export type RbacRole = (typeof RBAC_ROLES)[number]

export const JOB_STATUSES = ['queued', 'running', 'done', 'failed'] as const
export type JobStatus = (typeof JOB_STATUSES)[number]

export const MODEL_STATUSES = ['heuristica', 'calibrado'] as const
export type ModelStatus = (typeof MODEL_STATUSES)[number]

// LegalScore: score alto = risco baixo
export function scoreToriskLevel(score: number): RiskLevel {
  if (score >= 700) return 'BAIXO'
  if (score >= 500) return 'MODERADO'
  if (score >= 300) return 'ALTO'
  return 'CRITICO'
}

// Freshness: lag in days → band
export function lagToFreshnessBand(lagDays: number): FreshnessBand {
  if (lagDays <= 7) return 'fresh'
  if (lagDays <= 90) return 'stale'
  return 'very_stale'
}

export const PRODUCT_CODES = {
  legalscore: 'LS',
  contabilia: 'CT',
  complianceradar: 'CR',
  taxpredict: 'TP',
  licitawatch: 'LW',
  danobot: 'DB',
  petibot: 'PB',
  concilia: 'CC',
  tribuna: 'TC',
  inicio: 'IN',
  entidade: 'EN',
  alertas: 'AL',
  auditoria: 'AU',
  conformidade: 'CF',
  configuracoes: 'CG',
  jurimetria: 'JM',
  knowledgeGraph: 'KG',
  forecasting: 'FC',
  chamberProfiler: 'CP',
  secondOpinion: 'SO',
  settlementOptimizer: 'ST',
  earlyWarning: 'EW',
  fiscal: 'FI',
  adminIngestao: 'IG',
} as const

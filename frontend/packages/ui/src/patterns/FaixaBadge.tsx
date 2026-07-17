import * as React from 'react'
import { cn } from '../lib/cn'
import { RISK_COLORS } from '@juridico/tokens'

export type FaixaTone = 'BAIXO' | 'MODERADO' | 'ALTO' | 'CRITICO'

const KEYWORD_TONE: Array<[RegExp, FaixaTone]> = [
  [/CRITIC|MUITO_CONGESTIONADO|PREDATORIO/i, 'CRITICO'],
  [/ALTO|LENTO|DECRESCENTE|OPEN/i, 'ALTO'],
  [/MODERADO|CONGESTIONADO|MEDIANO|HALF_OPEN|RECORRENTE|ESTAVEL/i, 'MODERADO'],
  [/BAIXO|RAPIDO|FLUIDO|CLOSED|ISOLADO|CRESCENTE|OCASIONAL|FAVORAVEL/i, 'BAIXO'],
]

function inferTone(value: string): FaixaTone {
  for (const [re, tone] of KEYWORD_TONE) {
    if (re.test(value)) return tone
  }
  return 'MODERADO'
}

interface FaixaBadgeProps {
  value: string
  tone?: FaixaTone
  className?: string
}

/** Badge de faixa categórica (ex.: MUITO_CONGESTIONADO, PROVIMENTO_ALTO, RAPIDO). */
export function FaixaBadge({ value, tone, className }: FaixaBadgeProps) {
  const t = tone ?? inferTone(value)
  const c = RISK_COLORS[t]
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 px-2 py-0.5 rounded-chip text-[11px] font-medium border',
        className,
      )}
      style={{ background: c.bg, color: c.text, borderColor: c.border }}
    >
      {value.replaceAll('_', ' ')}
    </span>
  )
}

import * as React from 'react'
import { cn } from '../lib/cn'
import { RISK_COLORS } from '@juridico/tokens'

export type Relacao = 'ISOLADO' | 'OCASIONAL' | 'RECORRENTE' | 'PREDATORIO'

const RELACAO_TONE: Record<Relacao, keyof typeof RISK_COLORS> = {
  ISOLADO: 'BAIXO',
  OCASIONAL: 'MODERADO',
  RECORRENTE: 'ALTO',
  PREDATORIO: 'CRITICO',
}

interface RelationBadgeProps {
  relacao: Relacao
  className?: string
}

/** Badge de intensidade de co-litigância (Knowledge Graph): ISOLADO → PREDATORIO. */
export function RelationBadge({ relacao, className }: RelationBadgeProps) {
  const c = RISK_COLORS[RELACAO_TONE[relacao]]
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 px-2 py-0.5 rounded-chip text-[11px] font-medium border',
        className,
      )}
      style={{ background: c.bg, color: c.text, borderColor: c.border }}
    >
      {relacao}
    </span>
  )
}

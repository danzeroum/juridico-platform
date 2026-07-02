import * as React from 'react'
import { cn } from '../lib/cn'
import { RISK_COLORS, FRESHNESS_COLORS } from '@juridico/tokens'
import type { FreshnessBand } from '@juridico/tokens'

export type CircuitBreakerState = 'CLOSED' | 'HALF_OPEN' | 'OPEN'

const CB_TONE: Record<CircuitBreakerState, keyof typeof RISK_COLORS> = {
  CLOSED: 'BAIXO',
  HALF_OPEN: 'MODERADO',
  OPEN: 'CRITICO',
}

interface CircuitBreakerBadgeProps {
  state: CircuitBreakerState
  className?: string
}

/** Badge do estado do circuit breaker de uma fonte de ingestão. */
export function CircuitBreakerBadge({ state, className }: CircuitBreakerBadgeProps) {
  const c = RISK_COLORS[CB_TONE[state]]
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 px-2 py-0.5 rounded-chip font-mono text-[10px] font-semibold border',
        className,
      )}
      style={{ background: c.bg, color: c.text, borderColor: c.border }}
    >
      {state === 'OPEN' && (
        <span className="w-1.5 h-1.5 rounded-full flex-shrink-0 animate-pulse" style={{ background: c.solid }} aria-hidden />
      )}
      {state}
    </span>
  )
}

interface FreshnessBandChipProps {
  lagDays: number
  className?: string
}

const FONTE_FRESHNESS_LABEL: Record<FreshnessBand, string> = {
  fresh: 'fresco', stale: 'recente', very_stale: 'defasado',
}

/** Frescor específico do console de Ingestão: ≤2d fresco · ≤7d recente · >7d defasado. */
export function ingestFreshnessBand(lagDays: number): FreshnessBand {
  if (lagDays <= 2) return 'fresh'
  if (lagDays <= 7) return 'stale'
  return 'very_stale'
}

export function FreshnessBandChip({ lagDays, className }: FreshnessBandChipProps) {
  const band = ingestFreshnessBand(lagDays)
  const c = FRESHNESS_COLORS[band]
  return (
    <span
      className={cn('inline-flex items-center gap-1.5 px-2 py-0.5 rounded-[5px] font-mono text-[10px] font-medium border', className)}
      style={{ background: c.bg, color: c.text, borderColor: c.border }}
    >
      <span className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ background: c.dot }} aria-hidden />
      {lagDays}d · {FONTE_FRESHNESS_LABEL[band]}
    </span>
  )
}

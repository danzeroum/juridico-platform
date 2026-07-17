import * as React from 'react'
import { cn } from '../lib/cn'
import { FRESHNESS_COLORS } from '@juridico/tokens'

export type Fonte =
  | 'DATAJUD' | 'ABJ' | 'BLEND' | 'TIPI' | 'CONFAZ' | 'PNCP' | 'SICONFI' | 'RECEITA' | 'PGFN'

interface SourceChipProps {
  fonte: string
  stale?: boolean
  className?: string
}

/** Chip mono de proveniência (DATAJUD/ABJ/BLEND/TIPI/CONFAZ…). Vira âmbar quando a fonte está defasada. */
export function SourceChip({ fonte, stale, className }: SourceChipProps) {
  const c = stale ? FRESHNESS_COLORS.stale : null
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 px-1.5 py-0.5 rounded-[4px] font-mono text-[10px] font-medium border',
        !stale && 'bg-surfaceMuted text-textSecondary border-border',
        className,
      )}
      style={c ? { background: c.bg, color: c.text, borderColor: c.border } : undefined}
      title={stale ? `${fonte} · fonte defasada` : fonte}
    >
      {fonte}
    </span>
  )
}

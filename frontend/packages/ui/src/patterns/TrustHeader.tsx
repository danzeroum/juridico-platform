import * as React from 'react'
import { ShieldCheck } from 'lucide-react'
import { cn } from '../lib/cn'
import { FreshnessSeal } from './FreshnessSeal'
import { HeuristicBadge } from './HeuristicBadge'
import { MonoChip } from '../primitives/Badge'
import type { ModelStatus, FreshnessBand } from '@juridico/tokens'

export interface TrustSource {
  name: string
  lagDays: number
  band: FreshnessBand
}

export interface TrustHeaderProps {
  sources: TrustSource[]
  score?: number
  ciLow?: number
  ciHigh?: number
  modelStatus: ModelStatus
  sourceNames: string[]
  extraSourceCount?: number
  onVerify?: () => void
  className?: string
}

export function TrustHeader({
  sources,
  score,
  ciLow,
  ciHigh,
  modelStatus,
  sourceNames,
  extraSourceCount = 0,
  onVerify,
  className,
}: TrustHeaderProps) {
  return (
    <div className={cn('bg-surface border border-border rounded-card overflow-hidden', className)}>
      <div className="px-5 py-3 border-b border-[#f0f2f5] flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-accent" aria-hidden />
          <span className="text-[11px] font-semibold uppercase tracking-[0.06em] text-textSectionLabel">
            Trust header · procedência
          </span>
        </div>
        {onVerify && (
          <button
            onClick={onVerify}
            className="text-[12px] font-medium text-accent hover:underline flex items-center gap-1"
          >
            🔒 Verificar decisão →
          </button>
        )}
      </div>

      <div className="grid grid-cols-4 divide-x divide-[#f0f2f5]">
        {/* Col 1: Freshness */}
        <div className="px-4 py-4">
          <p className="text-[10px] font-semibold uppercase tracking-[0.06em] text-textSectionLabel mb-2">
            Frescor
          </p>
          <div className="flex flex-col gap-1.5">
            {sources.map((s) => (
              <FreshnessSeal key={s.name} source={s.name} lagDays={s.lagDays} band={s.band} />
            ))}
          </div>
        </div>

        {/* Col 2: Confidence */}
        <div className="px-4 py-4">
          <p className="text-[10px] font-semibold uppercase tracking-[0.06em] text-textSectionLabel mb-2">
            Confiança
          </p>
          {score !== undefined ? (
            <div className="flex flex-col gap-1">
              <span className="font-mono text-[20px] font-semibold text-textPrimary">{score}</span>
              {ciLow !== undefined && ciHigh !== undefined && (
                <span className="text-[11px] text-textMuted font-mono">
                  IC 95%: {ciLow}–{ciHigh}
                </span>
              )}
            </div>
          ) : (
            <span className="text-[12px] text-textFaint">—</span>
          )}
        </div>

        {/* Col 3: Model */}
        <div className="px-4 py-4">
          <p className="text-[10px] font-semibold uppercase tracking-[0.06em] text-textSectionLabel mb-2">
            Modelo
          </p>
          <HeuristicBadge status={modelStatus} />
          {modelStatus === 'heuristica' && (
            <p className="text-[11px] text-textMuted mt-1.5">não é veredito</p>
          )}
        </div>

        {/* Col 4: Sources */}
        <div className="px-4 py-4">
          <p className="text-[10px] font-semibold uppercase tracking-[0.06em] text-textSectionLabel mb-2">
            Fontes
          </p>
          <div className="flex flex-wrap gap-1">
            {sourceNames.map((name) => (
              <MonoChip key={name}>{name}</MonoChip>
            ))}
            {extraSourceCount > 0 && (
              <MonoChip>+{extraSourceCount}</MonoChip>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

import * as React from 'react'
import { cn } from '../lib/cn'

interface SettlementRangeBarProps {
  min: number
  suggested: number
  max: number
  pctOfCase?: number
  className?: string
}

function formatBRL(val: number): string {
  return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 }).format(val)
}

export function SettlementRangeBar({ min, suggested, max, pctOfCase, className }: SettlementRangeBarProps) {
  const range = max - min
  const suggestedPct = range > 0 ? ((suggested - min) / range) * 100 : 50

  const label = `Faixa de acordo: mínimo ${formatBRL(min)}, sugerido ${formatBRL(suggested)}, máximo ${formatBRL(max)}${pctOfCase ? `, equivalente a ${pctOfCase}% do valor da causa` : ''}.`

  return (
    <div className={cn('flex flex-col gap-4', className)} aria-label={label}>
      <div className="text-center">
        <span className="font-mono text-[38px] font-bold text-textPrimary leading-none">
          {formatBRL(suggested)}
        </span>
        {pctOfCase !== undefined && (
          <p className="text-[13px] text-textSecondary mt-1">
            {pctOfCase.toFixed(0)}% do valor da causa
          </p>
        )}
      </div>

      <div className="relative h-3 rounded-full bg-surfaceMuted">
        {/* Range band */}
        <div
          className="absolute h-3 rounded-full bg-accentTintBg border border-accentTintBorder"
          style={{ left: 0, right: 0 }}
        />
        {/* Suggested marker */}
        <div
          className="absolute top-1/2 -translate-y-1/2 w-4 h-4 rounded-full bg-accent border-2 border-surface shadow-float"
          style={{ left: `calc(${suggestedPct}% - 8px)` }}
          aria-hidden
        />
      </div>

      <div className="flex justify-between text-[11px] font-mono text-textMuted">
        <span>{formatBRL(min)}<br /><span className="text-[10px]">mínimo</span></span>
        <span className="text-center text-accent font-semibold">
          {formatBRL(suggested)}<br /><span className="text-[10px]">sugerido</span>
        </span>
        <span className="text-right">{formatBRL(max)}<br /><span className="text-[10px]">máximo</span></span>
      </div>
    </div>
  )
}

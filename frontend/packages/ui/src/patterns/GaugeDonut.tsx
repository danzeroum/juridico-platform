import * as React from 'react'
import { cn } from '../lib/cn'
import { RISK_COLORS } from '@juridico/tokens'

interface GaugeDonutProps {
  value: number // 0–1
  valueLabel?: string // texto central alternativo (ex.: "62%")
  label: string // rótulo abaixo do donut (ex.: "Provimento")
  faixaLabel: string // rótulo de faixa categórica (ex.: "MUITO_CONGESTIONADO")
  tone: keyof typeof RISK_COLORS
  size?: number
  className?: string
}

/** Donut de proporção (conic-gradient) com valor central + rótulo de faixa — CP/SO. */
export function GaugeDonut({ value, valueLabel, label, faixaLabel, tone, size = 140, className }: GaugeDonutProps) {
  const c = RISK_COLORS[tone]
  const pct = Math.round(Math.max(0, Math.min(1, value)) * 100)
  const display = valueLabel ?? `${pct}%`
  const strokeWidth = size * 0.13
  const track = '#e7eaee'

  const style: React.CSSProperties = {
    width: size,
    height: size,
    borderRadius: '50%',
    background: `conic-gradient(${c.solid} ${pct * 3.6}deg, ${track} 0deg)`,
  }

  return (
    <div className={cn('flex flex-col items-center gap-2', className)}>
      <div
        role="img"
        aria-label={`${label}: ${display}, faixa ${faixaLabel.replaceAll('_', ' ')}`}
        style={style}
        className="relative flex items-center justify-center"
      >
        <div
          className="absolute rounded-full bg-surface flex flex-col items-center justify-center"
          style={{ width: size - strokeWidth * 2, height: size - strokeWidth * 2 }}
        >
          <span className="font-mono text-[18px] font-bold text-textPrimary leading-none">{display}</span>
        </div>
      </div>
      <div className="flex flex-col items-center gap-1">
        <span className="text-[11px] text-textMuted">{label}</span>
        <span
          className="text-[10px] font-medium px-1.5 py-0.5 rounded-chip"
          style={{ background: c.bg, color: c.text }}
        >
          {faixaLabel.replaceAll('_', ' ')}
        </span>
      </div>
    </div>
  )
}

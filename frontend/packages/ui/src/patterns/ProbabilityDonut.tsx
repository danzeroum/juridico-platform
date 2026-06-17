import * as React from 'react'
import { cn } from '../lib/cn'

interface ProbabilityDonutProps {
  probability: number // 0–1
  ciLow: number // 0–1
  ciHigh: number // 0–1
  size?: number
  className?: string
}

function describeArc(cx: number, cy: number, r: number, start: number, end: number, sweep: number): string {
  const s = { x: cx + r * Math.cos(start), y: cy + r * Math.sin(start) }
  const e = { x: cx + r * Math.cos(end), y: cy + r * Math.sin(end) }
  return `M ${s.x} ${s.y} A ${r} ${r} 0 ${sweep} 1 ${e.x} ${e.y}`
}

export function ProbabilityDonut({ probability, ciLow, ciHigh, size = 180, className }: ProbabilityDonutProps) {
  const pct = Math.round(probability * 100)
  const cx = size / 2
  const cy = size / 2
  const r = size * 0.38
  const strokeWidth = size * 0.12

  const startAngle = -Math.PI / 2
  const filledAngle = startAngle + 2 * Math.PI * probability

  const ciStartAngle = startAngle + 2 * Math.PI * ciLow
  const ciEndAngle = startAngle + 2 * Math.PI * ciHigh
  const ciSweep = (ciHigh - ciLow) > 0.5 ? 1 : 0

  const label = `Probabilidade de desfecho favorável: ${pct}%. Intervalo de credibilidade 95%: ${Math.round(ciLow * 100)}% a ${Math.round(ciHigh * 100)}%.`

  return (
    <div className={cn('flex flex-col items-center', className)}>
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        role="img"
        aria-label={label}
      >
        <title>{label}</title>

        {/* Track */}
        <circle cx={cx} cy={cy} r={r} fill="none" stroke="#e7eaee" strokeWidth={strokeWidth} />

        {/* CI band */}
        <path
          d={describeArc(cx, cy, r, ciStartAngle, ciEndAngle, ciSweep)}
          fill="none"
          stroke="rgba(47,111,237,0.18)"
          strokeWidth={strokeWidth + 4}
          strokeLinecap="butt"
        />

        {/* Filled arc */}
        {probability > 0 && (
          <path
            d={describeArc(cx, cy, r, startAngle, filledAngle, probability > 0.5 ? 1 : 0)}
            fill="none"
            stroke="#2f6fed"
            strokeWidth={strokeWidth}
            strokeLinecap="round"
          />
        )}

        {/* Center text */}
        <text x={cx} y={cy - 6} textAnchor="middle" className="font-mono" fontSize={size * 0.22} fontWeight="700" fill="#13181f">
          {pct}%
        </text>
        <text x={cx} y={cy + size * 0.1} textAnchor="middle" fontSize={size * 0.08} fill="#76808d">
          probabilidade
        </text>
      </svg>
      <p className="text-[11px] text-textMuted font-mono mt-1">
        IC 95%: {Math.round(ciLow * 100)}%–{Math.round(ciHigh * 100)}%
      </p>
    </div>
  )
}

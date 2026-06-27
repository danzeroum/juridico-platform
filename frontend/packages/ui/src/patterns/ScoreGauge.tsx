import * as React from 'react'
import { cn } from '../lib/cn'
import { RISK_COLORS, scoreToriskLevel } from '@juridico/tokens'

interface ScoreGaugeProps {
  score: number
  ciLow: number
  ciHigh: number
  size?: number
  className?: string
}

// Gauge: 4 segments from 0–1000, semicircle (180°)
// Segments: 0–300 CRITICO (50%), 300–500 ALTO (20%), 500–700 MODERADO (20%), 700–1000 BAIXO (30%)
// Score alto = risco baixo (green on right)
const SEGMENTS = [
  { label: 'CRITICO', from: 0, to: 300, color: '#c4382f' },
  { label: 'ALTO', from: 300, to: 500, color: '#cf6a1f' },
  { label: 'MODERADO', from: 500, to: 700, color: '#b07d00' },
  { label: 'BAIXO', from: 700, to: 1000, color: '#1f8a5b' },
] as const

function scoreToAngle(score: number): number {
  // 0 = left (180°), 1000 = right (0°) in a semicircle going CW from left
  return 180 - (score / 1000) * 180
}

function polarToCartesian(cx: number, cy: number, r: number, angleDeg: number) {
  const rad = (angleDeg * Math.PI) / 180
  return { x: cx + r * Math.cos(rad), y: cy - r * Math.sin(rad) }
}

function describeArc(cx: number, cy: number, r: number, startAngle: number, endAngle: number) {
  const start = polarToCartesian(cx, cy, r, endAngle)
  const end = polarToCartesian(cx, cy, r, startAngle)
  const largeArc = endAngle - startAngle <= 180 ? '0' : '1'
  return `M ${start.x} ${start.y} A ${r} ${r} 0 ${largeArc} 0 ${end.x} ${end.y}`
}

export function ScoreGauge({ score, ciLow, ciHigh, size = 260, className }: ScoreGaugeProps) {
  const cx = size / 2
  const cy = size * 0.62
  const outerR = size * 0.45
  const innerR = size * 0.32
  const trackWidth = outerR - innerR

  const riskLevel = scoreToriskLevel(score)
  const riskColor: { solid: string; bg: string; text: string; border: string } =
    RISK_COLORS[riskLevel as keyof typeof RISK_COLORS]

  const scoreAngle = scoreToAngle(score)
  const ciLowAngle = scoreToAngle(ciLow)
  const ciHighAngle = scoreToAngle(ciHigh)

  // CI band radius (middle of track)
  const midR = (outerR + innerR) / 2
  const ciStart = polarToCartesian(cx, cy, outerR - 2, ciLowAngle)
  const ciEnd = polarToCartesian(cx, cy, outerR - 2, ciHighAngle)
  const ciLargeArc = Math.abs(ciHighAngle - ciLowAngle) > 180 ? '1' : '0'

  const markerPt = polarToCartesian(cx, cy, (outerR + innerR) / 2, scoreAngle)

  const label = `Score ${score} de 1000. Nível de risco: ${riskLevel}. Intervalo de confiança 95%: ${ciLow} a ${ciHigh}.`

  return (
    <div className={cn('flex flex-col items-center', className)}>
      <svg
        width={size}
        height={size * 0.68}
        viewBox={`0 0 ${size} ${size * 0.68}`}
        role="img"
        aria-label={label}
      >
        <title>{label}</title>

        {/* Segments */}
        {SEGMENTS.map((seg) => {
          const startA = scoreToAngle(seg.to)
          const endA = scoreToAngle(seg.from)
          return (
            <path
              key={seg.label}
              d={[
                describeArc(cx, cy, outerR, startA, endA),
                `L ${polarToCartesian(cx, cy, innerR, endA).x} ${polarToCartesian(cx, cy, innerR, endA).y}`,
                `A ${innerR} ${innerR} 0 ${endA - startA > 180 ? '1' : '0'} 1 ${polarToCartesian(cx, cy, innerR, startA).x} ${polarToCartesian(cx, cy, innerR, startA).y}`,
                'Z',
              ].join(' ')}
              fill={seg.color}
              opacity={0.85}
            />
          )
        })}

        {/* CI band overlay */}
        <path
          d={`M ${ciStart.x} ${ciStart.y} A ${outerR - 2} ${outerR - 2} 0 ${ciLargeArc} 1 ${ciEnd.x} ${ciEnd.y}`}
          fill="none"
          stroke="rgba(255,255,255,0.55)"
          strokeWidth={trackWidth - 4}
          strokeLinecap="round"
        />

        {/* Score marker */}
        <circle
          cx={markerPt.x}
          cy={markerPt.y}
          r={size * 0.033}
          fill="white"
          stroke={riskColor.solid}
          strokeWidth={2.5}
        />
      </svg>

      {/* Score number */}
      <div className="flex flex-col items-center -mt-4">
        <span className="font-mono text-[52px] font-bold leading-none text-textPrimary">
          {score}
        </span>
        <span
          className="mt-1 px-2.5 py-0.5 rounded-chip text-[12px] font-semibold border"
          style={{
            background: riskColor.bg,
            color: riskColor.text,
            borderColor: riskColor.border ?? riskColor.bg,
          }}
        >
          {riskLevel}
        </span>
        <span className="text-[11px] text-textFaint mt-1">score alto = risco baixo</span>
      </div>
    </div>
  )
}

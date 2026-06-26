import * as React from 'react'
import { cn } from '../lib/cn'

export type EventStatus = 'ok' | 'running' | 'pending'

const DOT_COLOR: Record<EventStatus, string> = {
  ok: '#22c55e',
  running: '#eab308',
  pending: '#64748b',
}

const DOT_LABEL: Record<EventStatus, string> = {
  ok: 'concluído',
  running: 'em execução',
  pending: 'aguardando',
}

interface EventStatusDotProps {
  status: EventStatus
  /** px — default 8 */
  size?: number
  className?: string
}

/**
 * Bolinha de status de um evento do agente Defensor.
 * `running` pulsa (pulse 1.4s) e respeita prefers-reduced-motion via a classe
 * utilitária `motion-safe:animate-pulse` (não anima se o usuário pediu menos movimento).
 */
export function EventStatusDot({ status, size = 8, className }: EventStatusDotProps) {
  return (
    <span
      role="img"
      aria-label={`status: ${DOT_LABEL[status]}`}
      className={cn('inline-block rounded-full flex-shrink-0', status === 'running' && 'motion-safe:animate-pulse', className)}
      style={{ width: size, height: size, background: DOT_COLOR[status] }}
    />
  )
}

export { DOT_COLOR as EVENT_STATUS_COLORS, DOT_LABEL as EVENT_STATUS_LABELS }

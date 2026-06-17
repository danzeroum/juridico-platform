import * as React from 'react'
import { cn } from '../lib/cn'
import { Badge } from '../primitives/Badge'
import { MonoChip } from '../primitives/Badge'
import type { AlertSeverity, AlertChannel, DeliveryStatus } from '@juridico/tokens'
import { DELIVERY_STATUS_COLORS } from '@juridico/tokens'

export interface AlertItem {
  id: string
  severity: AlertSeverity
  title: string
  subjectRef: string
  channels: AlertChannel[]
  deliveryStatus: DeliveryStatus
  createdAt: string
}

interface AlertListProps {
  alerts: AlertItem[]
  filterSeverity?: AlertSeverity | null
  filterChannel?: AlertChannel | null
  filterStatus?: DeliveryStatus | null
  className?: string
}

const severityIcon: Record<AlertSeverity, string> = {
  LOW: '●',
  MEDIUM: '◆',
  HIGH: '▲',
  CRITICAL: '⬟',
}

export function AlertList({ alerts, filterSeverity, filterChannel, filterStatus, className }: AlertListProps) {
  const filtered = alerts.filter((a) => {
    if (filterSeverity && a.severity !== filterSeverity) return false
    if (filterChannel && !a.channels.includes(filterChannel)) return false
    if (filterStatus && a.deliveryStatus !== filterStatus) return false
    return true
  })

  return (
    <div className={cn('flex flex-col divide-y divide-[#f0f2f5]', className)}>
      {filtered.length === 0 && (
        <p className="py-8 text-center text-[13px] text-textFaint">Nenhum alerta encontrado.</p>
      )}
      {filtered.map((alert) => (
        <AlertRow key={alert.id} alert={alert} />
      ))}
    </div>
  )
}

function AlertRow({ alert }: { alert: AlertItem }) {
  const statusColors = DELIVERY_STATUS_COLORS[alert.deliveryStatus]
  return (
    <div className="flex items-center gap-3 py-3 px-1">
      <Badge variant={alert.severity} dot className="flex-shrink-0">
        <span aria-hidden>{severityIcon[alert.severity]}</span>
        {alert.severity}
      </Badge>

      <div className="flex-1 min-w-0">
        <p className="text-[13px] font-medium text-textPrimary truncate">{alert.title}</p>
        <p className="text-[11px] font-mono text-textMuted mt-0.5">{alert.subjectRef}</p>
      </div>

      <div className="flex items-center gap-1 flex-shrink-0">
        {alert.channels.map((ch) => (
          <MonoChip key={ch}>{ch}</MonoChip>
        ))}
      </div>

      <span
        className="flex-shrink-0 text-[11px] font-medium px-2 py-0.5 rounded-chip"
        style={{ background: statusColors.bg, color: statusColors.text }}
      >
        {alert.deliveryStatus}
      </span>

      <span className="flex-shrink-0 text-[11px] font-mono text-textFaint">{alert.createdAt}</span>
    </div>
  )
}

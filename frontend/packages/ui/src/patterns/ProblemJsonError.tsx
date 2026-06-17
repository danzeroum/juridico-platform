import * as React from 'react'
import { AlertTriangle, Clock, Lock, Server } from 'lucide-react'
import { cn } from '../lib/cn'

export interface ProblemJson {
  type: string
  title: string
  status: number
  detail: string
  instance?: string
  contract_version?: string
  retry_after?: number
}

interface ProblemJsonErrorProps {
  error: ProblemJson
  inline?: boolean
  className?: string
}

function statusIcon(status: number) {
  if (status === 429) return Clock
  if (status === 501) return Lock
  if (status === 503) return Server
  return AlertTriangle
}

function statusTheme(status: number): { bg: string; border: string; text: string; icon: string } {
  if (status === 501) return { bg: '#f7f8fa', border: '#e7eaee', text: '#48515e', icon: '#76808d' }
  if (status >= 500) return { bg: '#fae3e1', border: '#f0c2bd', text: '#8f2a22', icon: '#c4382f' }
  if (status === 429) return { bg: '#fbf6e9', border: '#ecdcae', text: '#7a5800', icon: '#b07d00' }
  return { bg: '#fbe9da', border: '#f0cdab', text: '#9a4a12', icon: '#cf6a1f' }
}

export function ProblemJsonError({ error, inline, className }: ProblemJsonErrorProps) {
  const Icon = statusIcon(error.status)
  const theme = statusTheme(error.status)

  return (
    <div
      role="alert"
      className={cn(
        'flex gap-3 rounded-[8px] border p-4',
        inline ? 'text-[12px]' : 'text-[13px]',
        className,
      )}
      style={{ background: theme.bg, borderColor: theme.border }}
    >
      <Icon className="w-4 h-4 flex-shrink-0 mt-0.5" style={{ color: theme.icon }} aria-hidden />
      <div className="flex flex-col gap-1 min-w-0">
        <p className="font-semibold" style={{ color: theme.text }}>
          {error.title}
          <span className="ml-2 font-mono text-[11px] opacity-60">{error.status}</span>
        </p>
        <p style={{ color: theme.text }} className="opacity-80">{error.detail}</p>

        {error.status === 429 && error.retry_after && (
          <p className="font-mono text-[11px] opacity-70" style={{ color: theme.text }}>
            Tente novamente em {error.retry_after}s
          </p>
        )}

        {error.status === 501 && (
          <p className="text-[11px] opacity-60" style={{ color: theme.text }}>
            Funcionalidade aguardando liberação regulatória (PD-06)
          </p>
        )}

        {error.instance && (
          <p className="font-mono text-[10px] opacity-50 truncate" style={{ color: theme.text }}>
            {error.instance}
          </p>
        )}
        {error.contract_version && (
          <p className="font-mono text-[10px] opacity-40" style={{ color: theme.text }}>
            contract_version: {error.contract_version}
          </p>
        )}
      </div>
    </div>
  )
}

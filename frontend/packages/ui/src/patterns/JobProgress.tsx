import * as React from 'react'
import { CheckCircle, Circle, XCircle, Download } from 'lucide-react'
import { cn } from '../lib/cn'
import { Button } from '../primitives/Button'
import type { JobStatus } from '@juridico/tokens'

export interface JobStep {
  id: string
  label: string
  status: 'pending' | 'active' | 'done' | 'failed'
}

interface JobProgressProps {
  status: JobStatus
  progress: number // 0–100
  steps: JobStep[]
  onDownload?: () => void
  label?: string
  className?: string
}

export function JobProgress({ status, progress, steps, onDownload, label, className }: JobProgressProps) {
  return (
    <div className={cn('flex flex-col gap-4', className)}>
      {/* Status + label */}
      <div className="flex items-center justify-between">
        <span className="text-[13px] font-medium text-textPrimary">
          {label ?? statusLabel(status)}
        </span>
        <span className="font-mono text-[13px] text-textSecondary">{Math.round(progress)}%</span>
      </div>

      {/* Progress bar */}
      <div className="relative h-2 rounded-full bg-surfaceMuted overflow-hidden">
        {status === 'running' ? (
          <div
            className="absolute inset-y-0 left-0 rounded-full transition-all duration-500"
            style={{
              width: `${progress}%`,
              background:
                'repeating-linear-gradient(45deg,#2f6fed 0,#2f6fed 8px,#5b8ff9 8px,#5b8ff9 16px)',
              animation: 'barflow 0.7s linear infinite',
            }}
          />
        ) : status === 'failed' ? (
          <div className="absolute inset-y-0 left-0 w-full rounded-full bg-riskCritical opacity-40" />
        ) : status === 'done' ? (
          <div className="absolute inset-y-0 left-0 w-full rounded-full bg-riskLow" />
        ) : (
          <div className="absolute inset-y-0 left-0 rounded-full bg-accent opacity-20" style={{ width: `${progress}%` }} />
        )}
      </div>

      {/* Steps */}
      <div className="flex flex-col gap-1.5">
        {steps.map((step) => (
          <div key={step.id} className="flex items-center gap-2 text-[12px]">
            <StepIcon status={step.status} />
            <span
              className={cn(
                step.status === 'done' && 'text-textMuted',
                step.status === 'active' && 'text-textPrimary font-medium',
                step.status === 'pending' && 'text-textFaint',
                step.status === 'failed' && 'text-riskCriticalText',
              )}
            >
              {step.label}
            </span>
          </div>
        ))}
      </div>

      {/* Download when done */}
      {status === 'done' && onDownload && (
        <Button variant="secondary" size="sm" onClick={onDownload} className="self-start">
          <Download className="w-3.5 h-3.5" aria-hidden />
          Baixar
        </Button>
      )}
    </div>
  )
}

function StepIcon({ status }: { status: JobStep['status'] }) {
  if (status === 'done') return <CheckCircle className="w-3.5 h-3.5 text-riskLow flex-shrink-0" aria-label="concluído" />
  if (status === 'failed') return <XCircle className="w-3.5 h-3.5 text-riskCritical flex-shrink-0" aria-label="falhou" />
  if (status === 'active') return (
    <div className="w-3.5 h-3.5 flex-shrink-0 rounded-full border-2 border-accent border-t-transparent animate-spin" aria-label="em andamento" />
  )
  return <Circle className="w-3.5 h-3.5 text-textFaint flex-shrink-0" aria-label="pendente" />
}

function statusLabel(status: JobStatus): string {
  switch (status) {
    case 'queued': return '202 Aceito — na fila'
    case 'running': return 'Processando…'
    case 'done': return 'Pronto'
    case 'failed': return 'Falhou'
  }
}

import * as React from 'react'
import { cn } from '../lib/cn'
import { Button } from '../primitives/Button'

interface EmptyStateProps {
  icon?: React.ReactNode
  title: string
  description?: string
  action?: {
    label: string
    onClick: () => void
  }
  demoMode?: boolean
  className?: string
}

export function EmptyState({ icon, title, description, action, demoMode, className }: EmptyStateProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center gap-4 py-16 px-8 text-center',
        className,
      )}
    >
      {icon && (
        <div className="w-12 h-12 rounded-full bg-surfaceMuted flex items-center justify-center text-textMuted text-2xl">
          {icon}
        </div>
      )}
      <div className="flex flex-col gap-1">
        <p className="text-[15px] font-semibold text-textPrimary">{title}</p>
        {description && (
          <p className="text-[13px] text-textMuted max-w-sm">{description}</p>
        )}
        {demoMode && (
          <p className="text-[12px] font-mono text-textFaint mt-1">
            modo limpo · sem conexão com as APIs
          </p>
        )}
      </div>
      {action && (
        <Button variant="secondary" size="md" onClick={action.onClick}>
          {action.label}
        </Button>
      )}
    </div>
  )
}

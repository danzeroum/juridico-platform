import * as React from 'react'
import { cn } from '../lib/cn'

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  padding?: 'none' | 'sm' | 'md' | 'lg'
}

const paddingClasses = {
  none: '',
  sm: 'p-4',
  md: 'p-5',
  lg: 'p-6',
}

export function Card({ padding = 'md', className, children, ...props }: CardProps) {
  return (
    <div
      className={cn(
        'bg-surface rounded-card border border-border',
        paddingClasses[padding],
        className,
      )}
      {...props}
    >
      {children}
    </div>
  )
}

export function CardHeader({ className, children, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn('flex items-center justify-between gap-3 mb-4', className)}
      {...props}
    >
      {children}
    </div>
  )
}

export function SectionLabel({ className, children, ...props }: React.HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      className={cn(
        'text-[11px] font-semibold uppercase tracking-[0.06em] text-textSectionLabel',
        className,
      )}
      {...props}
    >
      {children}
    </span>
  )
}

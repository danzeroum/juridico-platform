import * as React from 'react'
import { cn } from '../lib/cn'

interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
  height?: string | number
  width?: string | number
  rounded?: string
}

export function Skeleton({ height, width, rounded = 'rounded-[6px]', className, style, ...props }: SkeletonProps) {
  return (
    <div
      className={cn('animate-pulse bg-[#e8ecf0]', rounded, className)}
      style={{ height, width, ...style }}
      aria-hidden
      {...props}
    />
  )
}

export function SkeletonText({ lines = 3, className }: { lines?: number; className?: string }) {
  return (
    <div className={cn('flex flex-col gap-2', className)}>
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton key={i} height={14} width={i === lines - 1 ? '60%' : '100%'} />
      ))}
    </div>
  )
}

export function SkeletonCard({ className }: { className?: string }) {
  return (
    <div className={cn('bg-surface rounded-card border border-border p-5 flex flex-col gap-3', className)}>
      <Skeleton height={16} width="40%" />
      <SkeletonText lines={2} />
    </div>
  )
}

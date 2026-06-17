import * as React from 'react'
import { cn } from '../lib/cn'

type AvatarSize = 'xs' | 'sm' | 'md' | 'lg'

const sizeClasses: Record<AvatarSize, string> = {
  xs: 'w-5 h-5 text-[9px]',
  sm: 'w-7 h-7 text-[11px]',
  md: 'w-9 h-9 text-[13px]',
  lg: 'w-12 h-12 text-[16px]',
}

interface AvatarProps {
  name: string
  src?: string
  size?: AvatarSize
  className?: string
  status?: 'online' | 'away' | 'offline'
}

export function Avatar({ name, src, size = 'md', status, className }: AvatarProps) {
  const initials = name
    .split(' ')
    .slice(0, 2)
    .map((n) => n[0]?.toUpperCase() ?? '')
    .join('')

  return (
    <div className={cn('relative inline-flex flex-shrink-0', className)}>
      <div
        className={cn(
          'rounded-full bg-accentTintBg text-accent font-semibold flex items-center justify-center select-none',
          sizeClasses[size],
        )}
        aria-label={name}
        title={name}
      >
        {src ? (
          <img src={src} alt={name} className="w-full h-full rounded-full object-cover" />
        ) : (
          initials
        )}
      </div>
      {status && (
        <span
          className={cn(
            'absolute bottom-0 right-0 w-2.5 h-2.5 rounded-full border-2 border-surface',
            status === 'online' && 'bg-riskLow',
            status === 'away' && 'bg-riskMedium',
            status === 'offline' && 'bg-textMuted',
          )}
          aria-label={`Status: ${status}`}
        />
      )}
    </div>
  )
}

interface AvatarStackProps {
  names: string[]
  max?: number
  size?: AvatarSize
}

export function AvatarStack({ names, max = 4, size = 'sm' }: AvatarStackProps) {
  const visible = names.slice(0, max)
  const overflow = names.length - max

  return (
    <div className="flex -space-x-2">
      {visible.map((name) => (
        <Avatar key={name} name={name} size={size} className="ring-2 ring-surface" />
      ))}
      {overflow > 0 && (
        <div
          className={cn(
            'rounded-full bg-surfaceMuted text-textMuted font-semibold flex items-center justify-center ring-2 ring-surface',
            sizeClasses[size],
          )}
        >
          +{overflow}
        </div>
      )}
    </div>
  )
}

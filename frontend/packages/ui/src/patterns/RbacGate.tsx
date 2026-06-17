import * as React from 'react'
import { Lock } from 'lucide-react'
import { cn } from '../lib/cn'
import type { RbacRole } from '@juridico/tokens'

type RequiredRole = 'analyst' | 'admin'

const ROLE_RANK: Record<RbacRole, number> = { viewer: 0, analyst: 1, admin: 2 }

function hasAccess(role: RbacRole, required: RequiredRole): boolean {
  return ROLE_RANK[role] >= ROLE_RANK[required]
}

interface RbacGateProps {
  role: RbacRole
  requires: RequiredRole
  children: React.ReactNode
  fallback?: React.ReactNode
  showLockChip?: boolean
  className?: string
}

export function RbacGate({ role, requires, children, fallback, showLockChip = true, className }: RbacGateProps) {
  if (hasAccess(role, requires)) {
    return <>{children}</>
  }

  if (fallback) return <>{fallback}</>

  if (showLockChip) {
    return (
      <span
        className={cn(
          'inline-flex items-center gap-1 px-2 py-0.5 rounded-chip text-[11px] font-medium',
          'bg-surfaceMuted text-textMuted border border-border cursor-default select-none',
          className,
        )}
        aria-label={`Exige perfil ${requires === 'admin' ? 'Admin' : 'Analista'}`}
        title={`Exige perfil ${requires === 'admin' ? 'Admin' : 'Analista'}`}
      >
        <Lock className="w-3 h-3" aria-hidden />
        exige perfil {requires === 'admin' ? 'Admin' : 'Analista'}
      </span>
    )
  }

  return null
}

interface ViewerBannerProps {
  className?: string
}

export function ViewerBanner({ className }: ViewerBannerProps) {
  return (
    <div
      role="banner"
      className={cn(
        'flex items-center gap-2 px-4 py-2.5 bg-[#f7f8fa] border-b border-border text-[12px] text-textSecondary',
        className,
      )}
    >
      <Lock className="w-3.5 h-3.5 text-textMuted" aria-hidden />
      Modo leitura — ações de análise exigem perfil Analista ou Admin
    </div>
  )
}

'use client'
import React, { createContext, useContext, useState } from 'react'
import type { RbacRole } from '@juridico/tokens'

interface Tenant {
  id: string
  name: string
}

interface ShellContextValue {
  tenant: Tenant | null
  role: RbacRole
  demoMode: boolean
  setTenant: (t: Tenant) => void
  setRole: (r: RbacRole) => void
  setDemoMode: (v: boolean) => void
}

const ShellContext = createContext<ShellContextValue | null>(null)

// demoMode liga por padrão (experiência de demonstração). Em produção, defina
// NEXT_PUBLIC_DEMO_MODE=false para que as páginas usem dados reais do gateway.
// TODO (P0): hidratar tenant/role a partir do JWT em vez de defaults fixos —
// hoje todo usuário assume role 'admin'. Ver PRODUCTION-READINESS.md.
const DEMO_DEFAULT = process.env.NEXT_PUBLIC_DEMO_MODE !== 'false'

export function ShellProvider({ children }: { children: React.ReactNode }) {
  const [tenant, setTenant] = useState<Tenant | null>({ id: 'demo', name: 'Acme Ltda.' })
  const [role, setRole] = useState<RbacRole>('admin')
  const [demoMode, setDemoMode] = useState(DEMO_DEFAULT)

  return (
    <ShellContext.Provider value={{ tenant, role, demoMode, setTenant, setRole, setDemoMode }}>
      {children}
    </ShellContext.Provider>
  )
}

export function useShell(): ShellContextValue {
  const ctx = useContext(ShellContext)
  if (!ctx) throw new Error('useShell must be used inside ShellProvider')
  return ctx
}

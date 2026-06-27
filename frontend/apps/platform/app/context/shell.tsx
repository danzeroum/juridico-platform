'use client'
import React, { createContext, useContext, useEffect, useState } from 'react'
import type { RbacRole } from '@juridico/tokens'
import { authApi } from '@/lib/api/auth'

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
const DEMO_DEFAULT = process.env.NEXT_PUBLIC_DEMO_MODE !== 'false'

const VALID_ROLES: RbacRole[] = ['admin', 'analyst', 'viewer']

export function ShellProvider({ children }: { children: React.ReactNode }) {
  const [tenant, setTenant] = useState<Tenant | null>({ id: 'demo', name: 'Acme Ltda.' })
  const [role, setRole] = useState<RbacRole>('admin')
  const [demoMode, setDemoMode] = useState(DEMO_DEFAULT)

  // Hidrata a sessão real: se houver login (cookie jwt), usa o role/tenant do
  // gateway em vez do default 'admin'. Sem sessão (401), mantém os defaults do
  // demo — best-effort, nunca quebra a UI.
  useEffect(() => {
    let cancelled = false
    authApi
      .me()
      .then((me) => {
        if (cancelled) return
        if (VALID_ROLES.includes(me.role)) setRole(me.role)
        if (me.tenant_id) setTenant({ id: me.tenant_id, name: me.tenant_id })
      })
      .catch(() => {
        /* sem sessão — mantém defaults do demo */
      })
    return () => {
      cancelled = true
    }
  }, [])

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

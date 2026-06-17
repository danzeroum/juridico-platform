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

export function ShellProvider({ children }: { children: React.ReactNode }) {
  const [tenant, setTenant] = useState<Tenant | null>({ id: 'demo', name: 'Acme Ltda.' })
  const [role, setRole] = useState<RbacRole>('admin')
  const [demoMode, setDemoMode] = useState(true)

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

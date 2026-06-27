import type { RbacRole } from '@juridico/tokens'

export interface MeResponse {
  user_id: string
  tenant_id: string | null
  role: RbacRole
}

/**
 * Sessão do usuário. `me()` chama a route same-origin /api/auth/me (que
 * encaminha o cookie httpOnly ao gateway). Rejeita se não autenticado (401).
 */
export const authApi = {
  me: async (): Promise<MeResponse> => {
    const res = await fetch('/api/auth/me', { cache: 'no-store' })
    if (!res.ok) throw new Error(`auth/me ${res.status}`)
    return res.json()
  },
}

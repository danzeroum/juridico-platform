import { NextRequest, NextResponse } from 'next/server'

const GATEWAY_URL = process.env.NEXT_PUBLIC_GATEWAY_URL ?? 'http://localhost:8000'

/**
 * Proxy de sessão: lê o cookie httpOnly `jwt` (inacessível ao JS do browser) e
 * consulta o gateway com `Authorization: Bearer`, devolvendo os claims do usuário.
 * Mantém o fluxo same-origin (sem CORS) e o token fora do alcance do client.
 */
export async function GET(req: NextRequest) {
  const jwt = req.cookies.get('jwt')?.value
  if (!jwt) {
    return NextResponse.json({ detail: 'Não autenticado.' }, { status: 401 })
  }

  try {
    const res = await fetch(`${GATEWAY_URL}/api/v1/auth/me`, {
      headers: { Authorization: `Bearer ${jwt}` },
      cache: 'no-store',
    })
    const data = await res.json().catch(() => ({}))
    return NextResponse.json(data, { status: res.status })
  } catch {
    return NextResponse.json({ detail: 'Gateway indisponível.' }, { status: 502 })
  }
}

import { NextRequest, NextResponse } from 'next/server'

const GATEWAY_URL = process.env.NEXT_PUBLIC_GATEWAY_URL ?? 'http://localhost:8000'

/** Lê o corpo seja qual for o content-type (JSON do client, ou form nativo). */
async function readBody(req: NextRequest): Promise<Record<string, string>> {
  const ct = req.headers.get('content-type') ?? ''
  if (ct.includes('application/json')) {
    return (await req.json().catch(() => ({}))) as Record<string, string>
  }
  const form = await req.formData().catch(() => null)
  if (!form) return {}
  return Object.fromEntries(
    [...form.entries()].map(([k, v]) => [k, String(v)]),
  )
}

export async function POST(req: NextRequest) {
  // Aceita tanto JSON (fetch do client) quanto form-urlencoded (submit nativo),
  // e mapeia os campos da UI (email/tenant) para o contrato do gateway
  // (username/tenant_slug).
  const raw = await readBody(req)
  const payload = {
    username: raw.username ?? raw.email ?? '',
    password: raw.password ?? '',
    tenant_slug: raw.tenant_slug ?? raw.tenant ?? '',
  }

  const res = await fetch(`${GATEWAY_URL}/api/v1/auth/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })

  if (!res.ok) {
    // Submit nativo volta para /login com flag de erro; fetch recebe o JSON.
    const err = await res.json().catch(() => ({ detail: 'Credenciais inválidas.' }))
    const wantsJson = (req.headers.get('content-type') ?? '').includes('application/json')
    if (wantsJson) return NextResponse.json(err, { status: res.status })
    return NextResponse.redirect(new URL('/login?erro=1', req.url), { status: 303 })
  }

  const data = await res.json()
  // Submit nativo: redireciona para a home autenticada já com o cookie.
  // fetch (JSON): recebe { ok: true } e decide a navegação no client.
  const wantsJson = (req.headers.get('content-type') ?? '').includes('application/json')
  const response = wantsJson
    ? NextResponse.json({ ok: true })
    : NextResponse.redirect(new URL('/inicio', req.url), { status: 303 })

  // Forward the httpOnly cookie from the gateway, or set our own
  const setCookie = res.headers.get('set-cookie')
  if (setCookie) {
    response.headers.set('set-cookie', setCookie)
  } else if (data.access_token) {
    response.cookies.set('jwt', data.access_token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'strict',
      maxAge: 60 * 60 * 24, // 24h
      path: '/',
    })
  }

  return response
}

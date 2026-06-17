import { NextRequest, NextResponse } from 'next/server'

const GATEWAY_URL = process.env.GATEWAY_URL ?? 'http://localhost:8000'

export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => ({}))

  const res = await fetch(`${GATEWAY_URL}/api/v1/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Credenciais inválidas.' }))
    return NextResponse.json(err, { status: res.status })
  }

  const data = await res.json()
  const response = NextResponse.json({ ok: true })

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

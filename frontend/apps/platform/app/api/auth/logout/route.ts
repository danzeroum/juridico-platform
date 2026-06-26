import { NextRequest, NextResponse } from 'next/server'

/**
 * Logout — limpa o cookie httpOnly de sessão e redireciona para /login.
 * Aceita GET (navegação direta a partir do botão) e POST.
 */
function clearAndRedirect(req: NextRequest): NextResponse {
  const res = NextResponse.redirect(new URL('/login', req.url), { status: 303 })
  res.cookies.set('jwt', '', { httpOnly: true, path: '/', maxAge: 0 })
  return res
}

export function GET(req: NextRequest) {
  return clearAndRedirect(req)
}

export function POST(req: NextRequest) {
  return clearAndRedirect(req)
}

import { NextRequest, NextResponse } from 'next/server'

/**
 * Proteção de rotas por sessão (cookie httpOnly `jwt`).
 *
 * Desligada por padrão para preservar o modo demo. Em produção, defina
 * `REQUIRE_AUTH=true` no ambiente para exigir login em todas as rotas do app.
 *
 * NOTA: aqui validamos apenas a PRESENÇA do cookie. A verificação da assinatura
 * RS256 (via JWKS do gateway) deve ser adicionada antes de tratar isto como
 * controle de acesso forte — ver PRODUCTION-READINESS.md (P0).
 */
const REQUIRE_AUTH = process.env.REQUIRE_AUTH === 'true'

const PUBLIC_PATHS = ['/login']

export function middleware(req: NextRequest) {
  if (!REQUIRE_AUTH) return NextResponse.next()

  const { pathname } = req.nextUrl

  // Libera a API de autenticação e rotas públicas.
  if (
    pathname.startsWith('/api/auth') ||
    PUBLIC_PATHS.some((p) => pathname === p || pathname.startsWith(p + '/'))
  ) {
    return NextResponse.next()
  }

  if (!req.cookies.get('jwt')?.value) {
    const url = req.nextUrl.clone()
    url.pathname = '/login'
    url.searchParams.set('next', pathname)
    return NextResponse.redirect(url)
  }

  return NextResponse.next()
}

export const config = {
  // Aplica a tudo, exceto assets estáticos do Next e arquivos com extensão.
  matcher: [
    '/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico)$).*)',
  ],
}

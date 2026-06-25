'use client'
import { ProblemJsonError } from '@juridico/ui'
import type { ProblemJson } from '@juridico/ui'
import { ApiError } from '@/lib/api/client'

/**
 * Banner de erro padrão para chamadas de API (mutation/query).
 * Só renderiza fora do modo demo e quando o erro é um ApiError (problem+json).
 * Centraliza o bloco antes repetido em todas as páginas de produto.
 */
export function ApiErrorBanner({ error, demoMode = false }: { error: unknown; demoMode?: boolean }) {
  if (demoMode || !(error instanceof ApiError)) return null
  return <ProblemJsonError error={error.problem as ProblemJson} />
}

'use client'
import { useEffect, useRef, useState, useCallback } from 'react'

interface StaggerOptions {
  total: number
  /** ms entre cada item. Default 620. */
  interval?: number
  /** dispara automaticamente ao montar/`run`. Default true. */
  auto?: boolean
}

/**
 * useStaggeredReveal — revela `total` itens um a um (stagger) para o feed do agente.
 * Respeita prefers-reduced-motion: revela tudo de uma vez, sem timers.
 * Retorna `{ revealed, done, run }`; chame `run()` para (re)iniciar.
 */
export function useStaggeredReveal({ total, interval = 620, auto = true }: StaggerOptions) {
  const [revealed, setRevealed] = useState(auto ? 0 : total)
  const [done, setDone] = useState(!auto)
  const timer = useRef<ReturnType<typeof setInterval>>()

  const run = useCallback(() => {
    if (timer.current) clearInterval(timer.current)
    const reduced = typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    if (reduced) { setRevealed(total); setDone(true); return }
    setRevealed(1); setDone(false)
    timer.current = setInterval(() => {
      setRevealed((n) => {
        if (n >= total) { clearInterval(timer.current); setDone(true); return total }
        return n + 1
      })
    }, interval)
  }, [total, interval])

  useEffect(() => {
    if (auto) run()
    return () => { if (timer.current) clearInterval(timer.current) }
  }, [auto, run])

  return { revealed, done, run }
}

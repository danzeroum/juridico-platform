import * as React from 'react'
import { cn } from '../lib/cn'

export interface Step {
  id: string
  label: string
}

interface StepIndicatorProps {
  steps: Step[]
  /** índice (0-based) do passo atual */
  current: number
  /** índice (0-based) do passo mais avançado já alcançado — limita o avanço */
  maxReached: number
  /** navega para um passo já concluído/alcançado */
  onNavigate?: (index: number) => void
  className?: string
}

/**
 * StepIndicator — 4 passos do fluxo do Defensor (Entrada · Execução · Resultado · Protocolo).
 * Regras: volta livre a passos já alcançados; NÃO permite pular adiante (só a ação da fase
 * avança). Estados por passo: concluído (✓, preenchido) · ativo (anel) · pendente (cinza).
 */
export function StepIndicator({ steps, current, maxReached, onNavigate, className }: StepIndicatorProps) {
  return (
    <ol className={cn('flex items-center bg-surface border border-border rounded-card px-[18px] py-3', className)}>
      {steps.map((step, i) => {
        const done = i < current
        const active = i === current
        const reachable = i <= maxReached
        return (
          <React.Fragment key={step.id}>
            <li>
              <button
                type="button"
                disabled={!reachable}
                aria-current={active ? 'step' : undefined}
                onClick={() => reachable && onNavigate?.(i)}
                className={cn('flex items-center gap-2.5 px-1 py-0.5', reachable ? 'cursor-pointer' : 'cursor-default')}
              >
                <span
                  className="w-[30px] h-[30px] rounded-full flex items-center justify-center font-mono text-[12px] font-semibold flex-none"
                  style={{
                    background: done ? '#2f6fed' : active ? '#fff' : '#eef1f4',
                    color: done ? '#fff' : active ? '#2f6fed' : '#9aa3af',
                    border: done ? '2px solid #2f6fed' : active ? '2px solid #2f6fed' : '1px solid #e3e7ec',
                  }}
                >
                  {done ? '✓' : i + 1}
                </span>
                <span className="flex flex-col items-start leading-[1.15]">
                  <span className="font-mono text-[9.5px] tracking-[0.08em] text-textFaint">PASSO {i + 1}</span>
                  <span className={cn('text-[13px] font-semibold', active || done ? 'text-textPrimary' : 'text-textFaint')}>
                    {step.label}
                  </span>
                </span>
              </button>
            </li>
            {i < steps.length - 1 && (
              <li aria-hidden className="flex-1 h-0.5 mx-1.5 rounded" style={{ background: i < current ? '#2f6fed' : '#e7eaee' }} />
            )}
          </React.Fragment>
        )
      })}
    </ol>
  )
}

export const DEFENSOR_STEPS: Step[] = [
  { id: 'entrada', label: 'Entrada' },
  { id: 'exec', label: 'Execução' },
  { id: 'result', label: 'Resultado' },
  { id: 'proto', label: 'Protocolo' },
]

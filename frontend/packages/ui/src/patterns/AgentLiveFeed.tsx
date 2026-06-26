import * as React from 'react'
import { cn } from '../lib/cn'
import { EventStatusDot, type EventStatus } from './EventStatusDot'

export interface AgentEvent {
  /** HH:MM:SS (já formatado) ou ISO — o feed usa só a parte de hora */
  ts: string
  /** chave técnica do evento, ex. `jurisprudencia.match` */
  evento: string
  /** detalhe curto em PT-BR, ex. `47 precedentes` */
  detalhe: string
  status: EventStatus
  /** título legível p/ o tratamento B (timeline). Default: deriva de `evento`. */
  titulo?: string
}

export type FeedTreatment = 'terminal' | 'timeline'

interface AgentLiveFeedProps {
  events: AgentEvent[]
  /** quantos eventos já revelados (stagger controlado pelo container). Default: todos. */
  revealed?: number
  treatment?: FeedTreatment
  /** rótulo do cabeçalho do terminal */
  caseRef?: string
  className?: string
}

function fmtTime(ts: string): string {
  return ts.length >= 19 && ts.includes('T') ? ts.slice(11, 19) : ts
}

/**
 * AgentLiveFeed — feed de execução do agente, em 2 tratamentos.
 *
 * - `terminal`  → escuro, monoespaçado, "máquina trabalhando" (ref. Sofira).
 * - `timeline`  → claro, integrado ao app, com linha de preenchimento progressivo.
 *
 * Ambos consomem o MESMO array de eventos. O stagger de entrada é controlado pelo
 * container via `revealed` (incremente com setInterval ~620ms); em
 * prefers-reduced-motion, passe `revealed = events.length` para revelar tudo.
 *
 * Tokens do terminal: bg #08111f · header #0c1c33 · texto #cdd9ea · secundário #5a6b85.
 */
export function AgentLiveFeed({
  events,
  revealed = events.length,
  treatment = 'terminal',
  caseRef = 'DF-2026-0418',
  className,
}: AgentLiveFeedProps) {
  return treatment === 'terminal'
    ? <TerminalFeed events={events} revealed={revealed} caseRef={caseRef} className={className} />
    : <TimelineFeed events={events} revealed={revealed} className={className} />
}

/* ---------------- Tratamento A — Terminal escuro ---------------- */
function TerminalFeed({ events, revealed, caseRef, className }: Required<Pick<AgentLiveFeedProps, 'events' | 'revealed' | 'caseRef'>> & { className?: string }) {
  const visible = events.slice(0, Math.max(revealed, 0))
  return (
    <div className={cn('rounded-[11px] overflow-hidden border', className)} style={{ borderColor: '#1a2d4e' }}>
      <div className="flex items-center gap-2 px-4 py-2.5" style={{ background: '#0c1c33' }}>
        <span className="w-2 h-2 rounded-full" style={{ background: '#475569' }} aria-hidden />
        <span className="w-2 h-2 rounded-full" style={{ background: '#475569' }} aria-hidden />
        <span className="w-2 h-2 rounded-full motion-safe:animate-pulse" style={{ background: '#eab308' }} aria-hidden />
        <span className="ml-2 font-mono text-[10.5px] tracking-[0.13em]" style={{ color: '#9fb0c5' }}>
          DEFENSOR · AGENT · LIVE
        </span>
        <span className="ml-auto font-mono text-[10px]" style={{ color: '#5a6b85' }}>caso #{caseRef}</span>
      </div>
      <ul className="flex flex-col gap-3 px-4 py-4 min-h-[280px]" style={{ background: '#08111f' }} aria-live="polite">
        {visible.map((e, i) => (
          <li key={i} className="flex items-start gap-3 motion-safe:animate-[fadeup_.32s_ease]">
            <span className="font-mono text-[10.5px] pt-px flex-none" style={{ color: '#46566f' }}>{fmtTime(e.ts)}</span>
            <div className="flex flex-col gap-0.5 min-w-0">
              <div className="flex items-center gap-2">
                <EventStatusDot status={e.status} />
                <span className="font-mono text-[12px] font-medium" style={{ color: '#cdd9ea' }}>{e.evento}</span>
              </div>
              <span className="font-mono text-[10.5px] pl-4" style={{ color: '#5a6b85' }}>{e.detalhe}</span>
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}

/* ---------------- Tratamento B — Timeline clara ---------------- */
function TimelineFeed({ events, revealed, className }: Required<Pick<AgentLiveFeedProps, 'events' | 'revealed'>> & { className?: string }) {
  return (
    <div className={cn('bg-surface border border-border rounded-card px-6 py-2', className)}>
      {events.map((e, i) => {
        const done = i < revealed - 1 || (i === revealed - 1 && e.status === 'ok')
        const running = i === revealed - 1 && e.status === 'running'
        const last = i === events.length - 1
        return (
          <div key={i} className="flex gap-4 items-stretch">
            <div className="flex flex-col items-center flex-none w-6">
              <span
                className={cn(
                  'w-6 h-6 rounded-full flex items-center justify-center font-mono text-[10px] font-semibold flex-none',
                  running && 'motion-safe:animate-pulse',
                )}
                style={{
                  background: done ? '#2f6fed' : running ? '#fbf4e2' : '#f1f3f6',
                  color: done ? '#fff' : running ? '#7a5800' : '#9aa3af',
                  border: running ? '2px solid #eab308' : done ? '2px solid #2f6fed' : '1px solid #e3e7ec',
                }}
              >
                {done ? '✓' : i + 1}
              </span>
              {!last && <span className="flex-1 w-0.5 my-0.5" style={{ background: done ? '#bcd0f5' : '#eef1f4' }} />}
            </div>
            <div className="flex-1 pt-1 pb-[18px]">
              <div className="flex items-center gap-2.5">
                <span className="text-[13.5px] font-semibold" style={{ color: done || running ? '#13181f' : '#9aa3af' }}>
                  {e.titulo ?? e.evento}
                </span>
                <StatusSeal done={done} running={running} />
              </div>
              <p className="text-[12px] mt-0.5" style={{ color: '#8a93a0' }}>{e.detalhe}</p>
            </div>
          </div>
        )
      })}
    </div>
  )
}

function StatusSeal({ done, running }: { done: boolean; running: boolean }) {
  const label = done ? 'ok' : running ? 'running' : 'pendente'
  const style = done
    ? 'bg-riskLowBg text-riskLowText border-[#bfe3d0]'
    : running
      ? 'bg-riskMediumBg text-riskMediumText border-[#ecdcae]'
      : 'bg-surfaceMuted text-textFaint border-border'
  return (
    <span className={cn('font-mono text-[9.5px] font-semibold px-1.5 py-px rounded-[5px] border', style)}>
      {label}
    </span>
  )
}

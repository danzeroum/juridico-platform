import '@testing-library/jest-dom/vitest'
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { AgentLiveFeed, type AgentEvent } from './AgentLiveFeed'
import { EventStatusDot } from './EventStatusDot'
import { ProtocolStatusCard } from './ProtocolStatusCard'
import { ProvenanceTag } from './ProvenanceTag'
import { StepIndicator, DEFENSOR_STEPS } from './StepIndicator'
import { Segmented } from '../primitives/Segmented'

/** Caso de exemplo (Mariana Alves × Telecom Brasil Conecta) — espelha o pipeline real. */
const MOCK_EVENTS: AgentEvent[] = [
  { ts: '12:48:04', evento: 'caso.classificado', detalhe: 'CONSUMERISTA · cobrança indevida', status: 'ok', titulo: 'Caso classificado' },
  { ts: '12:48:05', evento: 'reclamante.consultado', detalhe: '2 casos anteriores', status: 'ok', titulo: 'Reclamante consultado' },
  { ts: '12:48:06', evento: 'subsidios.solicitando', detalhe: 'crm · contrato + cobranças', status: 'ok', titulo: 'Reunindo subsídios' },
  { ts: '12:48:11', evento: 'subsidios.ok', detalhe: '3 docs anexados', status: 'ok', titulo: 'Subsídios reunidos' },
  { ts: '12:48:12', evento: 'jurisprudencia.match', detalhe: '47 precedentes', status: 'ok', titulo: 'Jurisprudência casada' },
  { ts: '12:48:14', evento: 'defesa.redigindo', detalhe: 'via IA · rascunho v3', status: 'running', titulo: 'Redigindo defesa' },
  { ts: '12:48:18', evento: 'defesa.pronta', detalhe: '4 seções', status: 'ok', titulo: 'Defesa pronta' },
  { ts: '12:48:19', evento: 'protocolo.preparado', detalhe: 'CONSUMIDOR_GOV · resp.: agente', status: 'pending', titulo: 'Protocolo preparado' },
]

describe('EventStatusDot', () => {
  it('expõe aria-label legível por status', () => {
    render(<EventStatusDot status="running" />)
    expect(screen.getByRole('img')).toHaveAttribute('aria-label', 'status: em execução')
  })
})

describe('AgentLiveFeed · terminal', () => {
  it('revela apenas os eventos até `revealed`', () => {
    render(<AgentLiveFeed events={MOCK_EVENTS} treatment="terminal" revealed={3} />)
    expect(screen.getByText('caso.classificado')).toBeInTheDocument()
    expect(screen.getByText('subsidios.solicitando')).toBeInTheDocument()
    // o 4º evento ainda não foi revelado
    expect(screen.queryByText('subsidios.ok')).not.toBeInTheDocument()
  })

  it('com reduced-motion (revealed = todos) mostra a sequência inteira', () => {
    render(<AgentLiveFeed events={MOCK_EVENTS} treatment="terminal" revealed={MOCK_EVENTS.length} />)
    expect(screen.getByText('protocolo.preparado')).toBeInTheDocument()
  })
})

describe('AgentLiveFeed · timeline', () => {
  it('renderiza títulos legíveis dos passos', () => {
    render(<AgentLiveFeed events={MOCK_EVENTS} treatment="timeline" revealed={5} />)
    expect(screen.getByText('Jurisprudência casada')).toBeInTheDocument()
    expect(screen.getByText('Protocolo preparado')).toBeInTheDocument()
  })
})

describe('ProtocolStatusCard', () => {
  it('mostra número e link apenas em ENVIADO', () => {
    render(
      <ProtocolStatusCard
        canal="CONSUMIDOR_GOV" status="ENVIADO" modo="real"
        numero="CG-2026-0098432" url="https://www.consumidor.gov.br/"
        mensagem="ok"
      />,
    )
    expect(screen.getByText('CG-2026-0098432')).toBeInTheDocument()
    expect(screen.getByRole('link')).toHaveAttribute('href', 'https://www.consumidor.gov.br/')
  })

  it('exibe o modo de forma explícita (ação sensível)', () => {
    render(<ProtocolStatusCard canal="PROCON" status="SIMULADO" modo="simulacao" numero="SIM-1" mensagem="x" />)
    expect(screen.getByText('simulação')).toBeInTheDocument()
  })

  it('omite número quando null (FALHA / sem credenciais)', () => {
    render(<ProtocolStatusCard canal="PROCON" status="FALHA" modo="real" numero={null} mensagem="503" />)
    expect(screen.queryByText(/número de protocolo/i)).not.toBeInTheDocument()
  })

  it('não quebra com status fora da união (fallback defensivo)', () => {
    // @ts-expect-error — simula backend que evoluiu os estados
    render(<ProtocolStatusCard canal="PROCON" status="PROCESSANDO" modo="real" numero={null} mensagem="x" />)
    expect(screen.getByText('FALHA')).toBeInTheDocument()
  })
})

describe('ProvenanceTag', () => {
  it.each([
    ['ia', '✦ via IA'],
    ['parcial', 'via IA · parcial'],
    ['template', 'via template'],
  ] as const)('%s → "%s"', (value, label) => {
    render(<ProvenanceTag value={value} />)
    expect(screen.getByText(label)).toBeInTheDocument()
  })
})

describe('StepIndicator', () => {
  it('desabilita passos além de maxReached e não navega', () => {
    const onNavigate = vi.fn()
    render(<StepIndicator steps={DEFENSOR_STEPS} current={0} maxReached={0} onNavigate={onNavigate} />)
    // passo 3 (Resultado, índice 2) está além de maxReached=0 → desabilitado
    const botoes = screen.getAllByRole('button')
    expect(botoes[2]).toBeDisabled()
    botoes[2].click()
    expect(onNavigate).not.toHaveBeenCalled()
  })
})

describe('Segmented', () => {
  it('marca a opção ativa via aria-checked', () => {
    render(
      <Segmented
        value="timeline"
        onChange={() => {}}
        options={[{ id: 'terminal', label: 'Terminal' }, { id: 'timeline', label: 'Timeline' }]}
      />,
    )
    expect(screen.getByRole('radio', { name: 'Timeline' })).toHaveAttribute('aria-checked', 'true')
    expect(screen.getByRole('radio', { name: 'Terminal' })).toHaveAttribute('aria-checked', 'false')
  })
})

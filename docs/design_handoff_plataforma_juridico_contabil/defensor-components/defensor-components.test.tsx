import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { AgentLiveFeed } from './AgentLiveFeed'
import { EventStatusDot } from './EventStatusDot'
import { ProtocolStatusCard } from './ProtocolStatusCard'
import { ProvenanceTag } from './ProvenanceTag'
import { MOCK_EVENTS } from './fixtures'

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
  it('renderiza títulos legíveis de todos os passos', () => {
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

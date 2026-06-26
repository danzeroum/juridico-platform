import type { Meta, StoryObj } from '@storybook/react'
import { ProtocolStatusCard, type ProtocolStatus } from './ProtocolStatusCard'

const meta: Meta<typeof ProtocolStatusCard> = {
  title: 'Defensor/ProtocolStatusCard',
  component: ProtocolStatusCard,
  parameters: { layout: 'centered' },
  args: { canal: 'CONSUMIDOR_GOV', enviadoEm: '2026-06-25T12:48:21' },
}
export default meta
type Story = StoryObj<typeof ProtocolStatusCard>

export const Simulado: Story = {
  args: {
    status: 'SIMULADO', modo: 'simulacao',
    numero: 'SIM-CONSUMIDOR_GOV-1A2B3C4D5E',
    mensagem: 'Execução em modo simulação — nenhuma submissão real foi feita ao portal. Ative o modo real e configure as credenciais para protocolar de fato.',
  },
}

export const AguardaCredenciais: Story = {
  args: {
    status: 'AGUARDA_CREDENCIAIS', modo: 'real', numero: null,
    mensagem: 'Modo real ativo, porém as credenciais do portal Consumidor.gov não estão configuradas para este tenant. Solicite ao Admin o cadastro das credenciais.',
  },
}

export const Enviado: Story = {
  args: {
    status: 'ENVIADO', modo: 'real',
    numero: 'CG-2026-0098432', url: 'https://www.consumidor.gov.br/',
    mensagem: 'Defesa protocolada com sucesso no portal Consumidor.gov. O número acima foi emitido pelo portal e consta na trilha de auditoria.',
  },
}

export const Falha: Story = {
  args: {
    status: 'FALHA', modo: 'real', numero: null,
    mensagem: 'O portal Consumidor.gov retornou erro 503 (indisponível) durante a submissão. Nenhum protocolo foi gerado; a defesa será reprocessada automaticamente.',
  },
}

export const CanalNaoSuportado: Story = {
  args: {
    status: 'CANAL_NAO_SUPORTADO', modo: 'na', numero: null, canal: 'CONTENCIOSO',
    mensagem: 'O canal selecionado não oferece protocolo automático pela plataforma. Encaminhe a defesa para peticionamento manual pelo responsável.',
  },
}

/** Galeria com os 5 estados lado a lado. */
export const Todos: Story = {
  render: () => {
    const base = { canal: 'CONSUMIDOR_GOV', enviadoEm: '2026-06-25T12:48:21' }
    const rows: { status: ProtocolStatus; modo: any; numero: string | null; mensagem: string }[] = [
      { status: 'SIMULADO', modo: 'simulacao', numero: 'SIM-…-1A2B3C', mensagem: 'Nenhuma submissão real foi feita.' },
      { status: 'AGUARDA_CREDENCIAIS', modo: 'real', numero: null, mensagem: 'Modo real sem credenciais configuradas.' },
      { status: 'ENVIADO', modo: 'real', numero: 'CG-2026-0098432', mensagem: 'Protocolado com sucesso no portal.' },
      { status: 'FALHA', modo: 'real', numero: null, mensagem: 'Portal retornou 503 (indisponível).' },
      { status: 'CANAL_NAO_SUPORTADO', modo: 'na', numero: null, mensagem: 'Canal sem protocolo automático.' },
    ]
    return (
      <div className="grid grid-cols-2 gap-4 max-w-[760px]">
        {rows.map((r) => <ProtocolStatusCard key={r.status} {...base} {...r} />)}
      </div>
    )
  },
}

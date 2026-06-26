import type { AgentEvent } from './AgentLiveFeed'

/**
 * Fixture do caso de exemplo (Mariana Alves de Souza × Telecom Brasil Conecta S.A.).
 * Usado em stories e testes. Espelha a sequência real do pipeline do agente.
 */
export const MOCK_EVENTS: AgentEvent[] = [
  { ts: '12:48:04', evento: 'caso.classificado',     detalhe: 'CONSUMERISTA · cobrança indevida', status: 'ok',      titulo: 'Caso classificado' },
  { ts: '12:48:05', evento: 'reclamante.consultado', detalhe: '2 casos anteriores',               status: 'ok',      titulo: 'Reclamante consultado' },
  { ts: '12:48:06', evento: 'subsidios.solicitando', detalhe: 'crm · contrato + cobranças',       status: 'ok',      titulo: 'Reunindo subsídios' },
  { ts: '12:48:11', evento: 'subsidios.ok',          detalhe: '3 docs anexados',                  status: 'ok',      titulo: 'Subsídios reunidos' },
  { ts: '12:48:12', evento: 'jurisprudencia.match',  detalhe: '47 precedentes',                   status: 'ok',      titulo: 'Jurisprudência casada' },
  { ts: '12:48:14', evento: 'defesa.redigindo',      detalhe: 'via IA · rascunho v3',             status: 'running', titulo: 'Redigindo defesa' },
  { ts: '12:48:18', evento: 'defesa.pronta',         detalhe: '4 seções · 12.480 caracteres',     status: 'ok',      titulo: 'Defesa pronta' },
  { ts: '12:48:19', evento: 'protocolo.preparado',   detalhe: 'CONSUMIDOR_GOV · resp.: agente',   status: 'pending', titulo: 'Protocolo preparado' },
]

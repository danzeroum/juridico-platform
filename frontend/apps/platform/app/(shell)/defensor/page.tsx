'use client'
import { useState } from 'react'
import {
  Card, SectionLabel, Badge, VerifiableCitationChip, AntiHallucinationGuard,
  EmptyState, Textarea, Input, Button, ViewerBanner, RbacGate,
} from '@juridico/ui'
import { useShell } from '@/app/context/shell'

const CANAIS = ['PROCON', 'CONSUMIDOR_GOV', 'OUVIDORIA', 'CONTENCIOSO']
const TIPOS = ['CONSUMERISTA', 'CIVEL', 'TRABALHISTA', 'TRIBUTARIO', 'PREVIDENCIARIO', 'ADMINISTRATIVO']

type Status = 'ok' | 'running' | 'pending'
const MOCK_EVENTOS: { ts: string; evento: string; detalhe: string; status: Status }[] = [
  { ts: '12:48:04', evento: 'caso.classificado', detalhe: 'cobrança indevida', status: 'ok' },
  { ts: '12:48:05', evento: 'reclamante.consultado', detalhe: '3 casos anteriores', status: 'ok' },
  { ts: '12:48:06', evento: 'subsidios.solicitando', detalhe: 'crm · pedidos', status: 'ok' },
  { ts: '12:48:11', evento: 'subsidios.ok', detalhe: '3 docs anexados', status: 'ok' },
  { ts: '12:48:12', evento: 'jurisprudencia.match', detalhe: '47 precedentes', status: 'ok' },
  { ts: '12:48:14', evento: 'defesa.redigindo', detalhe: 'rascunho v3', status: 'running' },
  { ts: '12:48:18', evento: 'protocolo.preparado', detalhe: 'PROCON · responsável: agente', status: 'pending' },
]

const MOCK_SECOES = [
  {
    titulo: 'DOS FATOS',
    conteudo: 'O reclamante identificou cobranças recorrentes em sua fatura referentes a serviço jamais contratado, tendo realizado diversas tentativas de cancelamento via SAC, todas sem solução...',
    precedentes: [
      { doc_id: 'STJ-REsp-001-2023', href: 'https://www.cnj.jus.br/datajud/STJ-REsp-001-2023', count: 12 },
      { doc_id: 'TJSP-AC-456-2022', href: 'https://www.cnj.jus.br/datajud/TJSP-AC-456-2022', count: 7 },
    ],
    precedentes_count: 19,
  },
  {
    titulo: 'DO DIREITO DO CONSUMIDOR',
    conteudo: 'O Código de Defesa do Consumidor (Lei 8.078/90), em seu art. 42, parágrafo único, assegura a repetição do indébito em dobro nos casos de cobrança indevida, salvo engano justificável...',
    precedentes: [
      { doc_id: 'STJ-AgInt-789-2021', href: 'https://www.cnj.jus.br/datajud/STJ-AgInt-789-2021', count: 9 },
    ],
    precedentes_count: 9,
  },
  {
    titulo: 'DOS DANOS',
    conteudo: 'Os transtornos suportados pelo reclamante, somados ao tempo despendido em atendimentos infrutíferos e à cobrança indevida persistente, configuram dano moral indenizável...',
    precedentes: [
      { doc_id: 'TJSP-AC-321-2023', href: 'https://www.cnj.jus.br/datajud/TJSP-AC-321-2023', count: 4 },
    ],
    precedentes_count: 4,
  },
  {
    titulo: 'DOS PEDIDOS',
    conteudo: 'Diante do exposto, requer-se: a) o cancelamento imediato da cobrança; b) a restituição em dobro dos valores indevidamente cobrados; c) a condenação ao pagamento de indenização por danos morais...',
    precedentes: [],
    precedentes_count: 0,
  },
]

function StatusDot({ status }: { status: Status }) {
  const color = status === 'ok' ? '#22c55e' : status === 'running' ? '#eab308' : '#64748b'
  return (
    <span
      className="w-2 h-2 rounded-full flex-shrink-0"
      style={{ background: color, animation: status === 'running' ? 'pulse 1.6s infinite' : undefined }}
      aria-hidden
    />
  )
}

export default function DefensorPage() {
  const { role, demoMode } = useShell()
  const [hasResult, setHasResult] = useState(demoMode)
  const [descricao, setDescricao] = useState('')
  const [canal, setCanal] = useState('PROCON')
  const [tipo, setTipo] = useState('CONSUMERISTA')

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center gap-3">
        <span className="font-mono text-[11px] font-bold px-2 py-1 rounded-[5px] bg-surfaceMuted text-textSecondary">DF</span>
        <h1 className="text-[20px] font-bold text-textPrimary">Defensor</h1>
        <Badge variant="accent" className="ml-auto text-[10px]">AGENTE</Badge>
      </div>

      {role === 'viewer' && <ViewerBanner />}

      <Card padding="md" className="flex flex-col gap-4">
        <Textarea
          label="Descrição do caso"
          placeholder="Descreva a reclamação / o caso (50–5.000 caracteres)…"
          rows={4}
          value={descricao}
          onChange={(e) => setDescricao(e.target.value)}
          charCount={{ current: descricao.length, max: 5000 }}
        />
        <div className="grid grid-cols-4 gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-[12px] font-medium text-textSecondary">Canal</label>
            <select
              value={canal}
              onChange={(e) => setCanal(e.target.value)}
              className="rounded-[8px] border border-borderStrong bg-surface px-3 py-2 text-[13px] text-textPrimary focus:outline-none focus:ring-2 focus:ring-accentTintBorder"
            >
              {CANAIS.map((c) => <option key={c}>{c}</option>)}
            </select>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[12px] font-medium text-textSecondary">Tipo de caso</label>
            <select
              value={tipo}
              onChange={(e) => setTipo(e.target.value)}
              className="rounded-[8px] border border-borderStrong bg-surface px-3 py-2 text-[13px] text-textPrimary focus:outline-none focus:ring-2 focus:ring-accentTintBorder"
            >
              {TIPOS.map((t) => <option key={t}>{t}</option>)}
            </select>
          </div>
          <Input label="Reclamante" placeholder="Nome do reclamante" />
          <Input label="Reclamada" placeholder="Nome da empresa" />
        </div>
        <RbacGate role={role} requires="analyst">
          <Button className="self-start" onClick={() => setHasResult(true)}>Acionar agente</Button>
        </RbacGate>
      </Card>

      {!hasResult && <EmptyState icon="🤖" title="Preencha o formulário e clique em Acionar agente" />}

      {hasResult && (
        <div className="grid grid-cols-3 gap-4">
          {/* Defesa montada */}
          <div className="col-span-2 flex flex-col gap-4">
            {MOCK_SECOES.map((secao) => (
              <Card key={secao.titulo} padding="md">
                <div className="flex items-center justify-between gap-3 mb-3">
                  <SectionLabel>{secao.titulo}</SectionLabel>
                  <div className="flex items-center gap-2">
                    <AntiHallucinationGuard count={secao.precedentes_count} />
                    {secao.precedentes.map((p) => (
                      <VerifiableCitationChip
                        key={p.doc_id}
                        docId={p.doc_id}
                        href={p.href}
                        label={p.doc_id.split('-')[0]}
                      />
                    ))}
                  </div>
                </div>
                <div
                  contentEditable
                  suppressContentEditableWarning
                  className="text-[13px] text-textPrimary leading-relaxed outline-none focus:ring-2 focus:ring-accentTintBorder rounded-[6px] p-2 -m-2"
                >
                  {secao.conteudo}
                </div>
              </Card>
            ))}
            <Button variant="secondary" className="self-start">Exportar .docx</Button>
          </div>

          {/* Rail: feed do agente + enriquecimento */}
          <div className="flex flex-col gap-4">
            {/* Feed ao vivo estilo terminal */}
            <div className="rounded-[10px] overflow-hidden border" style={{ borderColor: '#1a2d4e' }}>
              <div className="flex items-center gap-2 px-3 py-2" style={{ background: '#0c1c33' }}>
                <span className="w-2 h-2 rounded-full" style={{ background: '#475569' }} aria-hidden />
                <span className="w-2 h-2 rounded-full" style={{ background: '#475569' }} aria-hidden />
                <span className="w-2 h-2 rounded-full" style={{ background: '#eab308' }} aria-hidden />
                <span className="ml-2 font-mono text-[10px] tracking-[0.12em] text-[#9fb0c5]">DEFENSOR · AGENT · LIVE</span>
              </div>
              <div className="flex flex-col gap-2.5 px-3 py-3" style={{ background: '#08111f' }}>
                {MOCK_EVENTOS.map((ev, i) => (
                  <div key={i} className="flex items-start gap-2.5">
                    <span className="font-mono text-[10px] text-[#5a6b85] pt-0.5">{ev.ts}</span>
                    <div className="flex flex-col">
                      <div className="flex items-center gap-1.5">
                        <StatusDot status={ev.status} />
                        <span className="font-mono text-[11px] text-[#cdd9ea]">{ev.evento}</span>
                      </div>
                      <span className="font-mono text-[10px] text-[#5a6b85] pl-3.5">{ev.detalhe}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <Card padding="md">
              <SectionLabel className="mb-3">Enriquecimento</SectionLabel>
              <div className="flex flex-col gap-3">
                <div>
                  <p className="text-[11px] text-textMuted mb-1">Canal de protocolo</p>
                  <Badge variant="accent">{canal}</Badge>
                </div>
                <div>
                  <p className="text-[11px] text-textMuted mb-1">Histórico do reclamante</p>
                  <span className="font-mono text-[18px] font-bold text-textPrimary">3</span>
                  <span className="text-[11px] text-textMuted ml-1">casos anteriores</span>
                </div>
                <div>
                  <p className="text-[11px] text-textMuted mb-1">Próximo responsável</p>
                  <Badge variant="MODERADO">agente</Badge>
                </div>
              </div>
            </Card>

            <Card padding="md">
              <SectionLabel className="mb-2">RAG</SectionLabel>
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-riskLow" style={{ animation: 'pulse 1.6s infinite' }} aria-hidden />
                <span className="text-[12px] text-riskLowText font-medium">ChromaDB online</span>
              </div>
              <p className="text-[11px] text-textMuted mt-1">47 precedentes indexados</p>
            </Card>
          </div>
        </div>
      )}
    </div>
  )
}

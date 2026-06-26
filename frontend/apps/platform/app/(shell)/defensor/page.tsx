'use client'
/**
 * Defensor (lente DF) — agente de IA para reclamação de consumidor.
 *
 * Fluxo guiado: Entrada → Execução (feed ao vivo) → Resultado (defesa + rail) → Protocolo.
 * Dados reais via defensorApi.run / .reputacao / .protocolar; em demoMode usa fixtures.
 * Switchers de cenário/estado do protocolo aparecem só em demoMode (recursos de QA).
 */
import { useCallback, useEffect, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import {
  Card, SectionLabel, Badge, Button, Input, Textarea, Skeleton,
  VerifiableCitationChip, AntiHallucinationGuard, EmptyState, ViewerBanner, RbacGate,
  DegradationBanner, Segmented,
  AgentLiveFeed, ProvenanceTag, ProtocolStatusCard, StepIndicator, DEFENSOR_STEPS,
  useStaggeredReveal,
  type AgentEvent, type Provenance, type ProtocolStatus, type ProtocolMode,
} from '@juridico/ui'
import { useShell } from '@/app/context/shell'
import { defensorApi, type ProtocoloResult } from '@/lib/api/defensor'
import { ApiError } from '@/lib/api/client'
import { ApiErrorBanner } from '@/components/ApiErrorBanner'
import { downloadDoc, slugifyFilename } from '@/lib/export/documents'

const DEMO_API_ERROR = new ApiError(503, {
  type: 'https://juridico.io/errors/circuit-breaker',
  title: 'Serviço indisponível',
  status: 503,
  detail: 'Circuit breaker ativo — exibindo o último rascunho válido.',
})

const CANAIS = ['PROCON', 'CONSUMIDOR_GOV', 'OUVIDORIA', 'CONTENCIOSO']
const TIPOS = ['CONSUMERISTA', 'CIVEL', 'TRABALHISTA', 'TRIBUTARIO', 'PREVIDENCIARIO', 'ADMINISTRATIVO']

type Phase = 'entrada' | 'exec' | 'result' | 'proto'
type Scenario = 'normal' | 'juris_vazia' | 'llm_template' | 'erro'
const PHASE_INDEX: Record<Phase, number> = { entrada: 0, exec: 1, result: 2, proto: 3 }

/** título legível (timeline) por chave de evento */
const TITULO_BY_EVENTO: Record<string, string> = {
  'caso.classificado': 'Caso classificado',
  'reclamante.consultado': 'Reclamante consultado',
  'subsidios.solicitando': 'Reunindo subsídios',
  'subsidios.ok': 'Subsídios reunidos',
  'jurisprudencia.match': 'Jurisprudência casada',
  'defesa.redigindo': 'Redigindo defesa',
  'defesa.pronta': 'Defesa pronta',
  'protocolo.preparado': 'Protocolo preparado',
}
const PROVENANCE_BY_VIA: Record<string, Provenance> = { llm: 'ia', parcial: 'parcial', template: 'template' }

export default function DefensorPage() {
  const { role, demoMode } = useShell()
  const isViewer = role === 'viewer'

  const [phase, setPhase] = useState<Phase>('entrada')
  const [maxPhase, setMaxPhase] = useState(0)
  const [treatment, setTreatment] = useState<'terminal' | 'timeline'>('terminal')
  const [scenario, setScenario] = useState<Scenario>('normal')
  const [protoDemo, setProtoDemo] = useState<ProtocolStatus>('SIMULADO')
  const [feedRan, setFeedRan] = useState(false)   // o feed rodou de fato (≠ done inicial)
  const [replayKey, setReplayKey] = useState(0)   // força remount p/ re-animar o fadeup

  const [descricao, setDescricao] = useState('')
  const [canal, setCanal] = useState('CONSUMIDOR_GOV')
  const [tipo, setTipo] = useState('CONSUMERISTA')
  const [reclamante, setReclamante] = useState('')
  const [reclamada, setReclamada] = useState('')

  // ---- Dados reais (TanStack Query) ----
  const runMutation = useMutation({
    mutationFn: () =>
      defensorApi.run({
        descricao, canal, tipo_caso: tipo,
        reclamante: reclamante || 'Reclamante',
        reclamada: reclamada || 'Empresa',
      }),
  })
  const reputacaoQuery = useQuery({
    queryKey: ['defensor-reputacao', reclamada],
    queryFn: () => defensorApi.reputacao(reclamada),
    enabled: !demoMode && reclamada.trim().length >= 3,
  })

  const apiData = runMutation.data

  // ---- View-models (demo ↔ real) ----
  const events: AgentEvent[] = demoMode || !apiData
    ? MOCK_EVENTS
    : apiData.eventos.map((e) => ({
        ts: e.ts, evento: e.evento, detalhe: e.detalhe, status: e.status,
        titulo: TITULO_BY_EVENTO[e.evento] ?? e.evento,
      }))

  const provenance: Provenance = demoMode
    ? (scenario === 'llm_template' ? 'template' : scenario === 'juris_vazia' ? 'parcial' : 'ia')
    : (PROVENANCE_BY_VIA[apiData?.defesa_via ?? 'template'] ?? 'template')

  const secoes: SecaoView[] = demoMode || !apiData
    ? MOCK_SECOES
    : apiData.secoes.map((s) => ({
        titulo: s.titulo,
        conteudo: s.conteudo,
        precedentes_count: s.precedentes.length,
        precedentes: s.precedentes.map((id) => ({ doc_id: id, href: `https://www.cnj.jus.br/datajud/${id}` })),
      }))

  // Reconcilia o agregado com as seções: só "vazio" se o contador E as seções não têm precedentes
  // (evita esconder citações reais por causa de um precedentes_encontrados=0 dessincronizado).
  const jurisEmpty = demoMode
    ? scenario === 'juris_vazia'
    : (apiData?.precedentes_encontrados ?? 0) === 0 && secoes.every((s) => s.precedentes.length === 0)

  const protoMutation = useMutation({
    mutationFn: () =>
      defensorApi.protocolar({
        canal,
        reclamante: reclamante || 'Reclamante',
        reclamada: reclamada || 'Empresa',
        resumo: descricao.trim().length >= 20 ? descricao : 'Reclamação de consumidor conforme caso analisado pelo agente Defensor.',
        defesa: secoes.map((s) => `${s.titulo}\n${s.conteudo}`).join('\n\n'),
      }),
  })

  // ---- Stagger do feed ----
  const { revealed, done, run } = useStaggeredReveal({ total: events.length, auto: false })

  // (re)inicia o feed: marca que rodou de fato, força remount (replay do fadeup) e dispara o stagger.
  const startFeed = useCallback(() => {
    setFeedRan(true)
    setReplayKey((k) => k + 1)
    run()
  }, [run])

  // dispara o stagger quando os dados reais chegam (em demo, é disparado no acionar()).
  useEffect(() => {
    if (!demoMode && runMutation.isSuccess) startFeed()
  }, [demoMode, runMutation.isSuccess, startFeed])

  // feed concluído (após rodar de fato) → libera o passo Resultado.
  // `feedRan` evita o falso-positivo: com auto:false o hook começa done=true e, em modo
  // real, acionar() não chama run() (espera os dados) — sem feedRan o passo 3 abriria já
  // ao clicar Acionar, com o agente ainda pendente.
  useEffect(() => {
    if (phase === 'exec' && feedRan && done && maxPhase < 2) setMaxPhase(2)
  }, [phase, feedRan, done, maxPhase])

  function goto(i: number) {
    if (i <= maxPhase) setPhase(DEFENSOR_STEPS[i].id as Phase)
  }
  function acionar() {
    setPhase('exec'); setMaxPhase((m) => Math.max(m, 1))
    if (demoMode) startFeed()
    else runMutation.mutate()
  }
  function protocolar() {
    setPhase('proto'); setMaxPhase(3)
    if (!demoMode) protoMutation.mutate()
  }

  const showErro = demoMode && phase === 'result' && scenario === 'erro'

  return (
    <div className="flex flex-col gap-5">
      {/* Header da lente */}
      <div className="flex items-center gap-3">
        <span className="font-mono text-[11px] font-bold px-2 py-1 rounded-[5px] bg-surfaceMuted text-textSecondary">DF</span>
        <h1 className="text-[20px] font-bold text-textPrimary">Defensor</h1>
        <Badge variant="accent" dot className="ml-2 text-[10px]">AGENTE</Badge>
      </div>

      {isViewer && <ViewerBanner />}

      <StepIndicator steps={DEFENSOR_STEPS} current={PHASE_INDEX[phase]} maxReached={maxPhase} onNavigate={goto} />

      {/* ---------------- FASE 1 — ENTRADA ---------------- */}
      {phase === 'entrada' && (
        <>
          <Card padding="md" className="flex flex-col gap-4">
            <Textarea
              label="Descrição do caso" rows={5} value={descricao}
              onChange={(e) => setDescricao(e.target.value)}
              charCount={{ current: descricao.length, max: 5000 }}
              placeholder="Descreva a reclamação / o caso (50–5.000 caracteres)…"
            />
            <div className="grid grid-cols-4 gap-3">
              <Select label="Canal" value={canal} onChange={setCanal} options={CANAIS} />
              <Select label="Tipo de caso" value={tipo} onChange={setTipo} options={TIPOS} />
              <Input label="Reclamante" value={reclamante} onChange={(e) => setReclamante(e.target.value)} placeholder="Nome do reclamante" />
              <Input label="Reclamada" value={reclamada} onChange={(e) => setReclamada(e.target.value)} placeholder="Nome da empresa" />
            </div>
            <RbacGate role={role} requires="analyst">
              <Button className="self-start" onClick={acionar}>⚡ Acionar agente</Button>
            </RbacGate>
          </Card>
          <EmptyState icon="🤖" title="Preencha o formulário e clique em Acionar agente" demoMode={demoMode} />
        </>
      )}

      {/* ---------------- FASE 2 — EXECUÇÃO ---------------- */}
      {phase === 'exec' && (
        <div className="flex flex-col gap-3.5">
          <div className="flex items-center justify-between gap-3">
            <Segmented
              aria-label="Tratamento do feed"
              value={treatment}
              onChange={(v) => setTreatment(v as 'terminal' | 'timeline')}
              options={[{ id: 'terminal', label: 'A · Terminal' }, { id: 'timeline', label: 'B · Timeline' }]}
            />
            <div className="flex items-center gap-2">
              <span className="font-mono text-[11px] text-textMuted">{done ? 'concluído' : 'rodando…'}</span>
              <Button variant="secondary" size="sm" onClick={startFeed}>↻ re-rodar</Button>
            </div>
          </div>

          {!demoMode && runMutation.isError && <ApiErrorBanner error={runMutation.error} />}

          {!demoMode && runMutation.isPending
            ? <Skeleton height={300} className="rounded-card max-w-[760px]" />
            : <div className="max-w-[760px]"><AgentLiveFeed key={replayKey} events={events} revealed={revealed} treatment={treatment} /></div>}

          {done && (
            <Button className="self-start" onClick={() => { setMaxPhase((m) => Math.max(m, 2)); setPhase('result') }}>
              Ver resultado →
            </Button>
          )}
        </div>
      )}

      {/* ---------------- FASE 3 — RESULTADO ---------------- */}
      {phase === 'result' && (
        <div className="flex flex-col gap-4">
          {demoMode && (
            <Segmented
              aria-label="Cenário (demo)"
              value={scenario}
              onChange={(v) => setScenario(v as Scenario)}
              options={[
                { id: 'normal', label: 'Normal' },
                { id: 'juris_vazia', label: 'Jurisprudência vazia' },
                { id: 'llm_template', label: 'LLM template' },
                { id: 'erro', label: 'Erro de API' },
              ]}
            />
          )}
          {showErro && <ApiErrorBanner error={DEMO_API_ERROR} />}
          {provenance === 'template' && (
            <DegradationBanner message="Defesa gerada por template — LLM indisponível. Revisar integral." />
          )}
          {jurisEmpty && !showErro && (
            <DegradationBanner message="DataJud não liberado — defesa sem precedentes (degradação graciosa)." />
          )}

          <div className="grid grid-cols-3 gap-4 items-start">
            <div className="col-span-2 flex flex-col gap-4">
              {secoes.map((sec) => {
                const count = jurisEmpty ? 0 : sec.precedentes_count
                return (
                  <Card key={sec.titulo} padding="md">
                    <div className="flex items-center justify-between gap-3 mb-3 flex-wrap">
                      <SectionLabel>{sec.titulo}</SectionLabel>
                      <div className="flex items-center gap-2 flex-wrap">
                        <ProvenanceTag value={provenance} />
                        {count < 3 && <AntiHallucinationGuard count={count} />}
                        {!jurisEmpty && sec.precedentes.map((p) => (
                          <VerifiableCitationChip key={p.doc_id} docId={p.doc_id} href={p.href} label={p.doc_id} />
                        ))}
                      </div>
                    </div>
                    <div contentEditable suppressContentEditableWarning className="text-[13px] text-textPrimary leading-relaxed outline-none focus:ring-2 focus:ring-accentTintBorder rounded-[6px] p-2 -m-2">
                      {sec.conteudo}
                    </div>
                  </Card>
                )
              })}
              <div className="flex items-center gap-3 self-start">
                <Button
                  variant="secondary"
                  onClick={() =>
                    downloadDoc({
                      filename: slugifyFilename(`defesa-${reclamante || 'reclamante'}`),
                      title: 'Defesa do consumidor',
                      subtitle: `${reclamante || 'Reclamante'} × ${reclamada || 'Reclamada'} · ${canal}`,
                      sections: secoes.map((s) => ({ titulo: s.titulo, conteudo: s.conteudo })),
                      footer: 'Gerado pelo agente Defensor (Plataforma Jurídico-Contábil). Revise antes de protocolar.',
                    })
                  }
                >
                  ⤓ Exportar .docx
                </Button>
                <RbacGate role={role} requires="analyst">
                  <Button onClick={protocolar}>Protocolar defesa →</Button>
                </RbacGate>
              </div>
            </div>

            <EnrichmentRail
              canal={canal}
              jurisEmpty={jurisEmpty}
              precedentes={demoMode ? 47 : (apiData?.precedentes_encontrados ?? 0)}
              casosAnteriores={demoMode ? 2 : (apiData?.casos_anteriores ?? 0)}
              proximoResponsavel={demoMode ? 'agente' : (apiData?.proximo_responsavel ?? 'agente')}
              reputacao={demoMode ? DEMO_REPUTACAO : (reputacaoQuery.data?.encontrado ? { empresa: reputacaoQuery.data.reputacao.empresa, total: reputacaoQuery.data.reputacao.total, pct_resolucao: reputacaoQuery.data.reputacao.pct_resolucao, nota_media: reputacaoQuery.data.reputacao.nota_media } : null)}
            />
          </div>
        </div>
      )}

      {/* ---------------- FASE 4 — PROTOCOLO ---------------- */}
      {phase === 'proto' && (
        <div className="max-w-[680px] flex flex-col gap-4">
          {demoMode && (
            <Segmented
              aria-label="Estado do protocolo (demo)"
              value={protoDemo}
              onChange={(v) => setProtoDemo(v as ProtocolStatus)}
              options={(['SIMULADO', 'AGUARDA_CREDENCIAIS', 'ENVIADO', 'FALHA', 'CANAL_NAO_SUPORTADO'] as const).map((s) => ({ id: s, label: s }))}
            />
          )}

          {!demoMode && protoMutation.isError && <ApiErrorBanner error={protoMutation.error} />}
          {!demoMode && protoMutation.isPending && <Skeleton height={180} className="rounded-card" />}

          {demoMode ? (
            <ProtocolStatusCard {...PROTOCOLO_FIXTURE[protoDemo]} canal={canal} enviadoEm="2026-06-25T12:48:21" />
          ) : protoMutation.data ? (
            <ProtocolStatusCard {...mapProtocolo(protoMutation.data)} canal={canal} />
          ) : null}

          <p className="text-[12px] text-textMuted">🔒 Ação externa sensível — confirme o modo (simulação / real) antes de qualquer envio.</p>
        </div>
      )}
    </div>
  )
}

/* —————————————————— tipos/locais —————————————————— */
interface SecaoView {
  titulo: string
  conteudo: string
  precedentes_count: number
  precedentes: { doc_id: string; href: string }[]
}

function mapProtocolo(p: ProtocoloResult) {
  return {
    status: p.status as ProtocolStatus,
    numero: p.numero_protocolo,
    mensagem: p.mensagem,
    modo: (p.modo as ProtocolMode) ?? 'na',
    url: p.url,
    enviadoEm: p.enviado_em,
  }
}

function Select({ label, value, onChange, options }: { label: string; value: string; onChange: (v: string) => void; options: string[] }) {
  return (
    <label className="flex flex-col gap-1.5 text-[12px] font-medium text-textSecondary">
      {label}
      <select value={value} onChange={(e) => onChange(e.target.value)} className="h-10 rounded-[8px] border border-borderStrong bg-surface px-3 text-[13px] text-textPrimary focus:outline-none focus:ring-2 focus:ring-accentTintBorder">
        {options.map((o) => <option key={o}>{o}</option>)}
      </select>
    </label>
  )
}

interface RepView { empresa?: string; total?: number; pct_resolucao?: number; nota_media?: number | null }
function EnrichmentRail({ canal, jurisEmpty, precedentes, casosAnteriores, proximoResponsavel, reputacao }: {
  canal: string; jurisEmpty: boolean; precedentes: number; casosAnteriores: number; proximoResponsavel: string; reputacao: RepView | null
}) {
  return (
    <div className="flex flex-col gap-4">
      <Card padding="md">
        <SectionLabel className="mb-3">Enriquecimento</SectionLabel>
        <div className="flex flex-col gap-3.5">
          <div><p className="text-[11px] text-textMuted mb-1">Canal de protocolo</p><Badge variant="accent">{canal}</Badge></div>
          <div><p className="text-[11px] text-textMuted mb-1">Histórico do reclamante</p><span className="font-mono text-[20px] font-bold text-textPrimary">{casosAnteriores}</span> <span className="text-[11px] text-textMuted">casos anteriores</span></div>
          <div><p className="text-[11px] text-textMuted mb-1">Próximo responsável</p><Badge variant={proximoResponsavel === 'humano' ? 'ALTO' : 'MODERADO'}>🤖 {proximoResponsavel} · handoff opcional</Badge></div>
        </div>
      </Card>
      <Card padding="md">
        <SectionLabel className="mb-2">RAG · precedentes</SectionLabel>
        <p className="text-[12.5px] font-medium" style={{ color: jurisEmpty ? '#76808d' : '#0f5c3a' }}>
          {jurisEmpty ? 'DataJud não liberado' : 'ChromaDB online'}
        </p>
        <p className="text-[11.5px] text-textMuted mt-1">{jurisEmpty ? '0 precedentes · degradação graciosa' : `${precedentes} precedentes indexados`}</p>
      </Card>
      {reputacao && (
        <Card padding="md">
          <SectionLabel className="mb-2">Reputação · Consumidor.gov</SectionLabel>
          <p className="text-[12.5px] font-semibold mb-3 text-textPrimary">{reputacao.empresa ?? '—'}</p>
          <div className="grid grid-cols-3 gap-2.5 font-mono">
            <div><p className="text-[10px] text-textMuted">Reclamações</p><p className="text-[17px] font-bold text-textPrimary">{reputacao.total != null ? reputacao.total.toLocaleString('pt-BR') : '—'}</p></div>
            <div><p className="text-[10px] text-textMuted">Resolução</p><p className="text-[17px] font-bold" style={{ color: '#cf6a1f' }}>{reputacao.pct_resolucao != null ? `${Math.round(reputacao.pct_resolucao * 100)}%` : '—'}</p></div>
            <div><p className="text-[10px] text-textMuted">Nota média</p><p className="text-[17px] font-bold" style={{ color: '#c4382f' }}>{reputacao.nota_media != null ? reputacao.nota_media.toFixed(1).replace('.', ',') : '—'}</p></div>
          </div>
        </Card>
      )}
    </div>
  )
}

/* —————————————————— fixtures (caso de exemplo) —————————————————— */
const MOCK_EVENTS: AgentEvent[] = [
  { ts: '12:48:04', evento: 'caso.classificado', detalhe: 'CONSUMERISTA · cobrança indevida', status: 'ok', titulo: 'Caso classificado' },
  { ts: '12:48:05', evento: 'reclamante.consultado', detalhe: '2 casos anteriores', status: 'ok', titulo: 'Reclamante consultado' },
  { ts: '12:48:06', evento: 'subsidios.solicitando', detalhe: 'crm · contrato + cobranças', status: 'ok', titulo: 'Reunindo subsídios' },
  { ts: '12:48:11', evento: 'subsidios.ok', detalhe: '3 docs anexados', status: 'ok', titulo: 'Subsídios reunidos' },
  { ts: '12:48:12', evento: 'jurisprudencia.match', detalhe: '47 precedentes', status: 'ok', titulo: 'Jurisprudência casada' },
  { ts: '12:48:14', evento: 'defesa.redigindo', detalhe: 'via IA · rascunho v3', status: 'running', titulo: 'Redigindo defesa' },
  { ts: '12:48:18', evento: 'defesa.pronta', detalhe: '4 seções · 12.480 caracteres', status: 'ok', titulo: 'Defesa pronta' },
  { ts: '12:48:19', evento: 'protocolo.preparado', detalhe: 'CONSUMIDOR_GOV · resp.: agente', status: 'pending', titulo: 'Protocolo preparado' },
]

const MOCK_SECOES: SecaoView[] = [
  { titulo: 'DOS FATOS', conteudo: 'A Reclamante contratou plano de internet fibra de 500 Mbps a R$ 99,90/mês. Nas quatro faturas seguintes, foi cobrada por um "Streaming Premium" (R$ 39,90/mês) que jamais contratou, totalizando R$ 159,60, mesmo após três chamados de cancelamento no SAC sem solução.', precedentes_count: 19, precedentes: [{ doc_id: 'STJ-REsp-1.985.xxx', href: 'https://www.cnj.jus.br/datajud/STJ-REsp-1.985.xxx' }, { doc_id: 'TJSP-AC-1023456-2025', href: 'https://www.cnj.jus.br/datajud/TJSP-AC-1023456-2025' }] },
  { titulo: 'DO DIREITO DO CONSUMIDOR', conteudo: 'Aplica-se o CDC (Lei 8.078/90). O art. 42, parágrafo único, assegura a repetição do indébito em dobro nas cobranças indevidas, salvo engano justificável — inexistente no caso.', precedentes_count: 9, precedentes: [{ doc_id: 'STJ-AgInt-789-2024', href: 'https://www.cnj.jus.br/datajud/STJ-AgInt-789-2024' }] },
  { titulo: 'DOS DANOS', conteudo: 'A cobrança indevida e persistente, somada à ameaça de negativação e ao tempo despendido em atendimentos infrutíferos, configura dano moral indenizável.', precedentes_count: 4, precedentes: [{ doc_id: 'TJSP-AC-1023456-2025', href: 'https://www.cnj.jus.br/datajud/TJSP-AC-1023456-2025' }] },
  { titulo: 'DOS PEDIDOS', conteudo: 'Requer-se: a) cancelamento imediato da cobrança; b) repetição em dobro do indébito (R$ 319,20); c) indenização por danos morais; d) baixa de qualquer negativação.', precedentes_count: 0, precedentes: [] },
]

const DEMO_REPUTACAO: RepView = { empresa: 'Telecom Brasil Conecta S.A.', total: 8432, pct_resolucao: 0.71, nota_media: 2.8 }

const PROTOCOLO_FIXTURE: Record<ProtocolStatus, { status: ProtocolStatus; modo: ProtocolMode; numero: string | null; url?: string | null; mensagem: string }> = {
  SIMULADO: { status: 'SIMULADO', modo: 'simulacao', numero: 'SIM-CONSUMIDOR_GOV-1A2B3C4D5E', mensagem: 'Modo simulação — nenhuma submissão real foi feita.' },
  AGUARDA_CREDENCIAIS: { status: 'AGUARDA_CREDENCIAIS', modo: 'real', numero: null, mensagem: 'Modo real ativo, sem credenciais do portal configuradas.' },
  ENVIADO: { status: 'ENVIADO', modo: 'real', numero: 'CG-2026-0098432', url: 'https://www.consumidor.gov.br/', mensagem: 'Protocolado com sucesso no portal.' },
  FALHA: { status: 'FALHA', modo: 'real', numero: null, mensagem: 'Portal retornou 503 (indisponível). Será reprocessado.' },
  CANAL_NAO_SUPORTADO: { status: 'CANAL_NAO_SUPORTADO', modo: 'na', numero: null, mensagem: 'Canal sem protocolo automático — encaminhe para peticionamento manual.' },
}

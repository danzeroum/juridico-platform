'use client'
/**
 * EXEMPLO DE HANDOFF — app/(shell)/defensor/page.tsx
 *
 * Refatora a página atual para consumir os componentes novos:
 *   StepIndicator · AgentLiveFeed · ProvenanceTag · ProtocolStatusCard · EventStatusDot
 * e o hook useStaggeredReveal (stagger + fallback reduced-motion).
 *
 * Fluxo guiado: Entrada → Execução (feed) → Resultado (defesa + rail) → Protocolo.
 * Mantém os contratos de dados (defensorApi). Estados de degradação/erro via `scenario`.
 */
import { useState } from 'react'
import {
  Card, SectionLabel, Badge, Button, Input, Textarea,
  VerifiableCitationChip, AntiHallucinationGuard, EmptyState, ViewerBanner, RbacGate,
} from '@juridico/ui'
import {
  AgentLiveFeed, ProvenanceTag, ProtocolStatusCard, StepIndicator, DEFENSOR_STEPS,
  useStaggeredReveal, type AgentEvent, type Provenance, type ProtocolStatus,
} from '@juridico/ui'
import { useShell } from '@/app/context/shell'
import { defensorApi } from '@/lib/api/defensor'
import { ApiErrorBanner } from '@/components/ApiErrorBanner'

const CANAIS = ['PROCON', 'CONSUMIDOR_GOV', 'OUVIDORIA', 'CONTENCIOSO']
const TIPOS = ['CONSUMERISTA', 'CIVEL', 'TRABALHISTA', 'TRIBUTARIO', 'PREVIDENCIARIO', 'ADMINISTRATIVO']

type Phase = 'entrada' | 'exec' | 'result' | 'proto'
type Scenario = 'normal' | 'juris_vazia' | 'llm_template' | 'erro'

export default function DefensorPage() {
  const { role, demoMode } = useShell()
  const [phase, setPhase] = useState<Phase>('entrada')
  const [maxPhase, setMaxPhase] = useState(0)
  const [treatment, setTreatment] = useState<'terminal' | 'timeline'>('terminal')
  const [scenario, setScenario] = useState<Scenario>('normal')
  const [proto, setProto] = useState<ProtocolStatus | null>(null)

  const [descricao, setDescricao] = useState('')
  const [canal, setCanal] = useState('CONSUMIDOR_GOV')
  const [tipo, setTipo] = useState('CONSUMERISTA')
  const [reclamante, setReclamante] = useState('')
  const [reclamada, setReclamada] = useState('')

  // Dados do agente — aqui mocados; trocar por defensorApi.run(...) (useMutation).
  const events: AgentEvent[] = MOCK_EVENTS
  const { revealed, done, run } = useStaggeredReveal({ total: events.length, auto: false })

  const PHASE_INDEX: Record<Phase, number> = { entrada: 0, exec: 1, result: 2, proto: 3 }
  const goto = (i: number) => { const id = DEFENSOR_STEPS[i].id as Phase; if (i <= maxPhase) setPhase(id) }

  function acionar() {
    setPhase('exec'); setMaxPhase((m) => Math.max(m, 1))
    run() // dispara o stagger (revela os eventos)
  }

  // Quando o feed conclui, libera o passo Resultado.
  if (done && maxPhase < 2) setMaxPhase(2)

  const provenance: Provenance = scenario === 'llm_template' ? 'template' : scenario === 'juris_vazia' ? 'parcial' : 'ia'
  const jurisEmpty = scenario === 'juris_vazia'
  const isViewer = role === 'viewer'

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
              <Input label="Reclamante" value={reclamante} onChange={(e) => setReclamante(e.target.value)} />
              <Input label="Reclamada" value={reclamada} onChange={(e) => setReclamada(e.target.value)} />
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
            <Tabs value={treatment} onChange={(v) => setTreatment(v as any)} options={[['terminal', 'A · Terminal'], ['timeline', 'B · Timeline']]} />
            <Button variant="secondary" size="sm" onClick={run}>↻ re-rodar</Button>
          </div>
          <div className="max-w-[760px]">
            <AgentLiveFeed events={events} revealed={revealed} treatment={treatment} />
          </div>
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
          <Tabs
            value={scenario} onChange={(v) => setScenario(v as Scenario)}
            options={[['normal', 'Normal'], ['juris_vazia', 'Jurisprudência vazia'], ['llm_template', 'LLM template'], ['erro', 'Erro de API']]}
          />
          {scenario === 'erro' && <ApiErrorBanner error={{ title: 'Serviço indisponível', status: 503, detail: 'Circuit breaker ativo — último rascunho válido.', type: 'about:blank' }} demoMode={false} />}

          <div className="grid grid-cols-3 gap-4 items-start">
            <div className="col-span-2 flex flex-col gap-4">
              {MOCK_SECOES.map((sec) => {
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
                    <div contentEditable suppressContentEditableWarning className="text-[13px] leading-relaxed outline-none focus:ring-2 focus:ring-accentTintBorder rounded-[6px] p-2 -m-2">
                      {sec.conteudo}
                    </div>
                  </Card>
                )
              })}
              <div className="flex items-center gap-3 self-start">
                <Button variant="secondary">⤓ Exportar .docx</Button>
                <RbacGate role={role} requires="analyst">
                  <Button onClick={() => { setMaxPhase(3); setProto('SIMULADO'); setPhase('proto') }}>Protocolar defesa →</Button>
                </RbacGate>
              </div>
            </div>

            {/* Rail de enriquecimento — Canal · histórico · responsável · RAG · reputação */}
            <EnrichmentRail canal={canal} jurisEmpty={jurisEmpty} />
          </div>
        </div>
      )}

      {/* ---------------- FASE 4 — PROTOCOLO ---------------- */}
      {phase === 'proto' && proto && (
        <div className="max-w-[680px] flex flex-col gap-4">
          <Tabs
            value={proto} onChange={(v) => setProto(v as ProtocolStatus)}
            options={(['SIMULADO', 'AGUARDA_CREDENCIAIS', 'ENVIADO', 'FALHA', 'CANAL_NAO_SUPORTADO'] as const).map((s) => [s, s])}
          />
          <ProtocolStatusCard {...PROTOCOLO_FIXTURE[proto]} canal={canal} enviadoEm="2026-06-25T12:48:21" />
          <p className="text-[12px] text-textMuted">🔒 Ação externa sensível — confirme o modo (simulação / real) antes de qualquer envio.</p>
        </div>
      )}
    </div>
  )
}

/* —————————————————— helpers locais (substituir pelos primitives reais) —————————————————— */
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

function Tabs({ value, onChange, options }: { value: string; onChange: (v: string) => void; options: [string, string][] }) {
  return (
    <div className="inline-flex gap-0.5 bg-[#f1f3f6] border border-border rounded-[9px] p-0.5">
      {options.map(([id, label]) => (
        <button key={id} onClick={() => onChange(id)} className={`px-3 py-1.5 rounded-[7px] text-[12px] font-semibold ${value === id ? 'bg-surface text-textPrimary shadow-sm' : 'text-textMuted'}`}>
          {label}
        </button>
      ))}
    </div>
  )
}

function EnrichmentRail({ canal, jurisEmpty }: { canal: string; jurisEmpty: boolean }) {
  return (
    <div className="flex flex-col gap-4">
      <Card padding="md">
        <SectionLabel className="mb-3">Enriquecimento</SectionLabel>
        <div className="flex flex-col gap-3.5">
          <div><p className="text-[11px] text-textMuted mb-1">Canal de protocolo</p><Badge variant="accent">{canal}</Badge></div>
          <div><p className="text-[11px] text-textMuted mb-1">Histórico do reclamante</p><span className="font-mono text-[20px] font-bold">2</span> <span className="text-[11px] text-textMuted">casos anteriores</span></div>
          <div><p className="text-[11px] text-textMuted mb-1">Próximo responsável</p><Badge variant="MODERADO">🤖 agente · handoff opcional</Badge></div>
        </div>
      </Card>
      <Card padding="md">
        <SectionLabel className="mb-2">RAG · precedentes</SectionLabel>
        <p className="text-[12.5px] font-medium" style={{ color: jurisEmpty ? '#76808d' : '#0f5c3a' }}>
          {jurisEmpty ? 'DataJud não liberado' : 'ChromaDB online'}
        </p>
        <p className="text-[11.5px] text-textMuted mt-1">{jurisEmpty ? '0 precedentes · degradação graciosa' : '47 precedentes indexados'}</p>
      </Card>
      <Card padding="md">
        <SectionLabel className="mb-2">Reputação · Consumidor.gov</SectionLabel>
        <p className="text-[12.5px] font-semibold mb-3">Telecom Brasil Conecta S.A.</p>
        <div className="grid grid-cols-3 gap-2.5 font-mono">
          <div><p className="text-[10px] text-textMuted">Reclamações</p><p className="text-[17px] font-bold">8.432</p></div>
          <div><p className="text-[10px] text-textMuted">Resolução</p><p className="text-[17px] font-bold" style={{ color: '#cf6a1f' }}>71%</p></div>
          <div><p className="text-[10px] text-textMuted">Nota média</p><p className="text-[17px] font-bold" style={{ color: '#c4382f' }}>2,8</p></div>
        </div>
      </Card>
    </div>
  )
}

/* —————————————————— fixtures (mover p/ a camada de dados) —————————————————— */
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

const MOCK_SECOES = [
  { titulo: 'DOS FATOS', conteudo: 'A Reclamante contratou plano de internet fibra…', precedentes_count: 19, precedentes: [{ doc_id: 'STJ-REsp-1.985.xxx', href: 'https://www.cnj.jus.br/datajud/STJ-REsp-1.985.xxx' }, { doc_id: 'TJSP-AC-1023456-2025', href: 'https://www.cnj.jus.br/datajud/TJSP-AC-1023456-2025' }] },
  { titulo: 'DO DIREITO DO CONSUMIDOR', conteudo: 'Aplica-se o CDC (Lei 8.078/90), art. 42 §ún…', precedentes_count: 9, precedentes: [{ doc_id: 'STJ-AgInt-789-2024', href: 'https://www.cnj.jus.br/datajud/STJ-AgInt-789-2024' }] },
  { titulo: 'DOS DANOS', conteudo: 'A cobrança indevida e persistente configura dano moral…', precedentes_count: 4, precedentes: [{ doc_id: 'TJSP-AC-1023456-2025', href: 'https://www.cnj.jus.br/datajud/TJSP-AC-1023456-2025' }] },
  { titulo: 'DOS PEDIDOS', conteudo: 'Requer-se: cancelamento; repetição em dobro (R$ 319,20); danos morais; baixa de negativação.', precedentes_count: 0, precedentes: [] },
]

const PROTOCOLO_FIXTURE = {
  SIMULADO: { status: 'SIMULADO', modo: 'simulacao', numero: 'SIM-CONSUMIDOR_GOV-1A2B3C4D5E', mensagem: 'Modo simulação — nenhuma submissão real foi feita.' },
  AGUARDA_CREDENCIAIS: { status: 'AGUARDA_CREDENCIAIS', modo: 'real', numero: null, mensagem: 'Modo real ativo, sem credenciais do portal configuradas.' },
  ENVIADO: { status: 'ENVIADO', modo: 'real', numero: 'CG-2026-0098432', url: 'https://www.consumidor.gov.br/', mensagem: 'Protocolado com sucesso no portal.' },
  FALHA: { status: 'FALHA', modo: 'real', numero: null, mensagem: 'Portal retornou 503 (indisponível). Será reprocessado.' },
  CANAL_NAO_SUPORTADO: { status: 'CANAL_NAO_SUPORTADO', modo: 'na', numero: null, mensagem: 'Canal sem protocolo automático — encaminhe para peticionamento manual.' },
} as const

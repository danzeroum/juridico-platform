'use client'
import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import {
  Card, CardHeader, SectionLabel, Badge, VerifiableCitationChip, AntiHallucinationGuard,
  EmptyState, Textarea, Input, Button, ViewerBanner, RbacGate, HeuristicBadge,
  Skeleton, ProblemJsonError,
} from '@juridico/ui'
import type { ProblemJson } from '@juridico/ui'
import { useShell } from '@/app/context/shell'
import { petibotApi } from '@/lib/api/petibot'
import { ApiError } from '@/lib/api/client'

const TIPOS = ['TRABALHISTA', 'CIVEL', 'TRIBUTARIO', 'PREVIDENCIARIO', 'ADMINISTRATIVO', 'CONSUMERISTA']

const MOCK_SECOES = [
  {
    titulo: 'DOS FATOS',
    conteudo: 'O reclamante prestou serviços à reclamada pelo período de 3 (três) anos, de 01/01/2022 a 31/12/2024, na função de Analista de Sistemas, sem o devido registro em Carteira de Trabalho...',
    precedentes: [
      { doc_id: 'TST-RR-001-2023', href: 'https://www.cnj.jus.br/datajud/TST-RR-001-2023', count: 5 },
      { doc_id: 'TRT2-RO-123-2022', href: 'https://www.cnj.jus.br/datajud/TRT2-RO-123-2022', count: 3 },
    ],
    precedentes_count: 8,
  },
  {
    titulo: 'DO DIREITO',
    conteudo: 'A Constituição Federal, em seu art. 7º, assegura ao trabalhador o direito ao registro em CTPS. A ausência de registro caracteriza relação de emprego informal, sujeitando o empregador às sanções previstas na CLT...',
    precedentes: [
      { doc_id: 'TST-AIRR-456-2021', href: 'https://www.cnj.jus.br/datajud/TST-AIRR-456-2021', count: 4 },
    ],
    precedentes_count: 4,
  },
  {
    titulo: 'DAS VERBAS RESCISÓRIAS',
    conteudo: 'Considerando o período trabalhado e os proventos auferidos, o reclamante faz jus às seguintes verbas: aviso prévio proporcional (30 + 3 dias), saldo de salário, 13º salário proporcional...',
    precedentes: [
      { doc_id: 'TRT3-RO-789-2023', href: 'https://www.cnj.jus.br/datajud/TRT3-RO-789-2023', count: 2 },
    ],
    precedentes_count: 2,
  },
  {
    titulo: 'DOS PEDIDOS',
    conteudo: 'Diante do exposto, requer a V. Exa. que seja deferido: a) reconhecimento de vínculo empregatício; b) pagamento de todas as verbas rescisórias; c) anotação na CTPS; d) multa do art. 477 da CLT; e) demais verbas devidas...',
    precedentes: [],
    precedentes_count: 0,
  },
]

interface SecaoView {
  titulo: string
  conteudo: string
  precedentes: { doc_id: string; href: string; count: number }[]
  precedentes_count: number
}

export default function PetiBotPage() {
  const { role, demoMode } = useShell()
  const [descricao, setDescricao] = useState('')
  const [tipo, setTipo] = useState('TRABALHISTA')
  const [poloAtivo, setPoloAtivo] = useState('')
  const [poloPassivo, setPoloPassivo] = useState('')

  const assembleMutation = useMutation({
    mutationFn: () =>
      petibotApi.assemble({
        descricao,
        tipo_acao: tipo,
        polo_ativo: poloAtivo || 'Requerente',
        polo_passivo: poloPassivo || 'Requerido',
      }),
  })

  const hasResult = demoMode || assembleMutation.isSuccess
  const apiData = assembleMutation.data

  const secoes: SecaoView[] = demoMode
    ? MOCK_SECOES
    : apiData
      ? apiData.secoes.map((s) => ({
          titulo: s.titulo,
          conteudo: s.conteudo,
          precedentes: s.precedentes.map((id) => ({
            doc_id: id,
            href: `https://www.cnj.jus.br/datajud/${id}`,
            count: 0,
          })),
          precedentes_count: s.precedentes.length,
        }))
      : []

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center gap-3">
        <span className="font-mono text-[11px] font-bold px-2 py-1 rounded-[5px] bg-surfaceMuted text-textSecondary">PB</span>
        <h1 className="text-[20px] font-bold text-textPrimary">PetiBot</h1>
        <Badge variant="accent" className="ml-auto text-[10px]">RAG</Badge>
      </div>

      {role === 'viewer' && <ViewerBanner />}

      <Card padding="md" className="flex flex-col gap-4">
        <Textarea
          label="Descrição dos fatos"
          placeholder="Descreva os fatos e fundamentos (50–5.000 caracteres)…"
          rows={4}
          value={descricao}
          onChange={(e) => setDescricao(e.target.value)}
          charCount={{ current: descricao.length, max: 5000 }}
        />
        <div className="grid grid-cols-3 gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-[12px] font-medium text-textSecondary">Tipo de ação</label>
            <select
              value={tipo}
              onChange={(e) => setTipo(e.target.value)}
              className="rounded-[8px] border border-borderStrong bg-surface px-3 py-2 text-[13px] text-textPrimary focus:outline-none focus:ring-2 focus:ring-accentTintBorder"
            >
              {TIPOS.map((t) => <option key={t}>{t}</option>)}
            </select>
          </div>
          <Input label="Polo ativo" placeholder="Nome do requerente" value={poloAtivo} onChange={(e) => setPoloAtivo(e.target.value)} />
          <Input label="Polo passivo" placeholder="Nome do requerido" value={poloPassivo} onChange={(e) => setPoloPassivo(e.target.value)} />
        </div>
        <RbacGate role={role} requires="analyst">
          <Button className="self-start" onClick={() => assembleMutation.mutate()} loading={assembleMutation.isPending}>Montar peça</Button>
        </RbacGate>
      </Card>

      {!demoMode && assembleMutation.isError && assembleMutation.error instanceof ApiError && (
        <ProblemJsonError error={assembleMutation.error.problem as ProblemJson} />
      )}

      {assembleMutation.isPending && !demoMode && (
        <div className="grid grid-cols-3 gap-4">
          <Skeleton height={280} className="rounded-card col-span-2" />
          <Skeleton height={280} className="rounded-card" />
        </div>
      )}

      {!hasResult && !assembleMutation.isPending && <EmptyState icon="📄" title="Preencha o formulário e clique em Montar peça" />}

      {hasResult && (
        <div className="grid grid-cols-3 gap-4">
          {/* Editor */}
          <div className="col-span-2 flex flex-col gap-4">
            {secoes.map((secao) => (
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

          {/* Rail: enrichment */}
          <div className="flex flex-col gap-4">
            <Card padding="md">
              <SectionLabel className="mb-3">Enriquecimento</SectionLabel>
              <div className="flex flex-col gap-3">
                <div>
                  <p className="text-[11px] text-textMuted mb-1">Risco da ré (LegalScore)</p>
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-[18px] font-bold text-textPrimary">648</span>
                    <Badge variant="MODERADO">MODERADO</Badge>
                  </div>
                </div>
                <div>
                  <p className="text-[11px] text-textMuted mb-1">Prob. favorável (TaxPredict)</p>
                  <span className="font-mono text-[18px] font-bold text-accent">62%</span>
                </div>
              </div>
            </Card>

            <Card padding="md">
              <SectionLabel className="mb-2">RAG</SectionLabel>
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-riskLow" style={{ animation: 'pulse 1.6s infinite' }} aria-hidden />
                <span className="text-[12px] text-riskLowText font-medium">ChromaDB online</span>
              </div>
              <p className="text-[11px] text-textMuted mt-1">8 precedentes indexados</p>
            </Card>
          </div>
        </div>
      )}
    </div>
  )
}

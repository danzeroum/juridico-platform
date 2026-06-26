'use client'
import { Card, CardHeader, SectionLabel, Badge, Table, Thead, Tbody, Tr, Th, Td, Button } from '@juridico/ui'
import { Download, Shield, Database, Trash2 } from 'lucide-react'
import { downloadJson } from '@/lib/export/documents'

const ROPA = [
  { fonte: 'Receita Federal', classe: 'publico', base: 'Interesse legítimo', finalidade: 'Scoring PJ', lag: '2d' },
  { fonte: 'PGFN', classe: 'publico', base: 'Obrigação legal', finalidade: 'Dívida ativa', lag: '31d' },
  { fonte: 'DATAJUD', classe: 'publico', base: 'Interesse legítimo', finalidade: 'Processos', lag: '4d' },
  { fonte: 'CAGED', classe: 'pessoal', base: 'Obrigação legal', finalidade: 'Emprego', lag: '45d' },
  { fonte: 'SNIS', classe: 'publico', base: 'Interesse legítimo', finalidade: 'Saneamento', lag: '548d' },
]

const CLASS_STYLE: Record<string, string> = {
  publico: 'bg-riskLowBg text-riskLowText',
  pessoal: 'bg-riskMediumBg text-riskMediumText',
  sensivel: 'bg-riskCriticalBg text-riskCriticalText',
}

export default function ConformidadePage() {
  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-[20px] font-bold text-textPrimary">Conformidade · LGPD / DPO</h1>

      {/* Rights cards */}
      <div className="grid grid-cols-3 gap-4">
        {([
          {
            icon: Database, title: 'Acesso', action: 'Exportar dados',
            desc: 'Exportar todos os dados processados deste tenant em JSON.',
            onClick: () => downloadJson('dados-tenant', { tenant: 'demo', exported_at: new Date().toISOString(), ropa: ROPA }),
          },
          {
            icon: Download, title: 'Portabilidade', action: 'Baixar JSON',
            desc: 'Download em formato JSON estruturado (RFC 8259) de todas as decisões.',
            onClick: () => downloadJson('decisoes', { tenant: 'demo', exported_at: new Date().toISOString(), decisoes: [] }),
          },
          {
            icon: Trash2, title: 'Eliminação', action: 'Solicitar eliminação',
            desc: 'Crypto-shredding: chave de tenant rotacionada, dados inacessíveis. Ledger permanece read-only.',
            disabled: true, hint: 'Ação irreversível — requer aprovação do DPO (endpoint em implementação).',
          },
        ] as const).map((right) => (
          <Card key={right.title} padding="md" className="flex flex-col gap-3">
            <div className="flex items-center gap-2">
              <right.icon className="w-4 h-4 text-accent" aria-hidden />
              <SectionLabel>{right.title}</SectionLabel>
            </div>
            <p className="text-[12px] text-textSecondary">{right.desc}</p>
            <Button
              variant="secondary"
              size="sm"
              className="self-start"
              onClick={'onClick' in right ? right.onClick : undefined}
              disabled={'disabled' in right ? right.disabled : undefined}
              title={'hint' in right ? right.hint : undefined}
            >
              {right.action}
            </Button>
          </Card>
        ))}
      </div>

      {/* ROPA table */}
      <Card padding="none">
        <div className="px-5 py-3 border-b border-[#f0f2f5] flex items-center justify-between">
          <SectionLabel>ROPA — Registro de operações de tratamento</SectionLabel>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => downloadJson('trilha-anpd', { exported_at: new Date().toISOString(), ropa: ROPA })}
          >
            <Download className="w-3.5 h-3.5" aria-hidden />
            Exportar trilha (ANPD)
          </Button>
        </div>
        <Table>
          <Thead>
            <Tr><Th>Fonte</Th><Th>Classificação</Th><Th>Base legal</Th><Th>Finalidade</Th><Th>Lag</Th></Tr>
          </Thead>
          <Tbody>
            {ROPA.map((row) => (
              <Tr key={row.fonte}>
                <Td>{row.fonte}</Td>
                <Td>
                  <span className={`px-2 py-0.5 rounded-chip text-[10px] font-medium ${CLASS_STYLE[row.classe]}`}>
                    {row.classe}
                  </span>
                </Td>
                <Td>{row.base}</Td>
                <Td>{row.finalidade}</Td>
                <Td mono>{row.lag}</Td>
              </Tr>
            ))}
          </Tbody>
        </Table>
      </Card>

      {/* Incident playbook */}
      <Card padding="md">
        <SectionLabel className="mb-3">Playbook de incidentes</SectionLabel>
        <div className="flex flex-col gap-2 text-[13px] text-textSecondary">
          {[
            '1. Rotacionar chave de tenant (crypto-shredding)',
            '2. Acionar o DPO em até 24h',
            '3. Colocar Decision Ledger em modo read-only',
            '4. Notificar ANPD em até 72h (art. 48 LGPD)',
            '5. Exportar trilha de auditoria para ANPD',
          ].map((step) => (
            <p key={step}>{step}</p>
          ))}
        </div>
      </Card>
    </div>
  )
}

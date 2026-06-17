'use client'
import { Card, SectionLabel, Badge, Table, Thead, Tbody, Tr, Th, Td, Button, RbacGate } from '@juridico/ui'
import { useShell } from '@/app/context/shell'
import { Shield } from 'lucide-react'

const USERS = [
  { name: 'Admin Principal', email: 'admin@demo.com', role: 'Admin', status: 'ativo' },
  { name: 'Ana Advogada', email: 'ana@demo.com', role: 'Advogado', status: 'ativo' },
  { name: 'Carlos Contador', email: 'carlos@demo.com', role: 'Contador', status: 'ativo' },
  { name: 'Lúcia Leitura', email: 'lucia@demo.com', role: 'Leitura', status: 'inativo' },
]

const ROLE_BADGE: Record<string, string> = { Admin: 'accent', Advogado: 'LOW', Contador: 'MEDIUM', Leitura: 'muted' }

export default function ConfiguracoesPage() {
  const { role } = useShell()

  return (
    <RbacGate
      role={role}
      requires="admin"
      fallback={
        <div className="flex flex-col items-center justify-center min-h-[40vh] gap-3 text-center">
          <Shield className="w-10 h-10 text-textMuted" />
          <p className="text-[15px] font-semibold text-textPrimary">Acesso restrito</p>
          <p className="text-[13px] text-textMuted">Configurações exigem perfil Admin.</p>
        </div>
      }
    >
      <div className="flex flex-col gap-6">
        <h1 className="text-[20px] font-bold text-textPrimary">Configurações</h1>

        {/* Users */}
        <Card padding="none">
          <div className="px-5 py-3 border-b border-[#f0f2f5] flex items-center justify-between">
            <SectionLabel>Usuários e papéis</SectionLabel>
            <Button size="sm">Convidar usuário</Button>
          </div>
          <Table>
            <Thead><Tr><Th>Nome</Th><Th>E-mail</Th><Th>Papel</Th><Th>Status</Th><Th /></Tr></Thead>
            <Tbody>
              {USERS.map((u) => (
                <Tr key={u.email}>
                  <Td>{u.name}</Td>
                  <Td mono>{u.email}</Td>
                  <Td><Badge variant={ROLE_BADGE[u.role] as any}>{u.role}</Badge></Td>
                  <Td><Badge variant={u.status === 'ativo' ? 'LOW' : 'muted'} dot>{u.status}</Badge></Td>
                  <Td><Button variant="ghost" size="sm">Editar</Button></Td>
                </Tr>
              ))}
            </Tbody>
          </Table>
        </Card>

        {/* Rate limit */}
        <Card padding="md">
          <SectionLabel className="mb-3">Rate limit</SectionLabel>
          <div className="flex items-center gap-4">
            <div className="flex flex-col gap-1 flex-1">
              <div className="flex justify-between text-[12px]">
                <span className="text-textSecondary">Requisições por minuto</span>
                <span className="font-mono font-semibold text-textPrimary">42 / 100</span>
              </div>
              <div className="h-2 rounded-full bg-surfaceMuted overflow-hidden">
                <div className="h-2 rounded-full bg-accent" style={{ width: '42%' }} />
              </div>
              <p className="text-[11px] text-textFaint">101ª requisição retorna <span className="font-mono">429 Retry-After</span></p>
            </div>
          </div>
        </Card>

        {/* API keys */}
        <Card padding="md">
          <SectionLabel className="mb-3">Chaves de API</SectionLabel>
          <div className="flex flex-col gap-2">
            {[{ label: 'Produção', key: 'sk_prod_••••••••••••4a2f' }, { label: 'Desenvolvimento', key: 'sk_dev_••••••••••••9c1e' }].map((k) => (
              <div key={k.label} className="flex items-center justify-between gap-3 bg-surfaceMuted rounded-[8px] px-4 py-2.5">
                <span className="text-[12px] text-textSecondary">{k.label}</span>
                <span className="font-mono text-[12px] text-textPrimary">{k.key}</span>
                <Button variant="ghost" size="sm">Rotacionar</Button>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </RbacGate>
  )
}

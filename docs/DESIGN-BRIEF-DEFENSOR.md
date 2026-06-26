# Brief de Design — Fluxo do **Defensor**

Brief focado **somente no fluxo do Defensor** (agente de IA para reclamação de
consumidor). Para o designer produzir wireframes → hi-fi → protótipo no Figma,
usando o design system `@juridico/ui` e os tokens `@juridico/tokens`.

## Decisões fechadas (não precisa redecidir)

| Tema | Decisão |
|---|---|
| Onde vive | **Lente DF integrada** à plataforma existente (shell + sidebar + "entidade é o hub, produtos são lentes"). Navegável pelo menu. |
| Navegação entre as fases | **Fluxo guiado progressivo**: Entrada → Execução → Resultado → Protocolo. Uma fase leva à próxima, com um **indicador de passos** leve no topo (permite voltar a uma fase concluída; não permite pular adiante sem acionar). |
| Feed ao vivo | **Auto-roda** ao entrar na fase de execução (stagger + pulso de status), com botão **"re-rodar"**; respeita `prefers-reduced-motion` (sem animação → aparece como registro estático). |
| Variações a entregar | **2 tratamentos do feed ao vivo** (é o diferencial — ver §5) + **1 versão coesa** das demais telas. |
| Caso de exemplo | Caso consumerista fictício (§2), usado para popular defesa, citações e enriquecimento. |
| Estados transversais | Desenhar **todos**: Viewer/RBAC, 5 estados do Protocolo, Degradação, Erro problem+json, Empty (§6). |

## 1. Contexto e princípios
O Defensor recebe um caso e executa um pipeline agêntico ao vivo
(**classificar → consultar histórico → reunir subsídios → casar jurisprudência →
redigir defesa → preparar/protocolar**) em Procon, Consumidor.gov, Ouvidoria ou
contencioso. Princípios: (1) herdar o design system; (2) sensação **agêntica e ao
vivo**; (3) **confiança/proveniência** (anti-alucinação, citações verificáveis,
selos de frescor, proveniência IA vs template); (4) **honestidade de estado**
(degradação visível, simulação vs real).

## 2. Caso de exemplo (usar em todas as telas)

> **Reclamante:** Mariana Alves de Souza
> **Reclamada:** Telecom Brasil Conecta S.A. — CNPJ 12.345.678/0001-90
> **Canal:** Consumidor.gov · **Tipo:** CONSUMERISTA · **Valor:** R$ 159,60
> **Descrição:** Contratou plano de internet fibra 500 Mbps por R$ 99,90/mês.
> Nas 4 faturas seguintes apareceu cobrança adicional de "Streaming Premium"
> (R$ 39,90/mês) **nunca contratado**, totalizando R$ 159,60. Abriu 3 chamados de
> cancelamento no SAC (protocolos 2026-A4471, 2026-A5588, 2026-A6610), sem
> solução; a cobrança persistiu e houve ameaça de negativação.

**Derivados para preencher as telas:**
- **Classificação:** `CONSUMERISTA · CONSUMIDOR_GOV` — "cobrança indevida".
- **Histórico do reclamante:** 2 casos anteriores.
- **Subsídios (CRM):** contrato/termo de adesão · histórico de cobranças · 3 protocolos de SAC.
- **Jurisprudência (chips):** `STJ-REsp-1.985.xxx` (repetição em dobro, art. 42 §ún. CDC),
  `TJSP-AC-1023456-2025` (serviço não contratado), `STJ-AgInt-789-2024` (dano moral por cobrança indevida persistente).
- **Defesa (seções):** DOS FATOS · DO DIREITO DO CONSUMIDOR · DOS DANOS · DOS PEDIDOS
  (pedidos: cancelamento; **repetição em dobro = R$ 319,20**; danos morais; baixa de negativação).
- **Reputação Consumidor.gov da reclamada:** 8.432 reclamações · 71% resolução · nota 2,8.
- **Protocolo:** número simulado `SIM-CONSUMIDOR_GOV-1A2B3C4D5E`.

## 3. Indicador de passos (topo, persistente)
4 passos: **1 Entrada · 2 Execução · 3 Resultado · 4 Protocolo**. Estado de cada:
pendente / ativo / concluído. Volta livre a passos concluídos; avanço só pela ação
da fase. Compacto, alinhado ao header da lente (badge "AGENTE").

## 4. Fases (fluxo guiado)

### Fase 1 — Entrada
Título "Defensor" + badge "AGENTE". `Textarea` "Descrição do caso" (50–5.000,
com contador), selects **Canal** e **Tipo de caso**, inputs Reclamante e Reclamada,
CTA **"Acionar agente"**. EmptyState 🤖 antes de acionar.

### Fase 2 — Execução (feed ao vivo) — §5
Ao acionar, transiciona para o feed que roda os eventos do caso de exemplo. Ao
concluir (`defesa.pronta`), CTA/auto-avanço para Resultado.

### Fase 3 — Resultado (2 colunas)
- **Coluna principal (defesa):** cards por seção com `SectionLabel`,
  `AntiHallucinationGuard` (contador de fontes) e `VerifiableCitationChip` (chips
  com link p/ DataJud); conteúdo editável inline; **tag de proveniência**
  (IA / parcial / template). Rodapé: "Exportar .docx" + **"Protocolar defesa"**.
- **Rail (enriquecimento):** Canal · Histórico do reclamante (2) · Próximo
  responsável (agente/humano) · status RAG (precedentes) · **Reputação
  Consumidor.gov** (8.432 · 71% · 2,8). Topo opcional: `TrustHeader` + `FreshnessSeal`.

### Fase 4 — Protocolo — §6 (5 estados)
Card "Protocolo · {canal}" com badge de status, número, **modo (simulação/real)**
e mensagem. É uma ação externa sensível — deixar o modo muito claro.

## 5. Feed ao vivo — **2 tratamentos** (o diferencial)
Eventos a representar, em ordem, com status (ok / running-pulsante / pending):
`caso.classificado` → `reclamante.consultado` → `subsidios.solicitando` →
`subsidios.ok` → `jurisprudencia.match` → `defesa.redigindo` (mostra "via IA" /
"parcial" / "template") → `defesa.pronta` → `protocolo.preparado`.

- **Tratamento A — Terminal "AGENT · LIVE"** (escuro, mono): referência do print
  do Sofira. Cabeçalho com 3 dots + "DEFENSOR · AGENT · LIVE"; linhas
  `HH:MM:SS · evento · detalhe`; bolinha de status; stagger de entrada + pulso na
  linha "running". Transmite "máquina trabalhando".
- **Tratamento B — Timeline vertical de etapas** (claro, integrado ao app): cada
  etapa é um passo com ícone, título legível ("Jurisprudência casada — 47
  precedentes"), detalhe e selo de status, conectados por uma linha vertical com
  preenchimento progressivo. Mais "produto", menos "hacker".

Entregar **os dois** para decisão; ambos respeitam `reduced-motion`.

## 6. Estados transversais (desenhar todos)
- **Viewer/RBAC:** mostrar `ViewerBanner`; CTAs "Acionar agente"/"Protocolar"
  ocultos/desabilitados (`RbacGate requires=analyst`).
- **Protocolo — 5 estados (badges):** `SIMULADO` (info/neutro, padrão) ·
  `AGUARDA_CREDENCIAIS` (atenção) · `ENVIADO` (sucesso + nº do portal + link) ·
  `FALHA` (erro + mensagem) · `CANAL_NAO_SUPORTADO` (neutro).
- **Degradação:** jurisprudência vazia (DataJud não liberado → "0 precedentes"
  sem parecer quebrado); defesa "via template" (LLM indisponível); portal off
  (estados de protocolo). Usar `DegradationBanner` quando couber.
- **Erro problem+json:** banner `ApiErrorBanner` (title/detail) acima do conteúdo.
- **Empty:** EmptyState na Entrada antes de acionar.

## 7. Componentes — reuso vs novo
- **Reusar:** Card, Badge, Button, SectionLabel, Input, Textarea, Skeleton,
  RbacGate, ViewerBanner, EmptyState, VerifiableCitationChip,
  AntiHallucinationGuard, FreshnessSeal, TrustHeader, DegradationBanner, ApiErrorBanner.
- **Novos a especificar:** (a) **AgentLiveFeed** (2 tratamentos, §5) +
  **EventStatusDot**; (b) **StepIndicator** (4 passos, §3); (c)
  **ProtocolStatusCard** (5 estados, §6); (d) **ProvenanceTag** (IA/parcial/template).

## 8. Specs visuais (espelhar o que já existe no código)
- **Feed escuro (Tratamento A):** fundo `#08111f` / header `#0c1c33`; texto
  `#cdd9ea`; secundário `#5a6b85`; acento `#2f6fed`. Mono para feed e
  números/protocolos.
- **Status dots:** ok `#22c55e` · running `#eab308` (pulse 1.6s) · pending `#64748b`.
- **App (claro):** usar tokens `@juridico/tokens` (surface, textPrimary/Secondary/Muted,
  borderStrong, accent, riskLow/Moderado/Alto/Critico para badges).
- Tamanhos de referência atuais: título 20px/bold; SectionLabel 10–11px/uppercase;
  corpo 12–13px; número-destaque 18–22px/mono-bold; raios 6–10px.

## 9. Acessibilidade e responsividade
- Contraste AA; `aria-label` em dots/eventos; **respeitar `prefers-reduced-motion`**
  (desligar pulsos/stagger → feed estático); foco visível; navegação por teclado.
- Desktop-first (ferramenta de trabalho); em tablet o rail colapsa abaixo da defesa.

## 10. Entregáveis
1. Wireframes low-fi das 4 fases + estados transversais.
2. Hi-fi coeso (Figma) com os tokens, **+ 2 tratamentos do feed** (§5).
3. Spec dos 4 componentes novos (variantes/estados).
4. Protótipo navegável Entrada → Execução → Resultado → Protocolo.
5. Spec de motion (stagger + pulso) com fallback reduced-motion.

## 11. Referências
Print do Sofira (norte do feed); telas existentes **LegalScore** e **PetiBot**
(consistência de rail/citações); `app/(shell)/defensor/page.tsx` (estrutura
funcional atual — ponto de partida, não o teto).

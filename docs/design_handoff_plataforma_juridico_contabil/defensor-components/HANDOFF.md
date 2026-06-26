# Handoff: Defensor — agente de IA para reclamação de consumidor (lente DF)

> Pacote para o **dev (Claude Code)** implementar o módulo **Defensor** na plataforma
> **Jurídico-Contábil** (`@juridico/ui` + `@juridico/tokens`, Next.js App Router).

---

## 1. Overview

O **Defensor** é uma "lente" (produto, código **DF**) dentro da plataforma onde
*"a entidade é o hub e os produtos são lentes"*. É um **agente de IA** que recebe um
caso de consumidor e executa um pipeline ao vivo:

```
classificar → consultar histórico → reunir subsídios → casar jurisprudência
→ redigir defesa → preparar/protocolar
```

em **Procon, Consumidor.gov, Ouvidoria ou Contencioso**. O diferencial visual é a
**execução ao vivo** (feed de eventos do agente). O fluxo é **guiado e progressivo**
em 4 fases, com um indicador de passos persistente.

Rota alvo: `app/(shell)/defensor/page.tsx` (já existe uma versão funcional — este
pacote é a experiência-alvo de alta fidelidade, não o teto).

---

## 2. Sobre os arquivos deste pacote

Os arquivos aqui são **referências de design**, não código de produção para colar:

- `prototype/Defensor.dc.html` — **protótipo navegável** (look & behavior alvo). É um
  HTML standalone; abra no navegador. Use como fonte da verdade visual/interativa.
- `*.tsx` (AgentLiveFeed, ProtocolStatusCard, EventStatusDot, ProvenanceTag,
  StepIndicator) — **esqueletos React/TS** já no estilo do repo (`cn()`, tokens,
  `lucide-react`, Tailwind), prontos para mover para `packages/ui/src/`.
- `useStaggeredReveal.ts` — hook do stagger do feed.
- `*.stories.tsx`, `defensor-components.test.tsx` — Storybook + Vitest.
- `page.example.tsx` — `defensor/page.tsx` de referência consumindo todos os componentes.

**Tarefa:** recriar o protótipo HTML **dentro do ambiente existente** do repo
(`@juridico/ui`, tokens, Tailwind, React/Next), reaproveitando os primitives já
existentes. Os `.tsx` deste pacote são um ponto de partida fiel — ajuste imports/paths
ao integrar.

---

## 3. Fidelidade: **Alta (hi-fi)**

Cores, tipografia, espaçamentos e interações são finais. Recriar pixel-a-pixel usando
os componentes/tokens do repo. Onde o protótipo usa um valor literal (ex. `#08111f`
do feed), ele corresponde ao que já existe no código atual da página.

---

## 4. Telas / Views

Header da lente (em todas as fases): chip mono `DF` + `<h1>Defensor</h1>` (20px/700) +
`<Badge variant="accent" dot>AGENTE</Badge>`. Quando `role === 'viewer'`: `<ViewerBanner/>`.

**Indicador de passos** (persistente, topo): `StepIndicator` — 4 passos
**1 Entrada · 2 Execução · 3 Resultado · 4 Protocolo**. Estados: pendente / ativo /
concluído. Volta livre a passos concluídos; avanço só pela ação da fase
(`maxReached` trava o pulo adiante).

### Fase 1 — Entrada
- **Propósito:** capturar o caso em poucos campos e acionar o agente.
- **Layout:** `Card` (padding md) com `Textarea` "Descrição do caso" (rows 4–5, contador
  `current/5000`), depois grid de 4 colunas: `select` **Canal**, `select` **Tipo de caso**,
  `Input` **Reclamante**, `Input` **Reclamada**. CTA `<Button>` **"Acionar agente"**
  envolto em `<RbacGate requires="analyst">`.
- **Vazio:** abaixo do card, `<EmptyState icon="🤖" title="Preencha o formulário e clique
  em Acionar agente" />` (com `demoMode` → linha mono "modo limpo · sem conexão com as APIs").
- **Viewer:** CTA oculto (RbacGate) → mostra chip "exige perfil Analista".
- **Canal options:** `PROCON · CONSUMIDOR_GOV · OUVIDORIA · CONTENCIOSO`.
- **Tipo options:** `CONSUMERISTA · CIVEL · TRABALHISTA · TRIBUTARIO · PREVIDENCIARIO · ADMINISTRATIVO`.

### Fase 2 — Execução (feed ao vivo) — **o coração visual**
Ao acionar, transiciona para o feed que roda os eventos. Controles no topo: segmented
**A · Terminal / B · Timeline**, status (`rodando…` / `concluído`) e botão **re-rodar**.
Ao concluir (`done`), CTA **"Ver resultado →"** (libera passo 3).

Entregar **os 2 tratamentos** (decisão do time):
- **A — Terminal "AGENT · LIVE"** (escuro): cabeçalho `#0c1c33` com 3 dots +
  `DEFENSOR · AGENT · LIVE`; corpo `#08111f`; linhas mono `HH:MM:SS · evento · detalhe`
  com `EventStatusDot`. Stagger de entrada + pulso na linha running. Rodapé com legenda
  ok/running/pending. Largura máx. 760px.
- **B — Timeline vertical** (clara, integrada): cada etapa = nó (✓/nº) + título legível
  ("Jurisprudência casada"), detalhe e selo de status, conectados por linha vertical com
  preenchimento progressivo.

**Sequência de eventos** (caso de exemplo, §7):
`caso.classificado` → `reclamante.consultado` → `subsidios.solicitando` →
`subsidios.ok` → `jurisprudencia.match` → `defesa.redigindo` (mostra "via IA") →
`defesa.pronta` → `protocolo.preparado`.

### Fase 3 — Resultado (2 colunas: defesa 1.65fr + rail 1fr)
- **Coluna principal (defesa):** um `Card` por seção (**DOS FATOS · DO DIREITO DO
  CONSUMIDOR · DOS DANOS · DOS PEDIDOS**). Cabeçalho de cada card: `SectionLabel` +
  (à direita) `ProvenanceTag` + `AntiHallucinationGuard` (aparece quando precedentes < 3)
  + `VerifiableCitationChip`(s) com link para DataJud (`cnj.jus.br/datajud/<id>`).
  Corpo **editável inline** (`contentEditable`). Rodapé: `Button` **"Exportar .docx"**
  (secondary) + `Button` **"Protocolar defesa →"** (RbacGate analyst).
- **Rail (enriquecimento):** cards de **Canal** (Badge), **Histórico do reclamante** (nº),
  **Próximo responsável** (agente/humano · handoff), **RAG** (status + nº precedentes
  indexados) e **Reputação Consumidor.gov** (reclamações · % resolução · nota média).
  Topo opcional: `TrustHeader` com `FreshnessSeal`.
- **Seletor de Cenário** (degradação) no topo da fase: `Normal · Jurisprudência vazia ·
  LLM template · Erro de API` (ver §6).

### Fase 4 — Protocolo (`ProtocolStatusCard`)
- Indicador de **modo** (simulação/real) em destaque (ação externa sensível).
- Switcher dos **5 estados**; card "Protocolo · {canal}" com badge, número, mensagem,
  modo, e link quando ENVIADO (ver §6).

### View extra do protótipo — "Handoff dev"
O HTML tem uma aba **Handoff dev** (toggle no header) que documenta visualmente:
estado de loading (Skeleton), spec dos componentes novos, variantes do `ApiErrorBanner`
(429/501/503), spec de motion e tokens. É material de referência — não precisa virar tela.

---

## 5. Interações & comportamento

- **Navegação de fases:** `StepIndicator.onNavigate(i)` só permite `i <= maxReached`.
  Acionar agente → fase exec + `maxReached≥1` + dispara o feed. Feed concluído → `maxReached≥2`.
  Protocolar → fase proto + `maxReached≥3`.
- **Feed (stagger):** revela 1 evento a cada **620ms** (`useStaggeredReveal`). A linha mais
  recente fica `running` (pulsa); as anteriores viram `ok`. Re-rodar reinicia.
- **Pulso de status:** dot `running` → `pulse 1.4s ease-in-out infinite`; selos/banners
  defasados → `pulse 1.6s`.
- **Entrada de linha (terminal):** `fadeup .32s ease` — **só `transform`**, nunca `opacity`
  (para a linha não ficar invisível se a animação for interrompida).
- **Editável inline:** seções da defesa com `contentEditable` + focus ring `accentTintBorder`.
- **Citações:** abrem o DataJud em nova aba (`target=_blank rel=noopener`).
- **`prefers-reduced-motion: reduce`:** desliga stagger (revela tudo de uma vez) e todos
  os pulsos. Implementado via `motion-safe:` (classes) + checagem no hook.
- **Responsivo:** desktop-first (ferramenta de trabalho). Em tablet o rail colapsa abaixo
  da coluna de defesa (1 coluna).

---

## 6. Estados (desenhar todos)

**Protocolo — 5 estados** (badge / número / mensagem / modo):
| Estado | Badge (variant) | Número | Modo | Observação |
|---|---|---|---|---|
| `SIMULADO` (padrão) | accent | `SIM-CONSUMIDOR_GOV-1A2B3C4D5E` | simulação | nenhuma submissão real |
| `AGUARDA_CREDENCIAIS` | MODERADO (âmbar) | — | real | modo real sem credenciais |
| `ENVIADO` | BAIXO (verde) | `CG-2026-0098432` + link | real | nº do portal + link |
| `FALHA` | ALTO (vermelho) | — | real | portal 503 · reprocessar |
| `CANAL_NAO_SUPORTADO` | muted (neutro) | — | — | encaminhar manual |

**Degradação graciosa:**
- **Jurisprudência vazia** (DataJud não liberado) → "0 precedentes" sem parecer quebrado;
  `AntiHallucinationGuard` em todas as seções; `ProvenanceTag` = `parcial`; RAG "0 indexados";
  `DegradationBanner`.
- **LLM template** (LLM indisponível) → `ProvenanceTag` = `template`; `DegradationBanner`
  "defesa gerada por template — revisar integral".
- **Portal off** → estados de protocolo acima.

**Erro problem+json:** `ApiErrorBanner` acima do conteúdo. Temas por status:
- `429` rate limit (âmbar + retry_after) · `501` não liberado/PD-06 (neutro) ·
  `503` circuit breaker (vermelho).

**Viewer/RBAC:** `<ViewerBanner/>`; CTAs "Acionar agente"/"Protocolar" ocultos via
`<RbacGate requires="analyst">`.

**Loading:** Skeleton (2 cards de defesa + rail) enquanto `defensorApi.run` pende (modo limpo).

**Empty:** `EmptyState 🤖` na Entrada antes de acionar.

---

## 7. Caso de exemplo (popular todas as telas)

> **Reclamante:** Mariana Alves de Souza · **Reclamada:** Telecom Brasil Conecta S.A.
> (CNPJ 12.345.678/0001-90) · **Canal:** Consumidor.gov · **Tipo:** CONSUMERISTA ·
> **Valor:** R$ 159,60.
> **Descrição:** plano de fibra 500 Mbps a R$ 99,90/mês; nas 4 faturas seguintes,
> cobrança de "Streaming Premium" (R$ 39,90/mês) nunca contratado (total R$ 159,60);
> 3 chamados de SAC (2026-A4471, 2026-A5588, 2026-A6610) sem solução; ameaça de negativação.

Derivados: **classificação** "cobrança indevida"; **histórico** 2 casos; **subsídios**
contrato + cobranças + 3 protocolos SAC (3 docs); **jurisprudência** `STJ-REsp-1.985.xxx`
(art. 42 §ún CDC), `TJSP-AC-1023456-2025` (serviço não contratado), `STJ-AgInt-789-2024`
(dano moral); **pedidos** cancelamento + **repetição em dobro R$ 319,20** + danos morais +
baixa de negativação; **reputação** 8.432 reclamações · 71% resolução · nota 2,8;
**protocolo simulado** `SIM-CONSUMIDOR_GOV-1A2B3C4D5E`.

(Fixture pronto em `fixtures.ts` e `page.example.tsx`.)

---

## 8. State management (página)

```ts
phase: 'entrada' | 'exec' | 'result' | 'proto'   // fase atual
maxPhase: number                                  // passo mais avançado alcançado (trava avanço)
treatment: 'terminal' | 'timeline'                // tratamento do feed
scenario: 'normal' | 'juris_vazia' | 'llm_template' | 'erro'  // degradação/erro
proto: ProtocolStatus | null                      // estado do protocolo
{ descricao, canal, tipo, reclamante, reclamada } // form
revealed, done (← useStaggeredReveal)             // stagger do feed
```
Dados reais via `defensorApi.run` / `.reputacao` / `.protocolar` (ver `lib/api/defensor.ts`),
com `useMutation`/`useQuery` (TanStack Query, como nas outras lentes). `role`, `demoMode`
vêm de `useShell()`.

---

## 9. Design tokens (`@juridico/tokens`)

- **accent** `#2f6fed` (hover `#2660d8`) · tint `#e8effe`/`#eef4fe`/`#cddcf8`
- **sidebar** `#0c1c33` · linhas `#1a2d4e`/`#21385f`
- **app bg** `#f5f6f8` · surface `#fff` · surfaceMuted `#f7f8fa` · borders `#e7eaee`/`#e3e7ec`/`#d3d8df`
- **texto** primary `#13181f` · secondary `#48515e` · muted `#76808d` · faint `#9aa3af` · sectionLabel `#6b7480`
- **feed (escuro)** bg `#08111f` · header `#0c1c33` · texto `#cdd9ea` · secundário `#5a6b85`
- **status dots** ok `#22c55e` · running `#eab308` (pulse 1.6s) · pending `#64748b`
- **risco** Baixo `#1f8a5b`/bg `#e7f4ee` · Moderado `#caa215`/bg `#fbf4e2`/tx `#7a5800` ·
  Alto `#cf6a1f`/bg `#fbe9da` · Crítico `#c4382f`/bg `#fae3e1`
- **tipografia** Sans **IBM Plex Sans**; Mono **IBM Plex Mono** (feed, números, protocolos).
  Título 20px/700 · SectionLabel 10–11px uppercase tracking .07em · corpo 12–13px ·
  número-destaque 17–20px mono-bold.
- **raios** 6–12px · **motion** stagger 620ms · pulse 1.4–1.6s · fade .32s (só transform).

---

## 10. Componentes — reuso vs novo

**Reusar (já no `@juridico/ui`):** Card, Badge, Button, SectionLabel, Input, Textarea,
Skeleton, RbacGate, ViewerBanner, EmptyState, VerifiableCitationChip,
AntiHallucinationGuard, FreshnessSeal, TrustHeader, DegradationBanner, ApiErrorBanner.

**Novos (esqueletos neste pacote → `packages/ui/src/patterns/`):**
`AgentLiveFeed` (+ `EventStatusDot`), `StepIndicator`, `ProtocolStatusCard`, `ProvenanceTag`.
Hook: `useStaggeredReveal` → `packages/ui/src/hooks/`. Registrar o keyframe `fadeup` no
Tailwind/globals. Plugar exports no `index.ts` raiz (ver `index.ts`).

---

## 11. Arquivos deste pacote

```
defensor-components/
├── HANDOFF.md                      ← este documento (autossuficiente)
├── README.md                       ← guia técnico dos componentes (exports, motion, a11y)
├── index.ts                        ← barrel
├── fixtures.ts                     ← MOCK_EVENTS (caso de exemplo)
├── EventStatusDot.tsx
├── AgentLiveFeed.tsx               ← 2 tratamentos (terminal/timeline)
├── ProtocolStatusCard.tsx          ← 5 estados
├── ProvenanceTag.tsx               ← ia/parcial/template
├── StepIndicator.tsx               ← 4 passos (+ DEFENSOR_STEPS)
├── useStaggeredReveal.ts           ← stagger + fallback reduced-motion
├── AgentLiveFeed.stories.tsx
├── ProtocolStatusCard.stories.tsx
├── Selos.stories.tsx
├── defensor-components.test.tsx
├── page.example.tsx                ← defensor/page.tsx de referência
└── prototype/
    ├── Defensor.dc.html            ← protótipo navegável (abrir no navegador)
    └── support.js
```

## 12. Assets

Sem imagens próprias. Ícones via `lucide-react` (já no repo) — no protótipo HTML há
glifos unicode (⚡ ↻ ✓ 🔒 🤖) como placeholders; trocar pelos ícones lucide equivalentes
na implementação. Fontes IBM Plex (Sans/Mono) via Google Fonts, como no resto da app.

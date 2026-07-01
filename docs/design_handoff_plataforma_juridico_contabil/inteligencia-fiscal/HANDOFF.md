# Handoff: Inteligência Jurimétrica + Fiscal + Admin Ingestão

> Pacote para o **dev (Claude Code)** implementar 10 telas novas na plataforma
> **Jurídico-Contábil** (`juridico-platform`): 7 lentes de Inteligência/Jurimetria,
> a lente Fiscal e o console Admin de Ingestão. Next.js App Router + `@juridico/ui` +
> `@juridico/tokens`; backends em `services/`.

---

## 1. Overview

A plataforma segue o padrão *"a entidade (CNPJ) é o hub, cada produto é uma lente"*.
Estas 10 telas adicionam a camada de **inteligência jurimétrica** (análise agregada de
tribunais/classes/assuntos), a lente **Fiscal** (NCM/ICMS) e o console **Admin de
observabilidade da ingestão**. Todas herdam o shell existente (sidebar de lentes,
topbar com RBAC/rate-limit/demo, tooltips de orientação).

**Princípios inegociáveis (herdados do produto):**
1. **Herdar o design system** `@juridico/ui` e os tokens — consistência com LegalScore/Defensor.
2. **Honestidade epistêmica**: todo indicador estatístico traz selo **heurístico** (◔) e
   disclaimer "não é aconselhamento jurídico". Degradação graciosa sempre visível.
3. **Proveniência**: chip de **fonte** (DATAJUD/ABJ/BLEND/TIPI…) em cada dado e referência
   ao **Decision Ledger** (prova de origem) onde há decisão registrável.
4. **LGPD por design**: análise sempre **agregada** (tribunal+classe). **Perfilamento de
   juiz individual é vedado** — o grão mínimo é órgão julgador, nunca magistrado.

---

## 2. Sobre os arquivos deste pacote

- `prototype/Plataforma.dc.html` — **protótipo navegável** com as 10 telas (fonte da verdade
  visual/interativa). Abra no navegador, faça login e navegue pela sidebar nos grupos
  **INTELIGÊNCIA · JURIMETRIA**, **PRODUTOS · Fiscal** e **ADMIN · DADOS**.
- `HANDOFF.md` — este documento (autossuficiente).
- `api-contracts.md` — assinaturas de request/response por tela, alinhadas aos serviços.

**Tarefa:** implementar cada tela como uma rota em `app/(shell)/<lente>/page.tsx` no app
`frontend/apps/platform`, consumindo `lib/api/<lente>.ts` (TanStack Query) e os primitives
de `@juridico/ui`. O protótipo mostra layout, estados e microcopy finais.

---

## 3. Fidelidade: **Alta (hi-fi)**

Cores, tipografia, espaçamentos e componentes são finais e vêm dos tokens do repo.
Recriar com os componentes existentes; onde o protótipo usa um valor literal, ele
corresponde a um token (ver §9 do handoff do Defensor / `packages/tokens`).

---

## 4. Rotas / navegação

Adicionar ao shell três blocos na sidebar (o protótipo já mostra a ordem):

```
INTELIGÊNCIA · JURIMETRIA
  JM  /jurimetria          Jurimetria
  KG  /knowledge-graph     Knowledge Graph
  FC  /forecasting         Forecasting
  CP  /chamber-profiler    Chamber Profiler
  SO  /second-opinion      Second Opinion
  ST  /settlement          Settlement Optimizer
  EW  /early-warning       Early Warning
PRODUTOS · LENTES
  FI  /fiscal              Fiscal            (junto às outras lentes)
ADMIN · DADOS  (só role=admin)
  IG  /admin/ingestao      Ingestão & Saúde de Dados
```

Cada item de nav tem um `data-tip` (tooltip de orientação) — texto no protótipo.
O grupo ADMIN só aparece para `role === 'admin'` (via `useShell()`).

---

## 5. Telas (layout, dados, estados)

Cabeçalho comum de toda lente: chip mono do código (JM, KG…) + `<h1>` + badge de status
(**◔ heurístico** para analíticos, ou tag descritiva) + parágrafo com o disclaimer.

### 5.1 Jurimetria — `JM`
- **Propósito:** indicadores agregados por tribunal/classe/assunto.
- **Layout:** barra de filtros (Tribunal, Classe, Assunto, Fonte) → **tabela de indicadores**
  (tribunal · classe · assunto · **chip de fonte** · nº processos · duração mediana ·
  **barra de congestionamento** colorida por faixa · % provimento) → 2 painéis:
  *Congestionamento por classe* (barras) e *Duração — mediana + faixa IQR p25–p75* → faixa
  escura **Market Intelligence** (segmentos: nº, ticket médio, soma) com selo do Ledger.
- **Estados:** vazio ("0 segmentos" sem quebrar); fonte defasada → chip de fonte em âmbar.

### 5.2 Knowledge Graph — `KG`
- **Propósito:** processos de uma empresa + rede de co-litigância (CNPJ↔CNPJ).
- **Layout:** busca por CNPJ → 3 stat cards (empresas, processos, arestas) → **banner de
  litigância predatória** quando aplicável → 2 colunas: *rede de vizinhos* (nome, CNPJ,
  ramos, nº em comum, **badge de relação** ISOLADO/OCASIONAL/RECORRENTE/PREDATÓRIO) e
  *processos ligados* (nº CNJ com link).
- **Estados:** rede vazia (empresa sem co-litigância) → mostrar "nenhum vizinho" gracioso.

### 5.3 Forecasting — `FC`
- **Propósito:** projeção de volume futuro de ações.
- **Layout:** filtros (Tribunal, Classe, Assunto, Horizonte) → card com **gráfico** (linha
  sólida = histórico, tracejada = projeção; SVG) + lista dos passos projetados com **banda
  de incerteza** `[lo–hi]` → badge de tendência (CRESCENTE/ESTÁVEL/DECRESCENTE) + inclinação.
- **Estado de degradação:** exige ≥3 períodos; abaixo disso, mensagem "dados insuficientes".

### 5.4 Chamber Profiler — `CP`
- **Propósito:** perfil **agregado** do órgão (tribunal+classe). **Nunca por juiz.**
- **Layout:** aviso LGPD destacado → filtros (Tribunal, Classe) → 3 **donuts** de faixa
  (Provimento, Congestionamento, Duração) com rótulo de faixa (ex.: MUITO_CONGESTIONADO).
- **Regra:** o request **não aceita** identificador de magistrado; grão mínimo tribunal+classe.

### 5.5 Second Opinion — `SO`
- **Propósito:** parecer de consenso combinando LegalScore + TaxPredict + jurimetria.
- **Layout:** coluna de inputs (3 sinais) → coluna de resultado: **donut de favorabilidade**,
  **veredito** (FAVORÁVEL/INCERTO/DESFAVORÁVEL), **concordância** dos sinais + breakdown
  normalizado (barras). Rodapé: Ledger **sem PII**.

### 5.6 Settlement Optimizer — `ST`
- **Propósito:** zona de acordo (ZOPA) por análise de decisão.
- **Layout:** inputs (valor da causa, prob. favorável, pct provimento, custos) → resultado:
  **recomendação** (ACORDAR/LITIGAR) + **barra ZOPA** (faixa de acordo vs valor da causa) +
  valores esperados autor/réu. Quando não há ZOPA, estado "sem sobreposição — litigar".

### 5.7 Early Warning — `EW`
- **Propósito:** detectar surtos de volume e picos de congestionamento.
- **Layout:** filtros → lista de **gatilhos** com **severidade** (CRITICAL/HIGH/MEDIUM/LOW),
  tipo (SURTO_VOLUME / PICO_CONGESTIONAMENTO), descrição e **métrica** (z-score, taxa).
- **Estado vazio:** "nenhum gatilho ativo" (verde), sem parecer quebrado.

### 5.8 Fiscal — `FI` (grupo PRODUTOS)
- **Propósito:** triagem NCM/ICMS de um item + enriquecimento de planilha em lote.
- **Layout:** coluna de triagem (descrição, UF origem/destino) → resultado: **NCM sugerido**
  + confiança + chip de fonte (TIPI) + bloco ICMS (interna, efetiva com FCP, DIFAL) +
  fundamento legal + Ledger. Abaixo: **job em lote** (JobProgress + tabela item/NCM/conf/status
  + download .xlsx com expiração).
- **Estados:** conflito de alíquota (badge âmbar "rever"); baixa confiança → status "rever".

### 5.9 Ingestão & Saúde de Dados — `IG` (ADMIN)
- **Propósito:** operar/observar o pipeline por fonte.
- **Layout:** tabela por fonte: **frescor** (banda fresco/recente/defasado por lag em dias),
  **circuit breaker** (CLOSED/HALF_OPEN/OPEN), **reconciliação** (records in / out / % perda
  colorida), último run, botão **disparar** (só admin).
- **Regra:** CB OPEN pausa a fonte após falhas consecutivas; disparo manual exige admin.

---

## 6. Estados transversais (desenhar em todas)

- **Heurístico:** selo ◔ + disclaimer no header dos analíticos (JM, FC, CP, SO, ST, EW).
- **Degradação graciosa:** fonte offline → chip de fonte âmbar; dados insuficientes → mensagem;
  jurisprudência/rede vazia → "0 …" sem layout quebrado.
- **RBAC:** ADMIN (IG) só para `admin`; ações de disparo/lote gated por `RbacGate`.
  Viewer vê leitura, sem CTAs.
- **Erro problem+json:** `ApiErrorBanner` acima do conteúdo (429/501/503) — mesmo padrão do Defensor.
- **Loading:** Skeleton nas tabelas/cards enquanto a query pende.
- **Ledger:** onde há decisão registrável (JM Market Intel, SO, ST, FI), mostrar
  `req #<PREFIXO>-AAAA-NNNN` e nota "sem PII" quando aplicável.

---

## 7. Componentes — reuso vs novo

**Reusar (`@juridico/ui`):** Card, Badge, Button, SectionLabel, Input, Textarea, Select,
Table/DataTable, Skeleton, RbacGate, ViewerBanner, EmptyState, ApiErrorBanner, FreshnessSeal,
JobProgress (se existir; senão barra simples). Tooltip de orientação = utilitário já usado no shell.

**Novos a especificar (pequenos, específicos das telas):**
- `SourceChip` — chip mono de fonte (DATAJUD/ABJ/BLEND/TIPI/CONFAZ) com cor por origem.
- `HeuristicSeal` — selo ◔ "heurístico" do header analítico.
- `FaixaBadge` — badge de faixa categórica (ex.: MUITO_CONGESTIONADO, PROVIMENTO_MODERADO).
- `GaugeDonut` — donut de proporção (conic-gradient) com valor central + rótulo de faixa (CP, SO).
- `ZopaBar` — barra da zona de acordo com marcadores de faixa, sugerido e valor da causa (ST).
- `RelationBadge` — badge de relação de co-litigância ISOLADO→PREDATÓRIO (KG).
- `CircuitBreakerBadge` / `FreshnessBand` — estados do console de ingestão (IG).

> Vários desses são variações finas de `Badge`; avaliar promover a `Badge variant=…`
> em vez de componentes separados.

---

## 8. Design tokens

Idênticos ao resto da plataforma (ver `packages/tokens`): accent `#2f6fed`, sidebar
`#0c1c33`, superfícies `#fff`/`#f7f8fa`, bordas `#e7eaee`/`#e3e7ec`, texto `#13181f`/`#48515e`/
`#76808d`/`#9aa3af`. **Faixas de risco/severidade** (reaproveitar): Baixo `#1f8a5b`/`#e7f4ee` ·
Moderado `#caa215`/`#fbf6e9`/tx `#7a5800` · Alto `#cf6a1f`/`#fbe9da` · Crítico `#c4382f`/`#fae3e1`.
Tipografia: **IBM Plex Sans** (UI) + **IBM Plex Mono** (números, códigos, NCM, protocolos, Ledger).

---

## 9. State management (por página)

Padrão das lentes existentes: filtros em `useState`, dados via `useQuery(['<lente>', filtros],
() => api.<lente>(filtros))`. Mutations (disparar ingestão, rodar lote fiscal) via `useMutation`.
`role`/`demoMode` de `useShell()`. Em `demoMode`, servir as fixtures do protótipo (mesmos números).

---

## 10. Arquivos deste pacote

```
inteligencia-fiscal/
├── HANDOFF.md              ← este documento
├── api-contracts.md        ← contratos request/response por tela
└── prototype/
    ├── Plataforma.dc.html  ← protótipo navegável (abrir no navegador)
    └── support.js
```

## 11. Assets

Sem imagens. Gráficos (Forecasting) e donuts (CP/SO) são SVG/conic-gradient inline — na
implementação, usar a lib de charts já adotada no repo (ou manter SVG leve). Ícones via
`lucide-react`. Fontes IBM Plex via o mesmo carregamento do resto do app.

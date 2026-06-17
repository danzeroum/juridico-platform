# Handoff: Plataforma Jurídico-Contábil — Interface (8 produtos + shell)

## Overview

Interface completa de uma plataforma SaaS B2B multi-tenant de IA aplicada ao direito e à contabilidade brasileira. Reúne **8 produtos** sobre uma base compartilhada de dados públicos (DATAJUD, PGFN, Receita, SICONFI, CAGED, SNIS, IBGE, PNCP, INEP, ComexStat…), o mesmo motor de scoring/anomalia e a mesma trilha de auditoria criptográfica (Decision Ledger / Merkle).

A tese do produto — e o eixo de todas as decisões de design — é **confiança auditável**: cada número exibido carrega data da fonte, defasagem (lag), rótulo "heurística × calibrado", intervalo de incerteza e prova de integridade verificável. Honestidade epistêmica é elemento visual de primeira classe, nunca letra miúda. Dado parcial/desatualizado é um estado calmo e desenhado, não um erro.

A navegação é organizada **por entidade, não por produto**: uma PJ (CNPJ) ou município é o hub, e os 8 produtos são *lentes* sobre essa entidade.

Repositório-alvo: `juridico-platform` — frontend **Next.js 14 (App Router) + TanStack Query**, monorepo (`frontend/apps/*` + `frontend/packages/`). Hoje os apps são placeholders; este handoff é o green field de UI.

---

## About the Design Files

Os arquivos deste bundle são **referências de design feitas em HTML** — um protótipo navegável que mostra aparência e comportamento pretendidos, **não código de produção para copiar**.

- `Plataforma.dc.html` — o protótipo. É um **"Design Component"**: um arquivo único onde o template (markup com `{{ holes }}` e `<sc-if>`/`<sc-for>`) e uma classe de lógica (`class Component extends DCLogic`) são renderizados por um runtime de protótipo.
- `support.js` — o runtime do protótipo (carrega React/Babel de CDN e interpreta o `<x-dc>`). **Não vá para produção. Ignore-o** na implementação; serve apenas para abrir o `.html` no navegador e ver o design.

**A tarefa:** recriar estas telas no ambiente do `juridico-platform` (Next.js 14 + TanStack Query + componentes em `frontend/packages/`), usando os padrões/bibliotecas já estabelecidos do projeto. Toda lógica de dados no protótipo é **mock** — não há ligação com APIs. A implementação real consome `/api/v1/{produto}/{recurso}` (ver "Contratos de API" abaixo).

### Como ler o protótipo
- **Template** (entre `<x-dc>…</x-dc>`): a UI. `{{ x }}` são valores; `<sc-if value="{{ b }}">` é condicional; `<sc-for list="{{ arr }}" as="item">` é loop. Estilos são **inline** (ótimo para ler valores exatos de cor/spacing/tipografia).
- **Lógica** (`<script data-dc-script>`): estado (`state = {…}`), navegação (`nav()`), e `renderVals()` que devolve todos os valores/handlers que o template consome. Os métodos `vEntity`, `vContabilia`, `vCompliance`, `vTax`, `vLicita`, `vPeti`, `vConcilia`, `vTribuna`, `vAlertas`, `vAudit`, `vConform`, `vConfig` agrupam os dados mock por produto.

---

## Fidelity

**Alta fidelidade (hi-fi).** Cores, tipografia, espaçamento, estados e microinterações são finais. Recrie pixel-perfect usando as libs do codebase. Onde o protótipo desenha visualizações com SVG/CSS (medidor de score, cartograma, donut, Benford, waterfall, grafo), trate-as como especificação visual e implemente com a lib de charts do projeto (ou SVG equivalente).

---

## Design Tokens

### Cores — neutros frios (institucional/terminal)
| Token | Hex | Uso |
|---|---|---|
| `bg/app` | `#f5f6f8` | fundo da área de conteúdo |
| `surface` | `#ffffff` | cards |
| `surface/muted` | `#f7f8fa` | blocos internos, inputs |
| `border` | `#e7eaee` / `#e3e7ec` | bordas de card / divisores |
| `border/strong` | `#d3d8df` | bordas de input |
| `sidebar/navy` | `#0c1c33` | sidebar, banners "ledger", CTA escuro |
| `sidebar/line` | `#1a2d4e` / `#21385f` | divisores na sidebar |
| `text/primary` | `#13181f` | texto principal |
| `text/secondary` | `#48515e` / `#5b6573` | rótulos, corpo |
| `text/muted` | `#76808d` / `#8a93a0` | secundário |
| `text/faint` | `#9aa3af` | placeholders, hints |
| `accent` (marca) | `#2f6fed` | ações primárias, links, ativo |
| `accent/hover` | `#2660d8` | hover de botão primário |
| `accent/tintBg` | `#e8effe` / `#eef4fe` | fundo de chip/realce azul |
| `accent/tintBorder` | `#cddcf8` | borda de chip azul |

### Cores semânticas — risco / severidade (verde→amarelo→laranja→vermelho)
Reutilizadas em score, alertas, indicadores, thresholds. **Nunca dependem só de cor** — sempre acompanham ícone+texto.
| Nível | Cor sólida | Bg tint | Texto | Borda tint |
|---|---|---|---|---|
| BAIXO / LOW | `#1f8a5b` | `#e7f4ee` | `#0f5c3a` | `#bfe3d0` |
| MODERADO / MEDIUM | `#caa215` (sólido) / `#b07d00` (texto/dot) | `#fbf4e2` / `#fbf6e9` | `#7a5800` | `#ecdcae` |
| ALTO / HIGH | `#cf6a1f` | `#fbe9da` | `#9a4a12` | `#f0cdab` |
| CRÍTICO / CRITICAL | `#c4382f` | `#fae3e1` | `#8f2a22` | `#f0c2bd` |

> **Caso contra-intuitivo do LegalScore:** score **alto = risco baixo** (verde no topo, 700–1000). A UI deixa explícito com rótulo lado a lado ("648 · Risco MODERADO") e a frase "score alto = risco baixo".

### Frescor de dados (freshness)
- Fresco (lag pequeno): verde `#1f8a5b` / bg `#f1f9f5` / texto `#0f5c3a` / borda `#bfe3d0`
- Defasado (médio): amarelo `#b07d00` / bg `#fbf6e9` / texto `#7a5800` / borda `#ecdcae`
- Muito defasado / stale (lag alto): vermelho `#c4382f` / bg `#fbeae8` / texto `#8f2a22` / borda `#f0c2bd`

### Classificação de dado (LGPD/ROPA)
- público 🟢 `#1f8a5b` (bg `#e7f4ee`/text `#0f5c3a`) · pessoal 🟡 `#b07d00` (bg `#fbf6e2`/text `#7a5800`) · sensível 🔴 `#c4382f` (bg `#fae3e1`/text `#8f2a22`)

### Tipografia
- **Sans (UI/corpo):** `'IBM Plex Sans', system-ui, sans-serif` — pesos 400/500/600/700.
- **Mono (dados):** `'IBM Plex Mono', monospace` — pesos 400/500/600. Usar em **CNPJ, hashes, request_id, merkle_root, IDs de processo, valores numéricos tabulares, datas técnicas, códigos IBGE, lags**.
- Escala observada: h1 23–24px/600/-.02em; h2 18–19px/600; título de seção 13px/600 uppercase letter-spacing .06em cor `#6b7480`; corpo 13–14px; rótulo 11–12px; mono pequeno 10–11px. Número grande de score 52px/700 mono; número grande de KPI/indicador 25–28px/600 mono.

### Raio, sombra, espaçamento
- Raio: card `10–12px`; input/botão `8px`; chip/badge `5–6px`; pill `20px`; avatar `50%`.
- Sombra: cards são **flat** (sem sombra), definidos por borda 1px. Sombra só em elementos flutuantes (ex.: nós do grafo `0 2px 6px rgba(12,28,51,.18)`; foco de input `0 0 0 3px #e2ebfd`).
- Espaçamento: gaps de grid 14–16px; padding de card 16–22px; padding de main 26–28px; largura máx. do conteúdo `1180px` centralizado.
- Sidebar: largura `238px`. Topbar: altura `58px`.

---

## Arquitetura de informação / Shell

```
Shell (sidebar 238px + topbar 58px + main scroll, max-width 1180px)
├── Login / seleção de tenant   (pré-shell)
├── PLATAFORMA
│   ├── Início (dashboard global)
│   ├── Entidade (HUB — produtos são lentes)   ← acessível também pela busca global
│   ├── Alertas (central multicanal)
│   ├── Auditoria (Decision Ledger / Merkle)
│   ├── Conformidade (LGPD / ROPA / direitos do titular / incidentes)
│   └── Configurações (admin-only — usuários, API keys, rate limit, assinaturas)
└── PRODUTOS · LENTES
    ├── LegalScore · ContabilIA · ComplianceRadar · TaxPredict
    ├── LicitaWatch · DanoBot (🔒 bloqueado) · PetiBot · ConciliaIA
    └── TribunaConnect (BETA · tempo real)
```

**Sidebar** (navy `#0c1c33`): logo, seletor de tenant, dois grupos de nav (item ativo = `background:rgba(47,111,237,.16)`, `box-shadow:inset 3px 0 0 #2f6fed`, texto branco; inativo = texto `#9fb0c5`). Cada item tem um "code chip" mono de 2 letras (IN, EN, LS, CT…). Rodapé: avatar do usuário + papel RBAC + sair.

**Topbar:** breadcrumb/título da rota · busca global (input; **Enter abre a Página de Entidade**) · **toggle de demonstração** (ver abaixo) · **switcher RBAC** (Admin/Analista/Leitor) · indicador de rate limit (42/100, barra) · sino de notificações (badge 3).

---

## Padrões transversais (design system — implementar em `frontend/packages/` PRIMEIRO)

Estes são reusados por todos os produtos. São o diferencial do produto.

### 1. Trust Header
Componente que responde 4 perguntas, em toda saída relevante (Página de Entidade e resultado do LegalScore o exibem):
1. **Frescor** — chips de selo por fonte (`Receita · 2d` verde, `PGFN · 31d` amarelo, `DATAJUD · 4d` amarelo…).
2. **Confiança** — score + intervalo (`648 · IC 95% 610–689`).
3. **Modelo** — chip `⚠ heurística` (amarelo) com "não é veredito" / vira "calibrado" após validação.
4. **Fontes** — chips mono das fontes consultadas (`DATAJUD PGFN Receita CAGED Neo4j +2`).
Layout: card branco, faixa de cabeçalho ("Trust header · procedência") + grid de 4 colunas com divisores `#f0f2f5`. Ação à direita: "🔒 Verificar decisão →" (→ Auditoria).

### 2. Selo de frescor (freshness seal)
Chip mono inline: `<dot> Fonte · Nd`. Cor por faixa de lag (ver tokens). Estado `stale` (lag > SLA) vira vermelho com aviso textual ("dado de 548 dias atrás"). Acompanha **todo** dado de fonte pública.

### 3. Visualização de incerteza
Nunca mostrar número-ponto de estimativa sozinho. Padrão único nos três:
- LegalScore: medidor 0–1000 (4 segmentos de risco) + **banda de IC** sobreposta + marcador do score.
- TaxPredict: donut de probabilidade + faixa de credibilidade (`51%–72%`).
- ConciliaIA: barra de faixa de acordo (mín–sugerido–máx).

### 4. Disclaimer heurística × calibrado
Chip/badge proeminente (amarelo) junto ao número. Estado "pending" no painel de métricas do modelo até AUC/Brier baterem meta → vira "calibrado".

### 5. Trilha de auditoria / Decision Ledger (celebrar)
Ação "🔒 Verificar decisão" → painel com `request_id`, `leaf_hash`, `merkle_root`, **prova de inclusão Merkle** (lista de irmãos L/R da folha até a raiz), resultado `verify_integrity` (íntegro), botão **"Exportar prova (PDF · ANPD)"** e "Reverificar".

### 6. Chip de citação verificável (anti-alucinação por construção)
Cada jurisprudência (TaxPredict) e cada precedente (PetiBot) é um **`<a>` clicável** que leva à fonte (processo no DATAJUD). No protótipo: `href="https://www.cnj.jus.br/datajud/<id>"`, estilo chip azul. **Regra de produto:** o chip só existe se a fonte foi verificada contra o índice. PetiBot exibe guarda **"⚠ < 3 precedentes — revisar"** em seções com suporte insuficiente.

### 7. Central de alertas
Lista filtrável por severidade (LOW/MEDIUM/HIGH/CRITICAL), canais (`webhook/email/slack/whatsapp` como chips mono), e **status de entrega** (`pending → claimed → done | failed`) com cores. **Sem PII:** `subject_ref` só usa referências não-pessoais (IBGE, CNPJ de órgão).

### 8. Estado de erro `problem+json` (RFC 9457)
Componente que renderiza `{type,title,status,detail,instance,contract_version}` de forma amigável. Casos: 400, 422 (entrada), 429 (mostrar Retry-After), 501 (DanoBot, bloqueado), 503 (modelo/fonte indisponível). *(No protótipo este componente é descrito mas não tem tela dedicada — implementar como toast/inline no codebase.)*

### 9. Processamento assíncrono (UX de job)
ContabilIA (upload → 202 + polling) e LegalScore (batch → job_id): barra de progresso real, lista de etapas (✓/·), status enfileirado→processando→pronto/falhou, download. Nunca spinner mudo.

### 10. Degradação graciosa
Linguagem visual calma para "resultado parcial / enriquecimento indisponível" (não parece erro). Ex.: LegalScore com DATAJUD off → banner amarelo "Score parcial", **IC alargado**, "circuit breaker ativo". Banner com `animation: pulse 1.6s infinite` no dot.

### 11. RBAC (role-aware UI)
Switcher Admin/Analista/Leitor na topbar muda a tela ao vivo:
- **viewer (Leitor):** vê scores/relatórios. Ações que disparam análise/geram documento/recalibram ficam **ocultas como afordância ausente** (chip "🔒 exige perfil Analista"), nunca erro tardio. Item "Configurações" some da nav. Banner de modo leitura no topo do conteúdo.
- **analyst (Analista):** roda análises e gera documentos.
- **admin:** tudo + "Configurações" + ação "Recalibrar modelo" no painel de métricas.

### 12. Toggle de dados (demonstração ↔ plataforma limpa)
Botão na topbar. **ON** = tudo populado (apresentação). **OFF** = plataforma limpa, como um tenant novo vê: KPIs zerados ("—"), listas vazias, e cada resultado cai no **estado vazio desenhado** ("Nenhum dado ingerido… modo limpo, sem conexão com as APIs") com botão "Ativar dados de demonstração". *(No produto real este toggle não existe — equivale ao estado natural "sem dados ingeridos" vs "dados ingeridos". Útil como referência dos estados vazios.)*

---

## Screens / Views

> Copy exata, layout e cores estão no `Plataforma.dc.html` (estilos inline). Resumo abaixo; consulte o arquivo para os valores literais.

### Login / Tenant
Split 1.1/0.9. Esquerda navy com grid sutil: logo, headline "Decisões de risco com prova de origem.", subtítulo da tese, 3 chips (Decision Ledger·Merkle / LGPD·multi-tenant / 14 fontes públicas), rodapé com **SLA honesto** ("~99% · nó único · janela dom 02:00–04:00"). Direita: form (e-mail, senha, **select de tenant**), botão "Entrar", nota "conexão isolada por tenant · TLS · auditada".

### Início (Dashboard global)
- 4 KPIs (Consultas hoje, Auditorias na fila, Alertas críticos, Uso da API 42/100) com dot de status.
- Grid de 8 cards de produto (code chip + nome + descrição; DanoBot com badge BLOQUEADO).
- Coluna de Alertas recentes (severidade + título + meta) com "ver todos →".
- Painel de **frescor das 7+ fontes** (Receita 2d…SNIS 548d) com dot e lag coloridos.
- CTA "Abrir entidade (CNPJ)".

### Entidade (HUB)
Rótulo "A ENTIDADE É O HUB, OS PRODUTOS SÃO LENTES". Cabeçalho da PJ (razão social, CNPJ mono, situação ATIVA, CNAE/porte). **Trust Header** (4 colunas). Grid de **lens cards** (LegalScore 648·MODERADO, Processos & grafo 7, ContabilIA 5 achados·1 crítico, TaxPredict 62%, ConciliaIA R$110k, ComplianceRadar N/A pois é PJ) — clicar abre a lente correspondente **preservando o contexto do CNPJ**. Rail direito: alertas da entidade + card navy "Decision Ledger".

### LegalScore PJ (produto âncora)
Header com chip "LS" + badge persistente "⚠ heurística". Barra de busca (CNPJ + "Calcular score" + "○ simular fonte off" [degradado] + "Score em lote ⬆" [analyst+]). Estados: vazio (prompt), **resultado**, e degradado (banner). Resultado:
- **Trust Header** + banner degradado (condicional).
- Card da empresa (razão social, CNPJ, situação, CNAE, capital, abertura, porte) + 3 selos de frescor (o de DATAJUD muda para vermelho "indisp." quando degradado).
- **Tabs:** Resumo · Grafo societário · Histórico · Auditoria · Métricas do modelo · Lote.
  - *Resumo:* card de score (número 648 52px mono, badge MODERADO, **medidor de 4 segmentos** red50%/orange10%/yellow10%/green30% + banda de IC + marcador `role="img"`), callout de IC 95% (610–689), engine (rust·38ms), link "request_id ↗ auditoria"; + card de **breakdown dos 7 fatores** (barras horizontais coloridas por saúde).
  - *Grafo societário:* rede empresa↔sócios↔processos (nós + linhas SVG; vem do Neo4j). Legenda.
  - *Histórico:* linha do score em 12 meses (área + pontos, com linha do último em destaque).
  - *Auditoria:* painel Merkle (ver transversal #5).
  - *Métricas do modelo:* banner "pending", cards AUC 0.78 / Brier 0.17 / KS 0.41 / amostra 12.4k com metas; **ação admin "Recalibrar modelo"** / nota de bloqueio para viewer.
  - *Lote:* dropzone CSV até 1.000 CNPJs → job_id; tabela de jobs com barra de progresso animada e status (done/running/queued).

### ContabilIA
Header "CT". Estados **upload → processamento → relatório** (UX de job).
- *Upload:* dropzone (CSV/PDF, OCR), nota "até 60s", grade dos 8 cross-checks CC01–CC08. Botão "iniciar auditoria" [analyst+].
- *Processamento:* "202 Accepted", % grande, barra, lista de etapas (OCR → parsing → 8 cross-checks → PDF) com ✓.
- *Relatório:* header "LAUDO PRONTO" + report_id + selo SICONFI 365d + "Baixar PDF". Lista de **achados por severidade** (cada um expansível: evidência lado a lado + fonte com data/lag; CC05 Benford destacado SUSPEITO). Card de **Benford** (barras observado vs esperado, χ²). Z-score, liquidez, EBITDA etc.

### ComplianceRadar
Header "CR". Tabs: Cartograma · Municípios · Perfil · Assinaturas · Alertas.
- *Cartograma:* **tile-grid das 27 UF** (grid 7×8, cada UF um quadrado colorido por severidade, `role="group"` + `aria-label` por tile) + legenda + aviso SNIS 548d. Rail: municípios em alerta (ranqueados).
- *Municípios:* tabela com indicadores e severidade.
- *Perfil:* cabeçalho do município (cod_ibge, referência) + "Avaliar regras agora" + grid de **cartões de indicadores** (Arrecadação YoY, Emprego YoY, Água, Esgoto, IDHM, PIB pc) cada um com **selo de frescor** e chip de severidade + aviso `sources_missing`.
- *Assinaturas:* form (município + indicador/regra + **canais** webhook/email/slack/whatsapp) + nota "alertas nunca expõem PII"; lista de assinaturas ativas.
- *Alertas:* central (compartilhada).

### TaxPredict
Header "TP" + toggle "simular fallback". Form (descrição 20–2000 chars, matéria PIS_COFINS…, valor/ano opc.) + "Prever desfecho" [analyst+]. Resultado:
- **Banner de fallback** (condicional): "estimativa nacional, modelo em recalibração" (prior 30%, is_fallback).
- Donut de probabilidade (62%) `role="img"` + badge heurística + faixa de credibilidade 95%.
- **SHAP** (barras divergentes +verde/−vermelho a partir de base = prior 30%), em linguagem do advogado.
- **Jurisprudências similares**: cada card com similaridade (barra), tribunal/ano, decisão (FAVORAVEL/PARCIAL/DESFAVORAVEL colorida) e **chip `<a>` clicável ao DATAJUD**.

### LicitaWatch
Header "LW". Busca por CNPJ de órgão → "Avaliar órgão". Resultado: cabeçalho do órgão (total contratos, valor total, selo PNCP 1d) + 4 **cartões de regra com semáforo** (LL03 único proponente 58% CRÍTICO, LL01 mesmo vencedor 74% ALTO, LL02 dispensa 34% ALTO, LL04 prazo curto 12% OK) + tabela de contratos (objeto, fornecedor, modalidade, valor, prazo, flag de anomalia).

### DanoBot (bloqueado)
Header "DB" + badge BLOQUEADO. **Estado de confiança desenhado:** ícone 🔒, "Indisponível — em conformidade legal", explicação DATASUS/art. 11/PD-06/501 intencional, chip "aguardando liberação do DPO", e **prévia do layout** (cards de indicadores em cinza/opacidade, pointer-events none). Não desenhar como ativo.

### PetiBot
Header "PB". Form (descrição 50–5000, tipo de ação TRABALHISTA…, polos, valor opc.) + "Montar peça" [analyst+]. Resultado: **editor de peça** com seções (DOS FATOS, DO DIREITO, DAS VERBAS RESCISÓRIAS, DOS PEDIDOS) editáveis (`contenteditable`), cada uma com **chips de precedentes clicáveis (DATAJUD)** e **guarda anti-alucinação** (< 3 precedentes). Rail: enriquecimento (risco da ré via LegalScore, prob. favorável via TaxPredict) + card "RAG online" (degrada para precedentes=0 se ChromaDB cair). Exportar .docx.

### ConciliaIA
Header "CC". Form (tipo, valor da causa, CNPJ do réu) + "Recomendar acordo" [analyst+]. Resultado: card de **faixa de acordo** (sugerido R$110k 38px mono, % da causa 22%, barra mín–sugerido–máx com banda + marcador) + **waterfall de fatores** (prior histórico, ajuste TaxPredict, ajuste LegalScore, valor presente) — cada fator com impacto +/− e descrição legível ("LegalScore=648/1000 → −2,2%"). Degradação graciosa quando enriquecimentos faltam.

### TribunaConnect (BETA · tempo real)
Sala colaborativa multi-escritório (Elixir/tempo real). Header com badge "BETA · TEMPO REAL" + badge "AO VIVO · 3 de 4 on-line" pulsando. Banner navy do caso (ação coletiva, nº processo, alerta vinculado) com avatares de presença empilhados. Layout: **minuta compartilhada** (`contenteditable`) com indicador "fulano está digitando…" (rotaciona), **timeline compartilhada** (eventos com autor/avatar/tempo, marcador "ao vivo"), rail de **presença** (status editando/online/ausente com dot pulsante) + **canais** (com badges de não-lidas). Projetar para presença/atualização ao vivo desde já.

### Alertas (central) · Auditoria · Conformidade · Configurações
- *Alertas:* filtros de severidade + lista (severidade, título, src/ref, canais, status de entrega).
- *Auditoria:* lista de decisões recentes (request_id, produto, timestamp) + painel Merkle grande.
- *Conformidade (LGPD/DPO):* 3 cards de **direitos do titular** (Acesso, Portabilidade JSON, Eliminação por crypto-shredding), **tabela ROPA** das fontes (classificação público/pessoal/sensível, base legal, finalidade), **playbook de incidentes** (chave rotacionada, ledger read-only) + "Exportar trilha (ANPD)".
- *Configurações (admin-only):* tabela de usuários (RBAC: Admin/Advogado/Contador/Leitura, status), rate limit (100 req/min, barra, 429 Retry-After), chaves de API (mascaradas), assinaturas de alerta.

---

## Interactions & Behavior

- **Navegação:** SPA por estado de rota; trocar de lente preserva a entidade (CNPJ). No codebase: rotas App Router `/(shell)/...` com contexto de entidade em URL/param ou store.
- **Busca global:** Enter → Página de Entidade. Implementar autocomplete (CNPJ / razão social / nº processo / município).
- **Estados por produto:** loading (skeleton, **carregamento progressivo** — mostrar o que chegou), vazio (orientar), erro (`problem+json`), parcial/stale, bloqueado (501), 429 (Retry-After), sem permissão (afordância ausente).
- **Async:** ContabilIA `POST /audit/upload` → 202 + header `Location` → polling em `GET /audit/{report_id}`. LegalScore batch → `job_id` → polling. UX de job (não fingir síncrono).
- **Degradação:** circuit breakers (DATAJUD, PNCP), RAG offline, modelo em recalibração → resultado parcial calmo, IC alargado.
- **Animações:** `pulse 1.6s` em dots de "ao vivo"/degradado; barra de progresso de batch com listras animadas (`barflow`); spinner só onde inevitável. Transições de hover sutis (border-color .12s).
- **contenteditable:** PetiBot (seções) e TribunaConnect (minuta) — no produto, editor controlado com salvamento.

## State Management (TanStack Query no produto)

Estado do protótipo (referência de quais flags a UI precisa): `route`, `tenant`, `role` (admin/analyst/viewer), `mock` (= "tem dados ingeridos"), por-produto: `lsHas/lsTab/degraded`, `caStage/caProgress`, `crView/crUf`, `tpHas/tpFallback/tpMateria`, `lwHas`, `pbHas/pbTipo`, `ccHas`, `expanded{}` (achados), `tribunaTick`.
No codebase: queries por recurso (`useQuery(['legalscore','score',cnpj])`), mutations para ações (score, predict, assemble, recommend, audit upload), polling com `refetchInterval` para jobs, e `role` vindo do RBAC do backend (admin/analyst/viewer) moldando afordâncias.

---

## Contratos de API (do repositório — a UI consome `/api/v1/{produto}/{recurso}`)

Erros: `application/problem+json` (RFC 9457) com `type,title,status,detail,instance,contract_version`.

- **LegalScore** — `POST /api/v1/legalscore/score` → `{score 0–1000, risk_level BAIXO|MODERADO|ALTO|CRITICO, confidence_interval [min,max], breakdown{7 fatores}, engine python|rust, disclaimer, source_date, lag_days}`. `GET /audit/{request_id}` (Merkle). `GET /model/metrics` (status pending/validado, AUC, Brier). Batch (até 1k) → `job_id`. Estados: 400 (CNPJ inválido), 429 (Retry-After), fonte off → score parcial, 501.
- **ContabilIA** — `POST /audit/upload` → 202 + `Location`. `GET /audit/{report_id}` (+PDF). `GET /audit/{report_id}/findings` (CC01–CC08, cada achado: `rule_id, severity, evidence, source{data,lag}`; Benford `CONFORME|MARGINAL|SUSPEITO`; Z-score 3σ; `ocr_confidence`).
- **ComplianceRadar** — `GET /municipalities`, `GET /municipality/{ibge_code}` (`MunicipioIndicadores`: delta_arrecadacao_yoy, delta_emprego_yoy, cobertura_agua_pct, cobertura_esgoto_pct, idhm, pib_per_capita, source_lag_days, source_date, sources_missing). `POST /alerts/subscribe`, `GET /alerts`, `POST /municipality/{ibge_code}/evaluate`. Regras: `arrecadacao_critica`, `saneamento_baixo`. Severity LOW|MEDIUM|HIGH|CRITICAL; canais webhook|email|slack|whatsapp. **subject_ref sem PII.**
- **TaxPredict** — `POST /predict` (`descricao 20–2000, materia PIS_COFINS|IRPJ|CSLL|ICMS|IPI|ISS|SIMPLES, valor?, orgao_autuante?, ano_autuacao?`) → `{probability 0–1, ci_lower, ci_upper, rag_hits, jurisprudencias[{doc_id, similarity, ementa, decisao FAVORAVEL|DESFAVORAVEL|PARCIAL|DESCONHECIDO, tribunal, ano}], features_used, model_version, is_fallback, model_status heurística|calibrado}`. Fallback = prior nacional 0.30. 422, 503.
- **LicitaWatch** — `GET /contratos/{cnpj}`, `POST /orgao/{cnpj}/evaluate` (`LicitacaoIndicadores`: total_contratos, valor_total, pct_mesmo_vencedor, pct_dispensa, pct_unico_proponente, pct_prazo_curto). Regras LL01 (>70% ALTO), LL02 (>30% ALTO), LL03 (>50% CRÍTICO), LL04 (<5d em >20% MÉDIO). PNCP circuit breaker.
- **DanoBot** — `501` (bloqueado, PD-06, DATASUS art. 11).
- **PetiBot** — `POST /assemble` (`descricao 50–5000, tipo_acao TRABALHISTA|CIVEL|TRIBUTARIO|PREVIDENCIARIO|ADMINISTRATIVO|CONSUMERISTA, polo_ativo, polo_passivo, valor_causa?, cnpj_parte?`) → `{secoes[{titulo, conteudo, precedentes[doc_id]}], precedentes_encontrados, risk_score?, probability_favorable?}`. RAG offline → precedentes_encontrados=0.
- **ConciliaIA** — `POST /recommend` → `{valor_minimo, valor_sugerido, valor_maximo, percentual_causa, fatores[{nome, impacto, descricao}], risco_reu, probabilidade_procedencia}`.

---

## Accessibility (WCAG 2.1 AA — requisito de mercado/setor público)

Já no protótipo: `<html lang="pt-BR">`; `<button>`/`<label>` nativos (foco/teclado); **ícone+texto** em toda severidade (não depende só de cor); `role="img"`+`aria-label` no medidor de score e donut; `role="group"`+`aria-label` no cartograma e em cada tile UF.

**A fazer no build (especificar):** ARIA no **grafo societário** e no **viewer Merkle** (descrição textual da estrutura); foco visível consistente; navegação por teclado nas tabs (roving tabindex); alternativas textuais para emojis decorativos (`aria-hidden`); contraste AA verificado nos chips amarelos sobre branco; leitor de tela nas barras/charts (resumo textual + `<title>`/`<desc>` em SVG). PT-BR nativo: R$, datas, CNPJ mascarado `00.000.000/0000-00`. eMAG quando houver cliente público.

---

## Responsividade & performance percebida
Desktop-first (densidade de dado). **Alertas, perfis e aprovações precisam funcionar no celular.** Considerar modo **compacto/confortável** (densidade). Metas: score < 1,5s; relatório < 60s; LCP do dashboard < 2s. Usar skeletons + carregamento progressivo + UX de job.

## Assets
Nenhum binário. Fontes: **IBM Plex Sans + IBM Plex Mono** (Google Fonts). Ícones: glyphs Unicode/mono no protótipo — **substituir por ícone-set do codebase** (ex.: lucide) no build; emojis (🔒⚠⌕) são placeholders. Grafo/cartograma/charts: implementar com a lib de viz do projeto.

## Lacunas conhecidas (próximos passos)
1. **Dark mode** e **tema por tenant** (white-label leve) via tokens — não implementados.
2. **A11y completa** (grafo, Merkle, teclado nas tabs) — iniciada, ver seção acima.
3. Tela dedicada do componente de **erro `problem+json`** — padrão descrito, não desenhado.
4. **TribunaConnect** é conceitual/futuro (cursores nomeados, histórico de versões, presença real via WebSocket/Phoenix Channels).

## Files
- `Plataforma.dc.html` — protótipo completo (todas as telas, estados, RBAC, toggle de dados). **Fonte da verdade visual.**
- `support.js` — runtime do protótipo (não usar em produção; apenas para abrir o HTML).

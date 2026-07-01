# pendencias.md — dúvidas e decisões para análise

> Registro autônomo de pontos que exigem sua decisão ou dados externos. Cada item
> tem impacto e recomendação. Nada aqui bloqueia o CI; são decisões de produto,
> licença e governança. (Distinto de `Pendencia.md`, que rastreia os DoD/P0 do
> roadmap original.)

## 1. Licença dos dados da ABJ  — **precisa de decisão**
- **Contexto:** a fonte ABJ (`services/ingest/tasks/abj.py`) está **desligada por
  padrão** (`ABJ_ENABLED=false`). Os datasets abjData/observatórios são públicos,
  mas a redistribuição comercial em SaaS precisa de confirmação de licença.
- **Impacto:** com ABJ ligada, a `jurimetria.indicador` ganha duração real
  (`fonte=BLEND`) e cross-check; sem ela, duração fica limitada (item 2).
- **Recomendação:** confirmar termos de cada dataset e registrar base legal na
  `docs/ROPA.md` antes de setar `ABJ_ENABLED=true`.

## 2. DATAJUD sem data de ajuizamento → duração subestimada
- **Contexto:** `DatajudProcessoBronze` tem `data_julgamento` mas não
  `data_ajuizamento`. A duração mediana em `jurimetria.indicador` só é confiável
  na linha `fonte=BLEND` (duração vinda da ABJ).
- **Decisão necessária:** (a) habilitar ABJ (item 1) para suprir a duração, e/ou
  (b) estender o contrato/ingest se a API pública do CNJ expuser a data de
  ajuizamento. Recomendo mapear o campo na API DataJud e, se existir, adicioná-lo.

## 3. Chamber Profiler: granularidade câmara/vara/juiz  — **LGPD**
- **Contexto:** o `chamber_profiler` opera hoje no grão **tribunal+classe** porque
  o silver do DATAJUD ainda não carrega `orgao_julgador`. Perfil por juiz
  individual é pessoa natural (risco LGPD alto — plano manteve só câmara/vara).
- **Para descer a câmara/vara:** adicionar `orgao_julgador` ao contrato/ingest e
  agregar por esse campo. **Perfil por juiz individual exige parecer do DPO**
  (mesmo padrão 501 do DanoBot) — não implementar sem sua aprovação + LIA.

## 4. Modelos rotulados como heurística (sem validação)
- **Forecasting** (tendência linear), **Second Opinion** (consenso ponderado) e o
  **LegalScore** seguem rotulados como heurística. Faltam datasets de desfecho
  real para medir AUC/erro e calibrar.
- **Recomendação:** definir uma fonte de ground truth (desfechos de processos
  encerrados) para validação out-of-time. Enquanto isso, os endpoints retornam
  `disclaimer` explícito.

## 5. Pesos do LegalScore ainda são default do engine
- **Contexto:** `features.py` agora entrega features data-backed (contagens reais
  do Neo4j), mas os **coeficientes** do `PythonScoreEngine` seguem placeholder.
- **Recomendação:** carregar coeficientes por CNAE de uma tabela de calibração
  quando houver dados de desfecho (item 4). Não bloqueante.

## 6. Verificação de persistência só em E2E
- Os clientes `services/shared/storage/*` (MinIO/OpenSearch/Neo4j) são I/O externo
  e estão omitidos da cobertura unitária (mesma política de `fiscal/storage.py`).
  Precisam de um teste **E2E** com o stack Docker de pé para validar o caminho
  real (bronze→MinIO, silver→OpenSearch, arestas→Neo4j). Sugiro adicionar ao
  `make` um alvo E2E de ingestão quando o ambiente permitir.

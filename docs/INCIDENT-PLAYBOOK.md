# Playbook de Incidentes — juridico-platform

> Atualizado: 2026-06-16. Revisar a cada release principal.
>
> **Contexto LGPD:** incidentes envolvendo dados pessoais (CNPJ/CPF pseudonimizados,
> subject_token do Ledger, chaves AES por titular) ativam o art. 48 da LGPD —
> comunicação à ANPD e titulares afetados em até 72h (casos graves).

---

## 1. Categorias de Incidente

| Categoria | Exemplos | Severidade |
|---|---|---|
| **SEC-1** | Vazamento de bucket MinIO / S3 | CRÍTICO |
| **SEC-2** | Acesso indevido a banco de dados (Postgres/Neo4j) | CRÍTICO |
| **SEC-3** | Comprometimento da chave HMAC | CRÍTICO |
| **SEC-4** | Comprometimento de chave AES por titular | ALTO |
| **SEC-5** | Exfiltração de tokens JWT | ALTO |
| **OPS-1** | Indisponibilidade do gateway (> 5 min) | ALTO |
| **OPS-2** | Falha no Celery (batch/recalibração travado) | MÉDIO |
| **OPS-3** | Redis indisponível (cache/idempotência offline) | MÉDIO |
| **DATA-1** | Inconsistência no Decision Ledger (raiz Merkle divergente) | CRÍTICO |
| **DATA-2** | Dado pessoal em claro detectado nos logs | CRÍTICO |

---

## 2. Fluxo Geral de Resposta

```
Detecção (alerta Prometheus / log audit / relato externo)
  → Triagem (15 min): categorizar, isolar, escalar se SEC-* ou DATA-*
  → Contenção: bloquear acesso, revogar credencial comprometida
  → Erradicação: rotação de chave / patch / remoção de dado em claro
  → Recuperação: restaurar serviço a partir de backup verificado
  → Pós-incidente: root cause, evidências → ANPD/titulares se aplicável
```

---

## 3. SEC-1 — Vazamento de Bucket MinIO

**Sintoma:** bucket bronze/silver/gold acessível anonimamente; notificação de
scan externo (shodan, TreatIntel).

**Contenção (< 30 min):**
1. Revogar todas as access keys do MinIO: `mc admin user list minio/` → `mc admin user remove`
2. Aplicar política deny-all temporária: `mc admin policy set minio/ deny-all user=minioadmin`
3. Bloquear porta 9000/9001 no firewall: `ufw deny 9000 && ufw deny 9001`

**Erradicação:**
4. Auditar logs de acesso (`mc admin trace minio/`) para identificar objetos acessados
5. Recriar access keys com permissão mínima (só escrita para ingest, só leitura para scoring)
6. Garantir que `MINIO_ANONYMOUS_ACCESS=off` (sem `mc anonymous set download`)

**Recuperação:**
7. Reabilitar acesso só via Traefik (porta 80/443 autenticada)
8. Verificar integridade dos buckets gold (checksums) contra backups

**Evidências para ANPD:** logs de acesso MinIO (`mc admin trace`), IPs de origem,
lista de objetos acessados, timestamps, ação tomada.

---

## 4. SEC-2 — Acesso Indevido ao Banco de Dados

**Sintoma:** login suspeito nos logs do Postgres/Neo4j; queries fora do padrão
detectadas no PgBouncer; `pg_stat_activity` com sessão de IP desconhecido.

**Contenção (< 30 min):**
1. Encerrar sessões suspeitas: `SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE client_addr = 'IP_SUSPEITO'`
2. Revogar credencial comprometida: `REVOKE ALL ON ALL TABLES IN SCHEMA public FROM usuario_comprometido; DROP ROLE usuario_comprometido;`
3. Bloquear IP no firewall

**Erradicação:**
4. Rotacionar senhas de todos os usuários de banco
5. Verificar RLS ativa em todas as tabelas multi-tenant: `SELECT tablename, rowsecurity FROM pg_tables WHERE schemaname='public'`
6. Auditar `audit_log` e `pg_stat_activity` para queries executadas

**Recuperação:**
7. Restaurar de backup se dados foram alterados (ver Seção 8)
8. Verificar `verify_integrity()` do Decision Ledger contra backup

---

## 5. SEC-3 — Comprometimento da Chave HMAC

**Sintoma:** chave HMAC (`HMAC_KEY` em Docker Secret / KMS) exposta em log,
variável de ambiente, ou repositório git.

**Impacto:** todos os pseudônimos gerados com a chave comprometida podem ser
vinculados aos CNPJs/CPFs originais por quem tem a chave. Os pseudônimos em si
não são PII (são HMACs), mas a chave torna o vínculo reversível.

**Contenção (imediata):**
1. Revogar o Docker Secret: `docker secret rm HMAC_KEY`
2. Gerar nova chave: `docker secret create HMAC_KEY <(openssl rand -hex 32)`
3. Redeploy do gateway para carregar a nova chave

**Erradicação:**
4. Re-pseudonimizar todos os registros do Decision Ledger com a nova chave
   (processo batch em Celery; script: `scripts/reпсеудonym_ledger.py` — a criar)
5. Remover a chave comprometida de todos os logs e alertar sobre o commit se
   exposta no git (`git filter-repo --path` para remover histórico)

**Nota LGPD:** a re-pseudonimização é necessária para manter a separação entre
o dado pseudonimizado e o original. Comunicar à ANPD se o acesso com a chave
comprometida permitiu re-identificação de titulares.

---

## 6. SEC-4 — Comprometimento de Chave AES por Titular

**Sintoma:** `_KEY_STORE` (em dev, memória) ou KMS (em produção) acessado por
processo não autorizado; vazamento de chave AES de um titular específico.

**Impacto:** o `subject_token` desse titular no Decision Ledger pode ser
decriptado, revelando o pseudônimo HMAC do titular.

**Contenção:**
1. Em KMS: revogar a chave comprometida imediatamente (AWS KMS: `DisableKey`)
2. Chamar `erase_titular(pseudonym, tenant_id)` para destruir a chave local
3. Auditar o `audit_log` para verificar `pii.decrypt` não autorizados

**Erradicação:**
4. Gerar nova chave para o titular e re-cifrar o `subject_token` no Ledger
5. Registrar o evento em `audit_log` como `pii.key_rotation`

**Nota LGPD:** titular afetado deve ser notificado se o pseudônimo exposto puder
ser combinado com outros dados para re-identificação.

---

## 7. DATA-1 — Inconsistência no Decision Ledger

**Sintoma:** `verify_integrity(entry_id, get_proof(entry_id))` retorna `False`;
raiz Merkle diverge do backup mais recente.

**Diagnóstico:**
```python
from services.shared.ledger.merkle import DecisionLedger
ledger = DecisionLedger()  # ou carregar do Postgres na Fase 1c
proof = ledger.get_proof("REQUEST_ID_SUSPEITO")
ok = ledger.verify_integrity("REQUEST_ID_SUSPEITO", proof)
print(f"Integridade: {ok}")
```

**Contenção:**
1. Colocar o Ledger em modo read-only (bloquear `add_entry`)
2. Identificar o índice da primeira entrada corrompida

**Erradicação:**
3. Restaurar o Ledger do backup verificado (ver Seção 8)
4. Reprocessar as entradas pós-backup via replay do outbox de alertas

**Evidências:** hash das entradas afetadas, timestamp da divergência, diff entre
raiz atual e raiz do backup.

---

## 8. Procedimento de Restauração de Backup

```bash
# 1. Parar serviços de escrita (não o gateway — só os workers)
docker compose stop celery-worker celery-beat

# 2. Restaurar Postgres
pg_restore --host=localhost --port=5432 --username=juridico \
  --dbname=juridico_db backup/postgres-YYYY-MM-DD.dump

# 3. Verificar integridade do Ledger pós-restore
python -c "
from services.shared.ledger.merkle import DecisionLedger
# (quando migrado para Postgres na Fase 1c)
print('Raiz Merkle:', DecisionLedger().merkle_root)
"

# 4. Restaurar MinIO (objetos gold)
mc mirror backup/minio/ minio/gold/

# 5. Reiniciar workers
docker compose start celery-worker celery-beat

# 6. Verificar health
curl -s http://localhost/api/v1/health | jq .
```

**Critério de aceite do restore:** raiz Merkle idêntica ao valor no backup;
`verify_integrity()` True para todas as entradas spot-checked.

---

## 9. Comunicação à ANPD (art. 48 LGPD)

**Quando comunicar:** incidente com acesso/exposição/alteração de dados pessoais
ou sensíveis que possa acarretar risco ou dano relevante aos titulares.

**Prazo:** ANPD deve ser notificada em prazo razoável (a ANPD recomenda 72h para
incidentes graves; comunicar aos titulares em prazo a ser definido pela ANPD).

**Conteúdo mínimo da comunicação:**
- Descrição da natureza dos dados afetados e dos titulares envolvidos
- Medidas técnicas e de segurança adotadas
- Riscos relacionados ao incidente
- Razões do atraso, se a comunicação não for imediata

**Cadeia de evidências:**
- Logs de acesso (`audit_log`, Loki): exportar em formato imutável
- Prova Merkle das entradas do Ledger afetadas
- Registros de rotação de chave com timestamps

---

## 10. Contatos e Responsabilidades

| Papel | Ação |
|---|---|
| **Dono do sistema** (danzeroum) | Autorizar contenção, comunicar ANPD |
| **DPO** (PD-06 — a contratar) | Avaliar obrigatoriedade de comunicação, coordenar com titulares |
| **Engenharia** | Executar contenção técnica, erradicação, restore |

---

## 11. Teste do Playbook

Este playbook deve ser testado a cada 6 meses:
- [ ] Simular SEC-3: rotacionar HMAC_KEY em staging, verificar gateway reinicia sem erros
- [ ] Simular DATA-1: corromper manualmente uma entrada no Ledger, verificar `verify_integrity()` detecta
- [ ] Simular OPS-1: derrubar o gateway, verificar tempo de recovery < 5 min
- [ ] Executar restore completo de backup em VM limpa (P0-2)

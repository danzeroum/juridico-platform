"""
Cliente Neo4j para o grafo de entidades jurídicas.

Modelo (plano A.1 / B):
    (:Empresa {cnpj})-[:PARTE_EM]->(:Processo {id, tribunal, classe, assunto,
                                                data_julgamento, valor_log})

Escrita em batelada via `UNWIND $rows` + `MERGE` (idempotente). Requer as
constraints de unicidade (`ensure_constraints`) ANTES do primeiro bulk, senão o
`MERGE` degrada para varredura O(n).

I/O externo — omitido de cobertura; validado em E2E. O driver é um singleton por
processo (thread-safe, com pool de conexões próprio) construído lazy.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_driver: Any | None = None


def _get_driver():
    global _driver
    if _driver is None:
        from neo4j import GraphDatabase

        from services.shared.config import settings

        _driver = GraphDatabase.driver(
            settings.NEO4J_URL,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
        )
    return _driver


def ensure_constraints(driver: Any | None = None) -> None:
    """Cria as constraints de unicidade (idempotente). Rodar uma vez no bootstrap."""
    driver = driver or _get_driver()
    stmts = (
        "CREATE CONSTRAINT processo_id IF NOT EXISTS "
        "FOR (p:Processo) REQUIRE p.id IS UNIQUE",
        "CREATE CONSTRAINT empresa_cnpj IF NOT EXISTS "
        "FOR (c:Empresa) REQUIRE c.cnpj IS UNIQUE",
    )
    with driver.session() as session:
        for stmt in stmts:
            session.run(stmt)
    logger.info("Neo4j: constraints de unicidade garantidas")


_UPSERT_CYPHER = """
UNWIND $rows AS r
MERGE (p:Processo {id: r.id_processo})
  SET p.tribunal        = r.tribunal,
      p.classe          = r.classe_tpu,
      p.assunto         = r.assunto_tpu,
      p.ramo            = r.ramo,
      p.data_julgamento = r.data_julgamento,
      p.valor_log       = r.valor_log
WITH p, r
WHERE r.cnpj_parte IS NOT NULL
MERGE (c:Empresa {cnpj: r.cnpj_parte})
MERGE (c)-[:PARTE_EM]->(p)
"""


def upsert_process_edges(records: list[dict[str, Any]], driver: Any | None = None) -> int:
    """
    Faz upsert em batelada de nós Processo/Empresa e arestas PARTE_EM.

    Extrai apenas os campos necessários de cada registro silver do DATAJUD.
    Retorna o número de registros enviados. Degradação graciosa a cargo do
    chamador (`persist_silver`).
    """
    if not records:
        return 0
    rows = [
        {
            "id_processo": r.get("id_processo"),
            "tribunal": r.get("tribunal"),
            "classe_tpu": r.get("classe_tpu"),
            "assunto_tpu": r.get("assunto_tpu"),
            "ramo": r.get("ramo"),
            "data_julgamento": str(r.get("data_julgamento")) if r.get("data_julgamento") else None,
            "valor_log": r.get("valor_log"),
            "cnpj_parte": r.get("cnpj_parte"),
        }
        for r in records
        if r.get("id_processo")
    ]
    driver = driver or _get_driver()
    with driver.session() as session:
        session.run(_UPSERT_CYPHER, rows=rows)
    logger.info("Neo4j: %d processos upsertados (arestas PARTE_EM)", len(rows))
    return len(rows)


def count_processos_por_cnpj(cnpj: str, driver: Any | None = None) -> dict[str, Any]:
    """
    Consulta usada pelo feature assembler do LegalScore (plano B.6).

    Retorna contagens de processos da empresa por eixo, agregando por assunto TPU
    quando disponível. Consulta read-only; degradação graciosa (retorna zeros se
    o grafo estiver indisponível é responsabilidade do chamador).
    """
    query = """
    MATCH (c:Empresa {cnpj: $cnpj})-[:PARTE_EM]->(p:Processo)
    RETURN count(p) AS total,
           collect(DISTINCT p.assunto) AS assuntos,
           sum(CASE WHEN p.ramo = 'TRABALHISTA' THEN 1 ELSE 0 END) AS trabalhistas
    """
    driver = driver or _get_driver()
    with driver.session() as session:
        rec = session.run(query, cnpj=cnpj).single()
    if rec is None:
        return {"total": 0, "trabalhistas": 0, "repetitivos": 0}
    total = rec["total"] or 0
    assuntos = [a for a in (rec["assuntos"] or []) if a]
    # "Repetitivo": mais processos que assuntos distintos ⇒ concentração de tema.
    repetitivos = max(0, total - len(assuntos)) if total else 0
    return {"total": total, "trabalhistas": rec["trabalhistas"] or 0, "repetitivos": repetitivos}

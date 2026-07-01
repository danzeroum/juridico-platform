#!/usr/bin/env python3
"""
Seed da base fiscal — matriz ICMS interestadual (27 UFs) + alíquotas internas
de SP/RJ/MG. Idempotente: remove as linhas de mesma `source` antes de reinserir.

O seed é o *gold standard* inicial; a partir do go-live, o sefaz_scraper e o
diario_oficial_monitor passam a ser a fonte de verdade (ver plano §7).

Fundamentos:
- Interestadual: Resolução do Senado Federal 22/1989 e 13/2012 (via contracts.fiscal).
- SP: 18% (Art. 52, I, RICMS-SP, Dec. 45.490/2000).
- MG: 18% (RICMS-MG).
- RJ: 18% + 2% FECP (LC-RJ 210/2023) → efetiva 20%.

Conexão: MIGRATIONS_DATABASE_URL (admin) ou DATABASE_URL. Execução idempotente.
"""
from __future__ import annotations

import os
import sys

from services.shared.contracts.fiscal import UF, aliquota_interestadual

SOURCE_INTER = "SENADO-SEED"
SOURCE_INTERNO = "SEFAZ-SEED"

# Alíquotas internas gerais (modal) e FCP por estado do escopo inicial.
INTERNAS = [
    # uf, aliquota_pct, fcp_pct, fundamento
    ("SP", 18.0, None, "Art. 52, I, RICMS-SP (Dec. 45.490/2000)"),
    ("MG", 18.0, None, "RICMS-MG (Dec. 43.080/2002)"),
    ("RJ", 18.0, 2.0, "RICMS-RJ + FECP (LC-RJ 210/2023)"),
]

CATEGORIAS = [
    ("epi", "EPI — Equipamento de Proteção Individual"),
    ("maquinas", "Máquinas e equipamentos"),
    ("embalagens", "Embalagens"),
    ("material-escritorio", "Material de escritório"),
    ("informatica", "Informática e eletrônicos"),
]


def _db_url() -> str:
    url = os.getenv("MIGRATIONS_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not url:
        sys.exit("Defina MIGRATIONS_DATABASE_URL (admin) ou DATABASE_URL.")
    return url


def seed(conn) -> dict[str, int]:
    from sqlalchemy import text

    # 1. Interestadual — matriz 27x27 (origem != destino), regra do Senado.
    conn.execute(text("DELETE FROM fiscal.icms_interestadual WHERE source = :s"), {"s": SOURCE_INTER})
    ufs = [u.value for u in UF]
    n_inter = 0
    for o in ufs:
        for d in ufs:
            if o == d:
                continue
            pct, fundamento = aliquota_interestadual(o, d)
            conn.execute(
                text(
                    "INSERT INTO fiscal.icms_interestadual "
                    "(uf_origem, uf_destino, aliquota_pct, importado, fundamento_legal, source) "
                    "VALUES (:o, :d, :pct, FALSE, :f, :s)"
                ),
                {"o": o, "d": d, "pct": pct, "f": fundamento, "s": SOURCE_INTER},
            )
            n_inter += 1

    # 2. Internas — SP/RJ/MG (alíquota geral, ncm_prefix NULL).
    conn.execute(text("DELETE FROM fiscal.icms_interno WHERE source = :s"), {"s": SOURCE_INTERNO})
    for uf, aliq, fcp, fundamento in INTERNAS:
        conn.execute(
            text(
                "INSERT INTO fiscal.icms_interno "
                "(uf, ncm_prefix, aliquota_pct, fcp_pct, fundamento_legal, source) "
                "VALUES (:uf, NULL, :aliq, :fcp, :f, :s)"
            ),
            {"uf": uf, "aliq": aliq, "fcp": fcp, "f": fundamento, "s": SOURCE_INTERNO},
        )

    # 3. Categorias iniciais (idempotente via slug).
    for slug, nome in CATEGORIAS:
        conn.execute(
            text(
                "INSERT INTO fiscal.categoria (slug, nome) VALUES (:slug, :nome) "
                "ON CONFLICT (slug) DO NOTHING"
            ),
            {"slug": slug, "nome": nome},
        )

    return {"interestadual": n_inter, "interno": len(INTERNAS), "categorias": len(CATEGORIAS)}


def main() -> None:
    from sqlalchemy import create_engine

    engine = create_engine(_db_url())
    with engine.begin() as conn:
        counts = seed(conn)
    print(f"✓ Seed fiscal concluído: {counts}")


if __name__ == "__main__":
    main()

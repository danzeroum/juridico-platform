"""
Resolução de ICMS — determinística e pura.

- Interna efetiva = alíquota modal + FCP/FECP (quando aplicável). Ignorar o FCP
  subestima o imposto (ex.: RJ efetivo ~20% = modal + 2% FECP, LC-RJ 210/2023).
- Interestadual: Resolução do Senado (22/1989, 13/2012) — ver contracts.fiscal.
- DIFAL (EC 87/2015 + LC 190/2022) = max(0, interna_efetiva_destino − interestadual).

A linha de ICMS interno vigente (`interna_row`) é injetada pelo chamador
(repository), permitindo teste sem banco.
"""
from __future__ import annotations

from services.shared.contracts.fiscal import (
    IcmsResolution,
    aliquota_interestadual,
    compute_difal,
)


def _efetiva(aliquota_pct: float | None, fcp_pct: float | None) -> float | None:
    if aliquota_pct is None:
        return None
    return round(aliquota_pct + (fcp_pct or 0.0), 2)


def resolve_icms(
    uf_origem: str,
    uf_destino: str,
    interna_row_destino: dict | None,
    *,
    importado: bool = False,
    conteudo_importacao_pct: float | None = None,
) -> IcmsResolution:
    """
    Monta a resolução de ICMS para a operação origem→destino.

    `interna_row_destino`: dict {'aliquota_pct', 'fcp_pct', 'fundamento_legal'} da
    alíquota interna vigente no DESTINO, ou None se não houver dado (não inventa valor).
    """
    interna_pct = fcp_pct = interna_efetiva = None
    fundamento = None
    if interna_row_destino is not None:
        interna_pct = interna_row_destino.get("aliquota_pct")
        fcp_pct = interna_row_destino.get("fcp_pct")
        interna_efetiva = _efetiva(interna_pct, fcp_pct)
        fundamento = interna_row_destino.get("fundamento_legal")

    if uf_origem == uf_destino:
        # Operação interna: sem interestadual/DIFAL.
        return IcmsResolution(
            interna_pct=interna_pct,
            fcp_pct=fcp_pct,
            interna_efetiva_pct=interna_efetiva,
            interestadual_pct=None,
            difal_pct=None,
            fundamento_legal=fundamento,
        )

    inter_pct, inter_fundamento = aliquota_interestadual(
        uf_origem,
        uf_destino,
        importado=importado,
        conteudo_importacao_pct=conteudo_importacao_pct,
    )
    difal = compute_difal(interna_efetiva, inter_pct)
    fundamento_final = "; ".join(f for f in (fundamento, inter_fundamento) if f) or None
    return IcmsResolution(
        interna_pct=interna_pct,
        fcp_pct=fcp_pct,
        interna_efetiva_pct=interna_efetiva,
        interestadual_pct=inter_pct,
        difal_pct=difal,
        fundamento_legal=fundamento_final,
    )

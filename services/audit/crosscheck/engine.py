"""
CrossCheckEngine — valida demonstrações financeiras contra fontes públicas.

Regras CC01–CC08:
  CC01: Headcount DRE vs CAGED (delta > 20%) — ALTO
  CC02: Receita municipal DRE vs SICONFI (delta > 30%) — CRITICO
  CC03: Receita de serviços públicos sem contratos PNCP — MEDIO
  CC04: Variação de estoque desproporcional às importações — MEDIO
  CC05: Lei de Benford em receitas mensais — MEDIO/ALTO
  CC06: Z-score em despesas mensais (|z| > 3σ) — ALTO
  CC07: Índice de Liquidez Corrente < 0,50 — CRITICO
  CC08: Margem EBITDA implausível (< -30% ou > 60%) — ALTO
"""
from __future__ import annotations

from dataclasses import dataclass, field

from services.audit.benford import BenfordResult, analyze_benford
from services.audit.zscore import ZScoreResult, compute_zscore


@dataclass
class CrossCheckFinding:
    rule: str
    severity: str
    description: str
    detail: dict = field(default_factory=dict)


class CrossCheckEngine:
    """
    Executa as regras de cross-check CC01–CC08.

    financials: métricas da DRE/balanço fornecidas pelo upload.
    public_data: dados públicos pré-buscados (CAGED, SICONFI, PNCP).
    """

    def run_checks(self, financials: dict, public_data: dict) -> list[CrossCheckFinding]:
        findings: list[CrossCheckFinding] = []
        findings.extend(self._cc01_headcount_vs_caged(financials, public_data))
        findings.extend(self._cc02_receita_vs_siconfi(financials, public_data))
        findings.extend(self._cc03_contratos_vs_pncp(financials, public_data))
        findings.extend(self._cc04_importacoes_vs_estoque(financials, public_data))
        findings.extend(self._cc05_benford_receitas(financials))
        findings.extend(self._cc06_zscore_despesas(financials))
        findings.extend(self._cc07_liquidez(financials))
        findings.extend(self._cc08_margem_ebitda(financials))
        return findings

    def _cc01_headcount_vs_caged(self, fin: dict, pub: dict) -> list[CrossCheckFinding]:
        headcount = fin.get("headcount")
        caged_saldo = pub.get("caged_saldo_12m")
        if headcount is None or caged_saldo is None or headcount == 0:
            return []
        delta = abs(headcount - caged_saldo) / abs(headcount)
        if delta > 0.20:
            return [CrossCheckFinding(
                rule="CC01",
                severity="ALTO",
                description="Delta headcount DRE vs CAGED > 20%",
                detail={"dre": headcount, "caged": caged_saldo, "delta_pct": round(delta * 100, 1)},
            )]
        return []

    def _cc02_receita_vs_siconfi(self, fin: dict, pub: dict) -> list[CrossCheckFinding]:
        receita_dre = fin.get("receita_liquida")
        siconfi_receita = pub.get("siconfi_receita_total")
        if receita_dre is None or siconfi_receita is None or siconfi_receita == 0:
            return []
        delta = abs(receita_dre - siconfi_receita) / abs(siconfi_receita)
        if delta > 0.30:
            return [CrossCheckFinding(
                rule="CC02",
                severity="CRITICO",
                description="Receita DRE vs SICONFI divergem > 30%",
                detail={"dre": receita_dre, "siconfi": siconfi_receita, "delta_pct": round(delta * 100, 1)},
            )]
        return []

    def _cc03_contratos_vs_pncp(self, fin: dict, pub: dict) -> list[CrossCheckFinding]:
        receita_publica = fin.get("receita_servicos_publicos")
        pncp_total = pub.get("pncp_contratos_total")
        if receita_publica is None or pncp_total is None:
            return []
        if pncp_total == 0 and receita_publica > 0:
            return [CrossCheckFinding(
                rule="CC03",
                severity="MEDIO",
                description="Receita de serviços públicos sem contratos PNCP correspondentes",
                detail={"receita_dre": receita_publica, "pncp_contratos": pncp_total},
            )]
        return []

    def _cc04_importacoes_vs_estoque(self, fin: dict, pub: dict) -> list[CrossCheckFinding]:
        importacoes = fin.get("importacoes")
        variacao_estoque = fin.get("variacao_estoque")
        if importacoes is None or variacao_estoque is None or importacoes == 0:
            return []
        ratio = variacao_estoque / importacoes
        if ratio > 3.0:
            return [CrossCheckFinding(
                rule="CC04",
                severity="MEDIO",
                description="Variação de estoque desproporcional às importações (ratio > 3x)",
                detail={"importacoes": importacoes, "variacao_estoque": variacao_estoque, "ratio": round(ratio, 2)},
            )]
        return []

    def _cc05_benford_receitas(self, fin: dict) -> list[CrossCheckFinding]:
        series = fin.get("serie_receitas_mensais")
        if not series or len(series) < 30:
            return []
        try:
            result: BenfordResult = analyze_benford(series, column="receitas_mensais")
        except ValueError:
            return []
        if result.status in ("MARGINAL", "SUSPEITO"):
            return [CrossCheckFinding(
                rule="CC05",
                severity="ALTO" if result.status == "SUSPEITO" else "MEDIO",
                description=f"Lei de Benford: distribuição {result.status} em receitas mensais",
                detail={"mad": result.mad, "status": result.status, "digitos_desviantes": result.deviating_digits},
            )]
        return []

    def _cc06_zscore_despesas(self, fin: dict) -> list[CrossCheckFinding]:
        series = fin.get("serie_despesas_mensais")
        if not series or len(series) < 2:
            return []
        try:
            result: ZScoreResult = compute_zscore(series, column="despesas_mensais", threshold=3.0)
        except ValueError:
            return []
        if result.outliers:
            return [CrossCheckFinding(
                rule="CC06",
                severity="ALTO",
                description=f"Z-score: {len(result.outliers)} despesa(s) com desvio > 3σ",
                detail={"outliers": result.outliers, "media": result.mean, "desvio_padrao": result.std},
            )]
        return []

    def _cc07_liquidez(self, fin: dict) -> list[CrossCheckFinding]:
        ativo = fin.get("ativo_circulante")
        passivo = fin.get("passivo_circulante")
        if ativo is None or passivo is None or passivo <= 0:
            return []
        liquidez = ativo / passivo
        if liquidez < 0.5:
            return [CrossCheckFinding(
                rule="CC07",
                severity="CRITICO",
                description=f"Índice de Liquidez Corrente crítico: {liquidez:.2f} (< 0,50)",
                detail={"ativo_circulante": ativo, "passivo_circulante": passivo, "liquidez": round(liquidez, 4)},
            )]
        return []

    def _cc08_margem_ebitda(self, fin: dict) -> list[CrossCheckFinding]:
        ebitda = fin.get("ebitda")
        receita = fin.get("receita_liquida")
        if ebitda is None or receita is None or receita == 0:
            return []
        margem = ebitda / receita
        if margem < -0.30 or margem > 0.60:
            return [CrossCheckFinding(
                rule="CC08",
                severity="ALTO",
                description=f"Margem EBITDA implausível: {margem * 100:.1f}%",
                detail={"ebitda": ebitda, "receita_liquida": receita, "margem_pct": round(margem * 100, 1)},
            )]
        return []

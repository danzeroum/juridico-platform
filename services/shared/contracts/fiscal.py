"""
Contrato da camada FiscalEngine (NCM + ICMS) — módulo 9.

NcmTriageRequest  →  engine.classify()  →  NcmTriageResult

Determinístico por design (auditabilidade > sofisticação): dado o mesmo input e a
mesma base vigente, a saída é idêntica. `classify()` é puro (não toca o Decision
Ledger); a ancoragem no Ledger é etapa separada (individual = 1 entrada; lote = 1
entrada por job com raiz Merkle do lote — ver services/fiscal/batch/anchor.py).

Fundamentos legais embutidos:
- ICMS interestadual: Resolução do Senado Federal 22/1989 (7%/12%) e 13/2012 (4%
  para importado com conteúdo de importação > 40%). NÃO é matéria de CONFAZ.
- ICMS interno efetivo = alíquota modal + FCP/FECP (quando aplicável).
- DIFAL (EC 87/2015 + LC 190/2022) = max(0, interna_efetiva_destino − interestadual).
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

FISCAL_CONTRACT_VERSION = "fiscal/v1"

# Regiões para a regra geográfica do interestadual (Res. SF 22/1989).
# Origem Sul/Sudeste (exceto ES) → Norte/Nordeste/Centro-Oeste/ES: 7%. Caso contrário: 12%.
SUL_SUDESTE = frozenset({"SP", "RJ", "MG", "PR", "SC", "RS"})  # Sudeste + Sul, exceto ES
ALIQUOTA_INTER_REDUZIDA = 7.0
ALIQUOTA_INTER_PADRAO = 12.0
ALIQUOTA_INTER_IMPORTADO = 4.0
CONTEUDO_IMPORTACAO_LIMIAR = 40.0  # % — acima disso, importado usa 4% (Res. SF 13/2012)


class UF(StrEnum):
    AC = "AC"
    AL = "AL"
    AP = "AP"
    AM = "AM"
    BA = "BA"
    CE = "CE"
    DF = "DF"
    ES = "ES"
    GO = "GO"
    MA = "MA"
    MT = "MT"
    MS = "MS"
    MG = "MG"
    PA = "PA"
    PB = "PB"
    PR = "PR"
    PE = "PE"
    PI = "PI"
    RJ = "RJ"
    RN = "RN"
    RS = "RS"
    RO = "RO"
    RR = "RR"
    SC = "SC"
    SP = "SP"
    SE = "SE"
    TO = "TO"


class FonteRegra(StrEnum):
    TIPI   = "TIPI"      # lookup exato de NCM/IPI na TIPI da RFB
    SENADO = "SENADO"    # alíquota interestadual (Resolução do Senado)
    CONFAZ = "CONFAZ"    # convênio (benefício/ST/isenção)
    SEFAZ  = "SEFAZ"     # alíquota interna estadual
    FUZZY  = "FUZZY"     # NCM sugerido por correspondência aproximada de descrição
    RAG    = "RAG"       # NCM sugerido por busca semântica (Fase posterior)


class NcmCandidate(BaseModel):
    """NCM sugerido pela triagem, com origem da regra e confiança."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ncm_codigo:  str = Field(..., pattern=r"^\d{8}$")
    descricao:   str
    confidence:  float = Field(..., ge=0.0, le=1.0)
    fonte_regra: FonteRegra


class NcmTriageRequest(BaseModel):
    """Entrada da triagem de um item."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    descricao:              str = Field(..., min_length=1, max_length=2000)
    uf_origem:              UF
    uf_destino:             UF
    data:                   date | None = None
    ncm_hint:               str | None = Field(None, pattern=r"^\d{8}$")
    importado:              bool = False
    conteudo_importacao_pct: float | None = Field(None, ge=0.0, le=100.0)


class IcmsResolution(BaseModel):
    """Resolução de ICMS para a operação: interno efetivo, interestadual e DIFAL."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    interna_pct:          float | None = None
    fcp_pct:              float | None = None
    interna_efetiva_pct:  float | None = None
    interestadual_pct:    float | None = None
    difal_pct:            float | None = None
    fundamento_legal:     str | None = None


class NcmTriageResult(BaseModel):
    """Resultado da triagem de um item."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    sku_descricao:      str
    suggested_ncm:      NcmCandidate | None = None
    icms:               IcmsResolution
    categoria:          str | None = None
    conflito_detectado: bool = False
    observacoes:        list[str] = Field(default_factory=list)
    decision_proof:     str | None = None  # prova de inclusão (get_proof), preenchida na ancoragem
    contract_version:   str = FISCAL_CONTRACT_VERSION


class SpreadsheetJobResponse(BaseModel):
    """Resposta 202 do enriquecimento assíncrono de planilhas."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    job_id:              str
    status_url:          str
    submitted_at:        str
    expected_completion: str | None = None
    contract_version:    str = FISCAL_CONTRACT_VERSION


# ---------------------------------------------------------------------------
# Helpers puros (determinísticos, sem I/O) — reutilizados por triagem e testes.
# ---------------------------------------------------------------------------
_WS = re.compile(r"\s+")
_NON_ALNUM = re.compile(r"[^a-z0-9 ]+")


def normalize_descricao(s: str) -> str:
    """
    Normaliza descrição comercial para matching: minúsculas, sem acento,
    sem pontuação, espaços colapsados. Determinístico.
    """
    if not s:
        return ""
    nfkd = unicodedata.normalize("NFKD", s)
    sem_acento = "".join(c for c in nfkd if not unicodedata.combining(c))
    limpo = _NON_ALNUM.sub(" ", sem_acento.lower())
    return _WS.sub(" ", limpo).strip()


def aliquota_interestadual(
    uf_origem: str,
    uf_destino: str,
    *,
    importado: bool = False,
    conteudo_importacao_pct: float | None = None,
) -> tuple[float, str]:
    """
    Alíquota interestadual base (Resolução do Senado). Retorna (pct, fundamento).

    - Importado com conteúdo de importação > 40% → 4% (Res. SF 13/2012).
    - Origem Sul/Sudeste (exceto ES) → N/NE/CO/ES → 7% (Res. SF 22/1989).
    - Demais operações interestaduais → 12%.
    """
    if importado and (conteudo_importacao_pct is None or conteudo_importacao_pct > CONTEUDO_IMPORTACAO_LIMIAR):
        return ALIQUOTA_INTER_IMPORTADO, "Resolução SF 13/2012"

    origem_privilegiada = uf_origem in SUL_SUDESTE
    destino_beneficiado = (uf_destino not in SUL_SUDESTE) or (uf_destino == "ES")
    if origem_privilegiada and destino_beneficiado:
        return ALIQUOTA_INTER_REDUZIDA, "Resolução SF 22/1989 (art. 1º)"
    return ALIQUOTA_INTER_PADRAO, "Resolução SF 22/1989 (art. 1º)"


def compute_difal(interna_efetiva_destino: float | None, interestadual: float | None) -> float | None:
    """DIFAL = max(0, interna_efetiva_destino − interestadual). None se faltar dado."""
    if interna_efetiva_destino is None or interestadual is None:
        return None
    return round(max(0.0, interna_efetiva_destino - interestadual), 2)

"""
Extração de regras de convênios/protocolos do CONFAZ (PDF → texto → regras).

Estratégia (plano §4):
1. Texto nativo via pdfplumber (PDFs digitais) — rápido e confiável.
2. Fallback OCR (pymupdf render → pytesseract) só quando o texto nativo é curto
   demais (PDF escaneado). OCR é lento e falível — gated por disponibilidade do
   binário tesseract; nunca 100% confiável para dado fiscal.
3. Extração de regras via RuleParser plugável: LlmRuleParser (Ollama JSON mode) em
   produção, com HeuristicRuleParser (determinístico) como fallback e para testes.
   Toda regra sai com needs_review=True → validação humana antes de persistir.
"""
from __future__ import annotations

import io
import re
import shutil
from typing import Any, Protocol

_OCR_MIN_CHARS = 200  # abaixo disso, assume PDF escaneado → tenta OCR

_NCM_RE = re.compile(r"NCM\s*[:\-]?\s*(\d{4}\.?\d{2}\.?\d{2})", re.IGNORECASE)
_ALIQ_RE = re.compile(r"al[íi]quota[^.\d]{0,40}?(\d{1,2}(?:[.,]\d{1,2})?)\s*%", re.IGNORECASE)
_UF_PAREN_RE = re.compile(r"\(([A-Z]{2})\)")
_VIG_RE = re.compile(r"vig[êe]ncia[^\d]{0,40}?(\d{2}/\d{2}/\d{4})", re.IGNORECASE)
_ATO_RE = re.compile(r"(conv[êe]nio|protocolo)\s+ICMS\s+([\d./]+)", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Extração de texto
# ---------------------------------------------------------------------------
def native_text(pdf_bytes: bytes) -> str:
    """Texto nativo do PDF (pdfplumber). Vazio se o PDF for só imagem."""
    import pdfplumber

    parts: list[str] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            parts.append(page.extract_text() or "")
    return "\n".join(parts)


def tesseract_available() -> bool:
    return shutil.which("tesseract") is not None


def ocr_text(pdf_bytes: bytes, *, dpi: int = 300, lang: str = "por") -> str:  # pragma: no cover - requer binário tesseract
    """OCR de cada página (pymupdf → imagem → pytesseract). Requer tesseract."""
    import fitz  # pymupdf
    import pytesseract
    from PIL import Image

    parts: list[str] = []
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        for page in doc:
            pix = page.get_pixmap(dpi=dpi)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            parts.append(pytesseract.image_to_string(img, lang=lang))
    finally:
        doc.close()
    return "\n".join(parts)


def extract_text(pdf_bytes: bytes, *, ocr_min_chars: int = _OCR_MIN_CHARS) -> str:
    """Texto do PDF: nativo se suficiente, senão OCR (se disponível)."""
    native = native_text(pdf_bytes)
    if len(native.strip()) >= ocr_min_chars or not tesseract_available():
        return native
    try:  # pragma: no cover - requer binário tesseract
        return ocr_text(pdf_bytes)
    except Exception:
        return native


# ---------------------------------------------------------------------------
# Extração de regras
# ---------------------------------------------------------------------------
class RuleParser(Protocol):
    def parse(self, text: str) -> list[dict[str, Any]]: ...


class HeuristicRuleParser:
    """
    Parser determinístico (regex) — fallback do LLM e alvo dos testes.

    Para cada NCM citado, captura uma janela de contexto e extrai alíquota,
    UFs de origem/destino, vigência e o ato legal. Sempre needs_review=True.
    """

    def parse(self, text: str) -> list[dict[str, Any]]:
        if not text:
            return []
        ato_m = _ATO_RE.search(text)
        ato_ref = f"{ato_m.group(1)} ICMS {ato_m.group(2)}" if ato_m else None

        regras: list[dict[str, Any]] = []
        for m in _NCM_RE.finditer(text):
            ncm = re.sub(r"\D", "", m.group(1)).zfill(8)
            janela = text[max(0, m.start() - 200): m.end() + 300]

            aliq_m = _ALIQ_RE.search(janela)
            aliquota = float(aliq_m.group(1).replace(",", ".")) if aliq_m else None

            ufs = _UF_PAREN_RE.findall(janela)
            uf_origem = ufs[0] if ufs else None
            uf_destino = ufs[1] if len(ufs) > 1 else None

            vig_m = _VIG_RE.search(janela)
            vigencia = vig_m.group(1) if vig_m else None

            regras.append({
                "ncm": ncm,
                "aliquota_pct": aliquota,
                "uf_origem": uf_origem,
                "uf_destino": uf_destino,
                "vigencia_inicio": vigencia,
                "ato_ref": ato_ref,
                "needs_review": True,
            })
        return regras


class LlmRuleParser:
    """
    Parser via LLM local (Ollama, JSON mode) — primário em produção.

    Passa o texto bruto ao modelo com um schema e devolve regras estruturadas.
    Requer Ollama no ar; em falha, o chamador cai para HeuristicRuleParser.
    Coberto por E2E (não por unit — depende de serviço externo).
    """

    def __init__(self, model: str = "llama3:8b", ollama_url: str | None = None):
        self.model = model
        self.ollama_url = ollama_url

    def parse(self, text: str) -> list[dict[str, Any]]:  # pragma: no cover - requer Ollama
        import json
        import os

        import requests

        base = self.ollama_url or os.getenv("OLLAMA_URL", "http://ollama:11434")
        prompt = (
            "Extraia as regras fiscais deste texto de convênio CONFAZ como JSON no "
            'formato {"regras":[{"ncm","aliquota_pct","uf_origem","uf_destino",'
            '"vigencia_inicio","ato_ref"}]}. Texto:\n' + text
        )
        resp = requests.post(
            f"{base}/api/generate",
            json={"model": self.model, "prompt": prompt, "format": "json", "stream": False},
            timeout=120,
        )
        resp.raise_for_status()
        data = json.loads(resp.json()["response"])
        regras = data.get("regras", [])
        for r in regras:
            r["needs_review"] = True
        return regras


def parse_rules(text: str, parser: RuleParser | None = None) -> list[dict[str, Any]]:
    """Extrai regras usando o parser dado (default: heurístico determinístico)."""
    return (parser or HeuristicRuleParser()).parse(text)

"""
Teste REAL de extração de texto de PDF: gera um PDF de verdade (pymupdf) com o
texto de um convênio e extrai com pdfplumber — exercita o caminho de texto nativo.
Também cobre o guard do fallback OCR quando não há texto nem tesseract.
"""
from __future__ import annotations

import fitz  # pymupdf

from services.fiscal.ingestion.confaz_parse import (
    extract_text,
    native_text,
    tesseract_available,
)

CONVENIO = (
    "CONVÊNIO ICMS 45/2026\n"
    "Autoriza isenção nas operações interestaduais com o produto classificado no "
    "NCM 8471.30.12, com alíquota de 7%, nas remessas do Estado de São Paulo (SP) "
    "para o Estado da Bahia (BA). Vigência a partir de 01/01/2026."
)


def _text_pdf(texto: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_textbox(fitz.Rect(50, 50, 550, 750), texto, fontsize=11)
    return doc.tobytes()


def _empty_pdf() -> bytes:
    doc = fitz.open()
    doc.new_page()  # página sem texto
    return doc.tobytes()


class TestExtractText:
    def test_extrai_texto_nativo_de_pdf_real(self):
        pdf = _text_pdf(CONVENIO)
        texto = extract_text(pdf)
        assert "8471.30.12" in texto
        assert "CONV" in texto.upper()

    def test_native_text_direto(self):
        pdf = _text_pdf(CONVENIO)
        assert "Bahia" in native_text(pdf)

    def test_pdf_sem_texto_sem_tesseract_retorna_vazio(self):
        # Sem texto nativo e (neste ambiente) sem tesseract → retorna o nativo (curto).
        texto = extract_text(_empty_pdf())
        assert len(texto.strip()) < 200

    def test_tesseract_available_retorna_bool(self):
        assert isinstance(tesseract_available(), bool)

"""
Drivers reais de protocolo (automação de portal via Playwright).

SEGURANÇA / REALIDADE:
  - Só são acionados com PROTOCOLO_MODO=real (a fábrica decide).
  - Exigem credenciais do portal; sem elas, devolvem AGUARDA_CREDENCIAIS e NÃO
    tocam a rede.
  - O portal real exige login gov.br e normalmente CAPTCHA; o fluxo Playwright
    aqui é um SCAFFOLD: os seletores/etapas precisam ser mapeados contra o portal
    real (inacessível neste ambiente — host bloqueado pela allowlist). Enquanto
    isso, a tentativa real termina em FALHA com mensagem explicativa, sem nunca
    submeter algo incorreto.

Playwright é importado de forma tardia (lazy) para que o módulo seja importável
sem o pacote instalado.
"""
from __future__ import annotations

import logging

from services.defensor.protocolo.base import ProtocoloDriver, now_iso
from services.shared.config import settings
from services.shared.contracts.protocolo import (
    ProtocoloModo,
    ProtocoloRequest,
    ProtocoloResultado,
    ProtocoloStatus,
)

logger = logging.getLogger(__name__)


class _PlaywrightPortalDriver(ProtocoloDriver):
    """Base de driver real: gating de credenciais + automação de portal."""

    canal: str
    portal_url: str
    portal_nome: str

    def _credenciais(self) -> tuple[str, str]:
        raise NotImplementedError

    def _resultado(self, req, status, mensagem, numero=None, url=None) -> ProtocoloResultado:
        return ProtocoloResultado(
            canal=req.canal.value,
            modo=ProtocoloModo.REAL.value,
            status=status,
            numero_protocolo=numero,
            url=url,
            mensagem=mensagem,
            enviado_em=now_iso(),
        )

    def submit(self, req: ProtocoloRequest) -> ProtocoloResultado:
        user, password = self._credenciais()
        if not (user and password):
            return self._resultado(
                req,
                ProtocoloStatus.AGUARDA_CREDENCIAIS.value,
                f"Credenciais do {self.portal_nome} não configuradas — submissão real não tentada.",
            )
        try:
            return self._submit_real(req, user, password)
        except Exception as exc:  # nunca propaga — protocolar() depende disso
            logger.warning("Falha na submissão real %s: %s", self.portal_nome, exc)
            return self._resultado(
                req, ProtocoloStatus.FALHA.value, f"Falha na submissão real: {exc}"
            )

    def _submit_real(self, req: ProtocoloRequest, user: str, password: str) -> ProtocoloResultado:
        """
        Fluxo de automação do portal (scaffold).

        Lazy-import do Playwright; o ambiente já traz o Chromium pré-instalado.
        Os passos de login/preenchimento/captcha precisam ser mapeados contra o
        portal real antes de habilitar — por isso, por ora, sinaliza FALHA
        controlada em vez de submeter algo incorreto.
        """
        from playwright.sync_api import sync_playwright  # noqa: F401

        # Esboço do fluxo (a completar com seletores reais do portal):
        #   with sync_playwright() as pw:
        #       browser = pw.chromium.launch(headless=True)
        #       page = browser.new_page()
        #       page.goto(self.portal_url)
        #       self._login(page, user, password)        # gov.br SSO
        #       self._resolver_captcha(page)              # requer serviço externo
        #       self._preencher_reclamacao(page, req)
        #       numero = self._submeter(page)
        #       return self._resultado(req, ENVIADO, "...", numero=numero, url=...)
        raise NotImplementedError(
            f"Automação do {self.portal_nome} requer mapeamento de seletores e "
            "tratamento de login gov.br/captcha contra o portal real (host bloqueado neste ambiente)."
        )


class ConsumidorGovDriver(_PlaywrightPortalDriver):
    canal = "CONSUMIDOR_GOV"
    portal_url = "https://www.consumidor.gov.br"
    portal_nome = "Consumidor.gov"

    def _credenciais(self) -> tuple[str, str]:
        return settings.CONSUMIDOR_GOV_USER, settings.CONSUMIDOR_GOV_PASSWORD


class ProconSPDriver(_PlaywrightPortalDriver):
    canal = "PROCON"
    portal_url = "https://www.procon.sp.gov.br"
    portal_nome = "Procon-SP"

    def _credenciais(self) -> tuple[str, str]:
        return settings.PROCON_SP_USER, settings.PROCON_SP_PASSWORD

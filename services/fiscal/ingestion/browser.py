"""
Fetch de HTML renderizado via Playwright — para portais SEFAZ com JS dinâmico.

Preferir a API REST interna do portal quando existir (mais leve); este módulo é o
fallback que renderiza o DOM. Resolve o executável do Chromium de forma robusta:
usa PLAYWRIGHT_EXECUTABLE se definido, senão procura o build pré-instalado em
PLAYWRIGHT_BROWSERS_PATH (headless_shell primeiro — compatível com o modo old-headless
que o Playwright invoca — depois o chromium completo).

Em produção o Dockerfile do worker instala o Chromium; ver docker/ e o plano.
"""
from __future__ import annotations

import glob
import os

_DEFAULT_ARGS = ["--no-sandbox", "--disable-dev-shm-usage"]


def resolve_chromium_executable() -> str | None:
    """Caminho do binário do Chromium, ou None para deixar o Playwright decidir."""
    env = os.getenv("PLAYWRIGHT_EXECUTABLE")
    if env and os.path.exists(env):
        return env
    base = os.getenv("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers")
    patterns = [
        os.path.join(base, "chromium_headless_shell-*/chrome-linux/headless_shell"),
        os.path.join(base, "chromium-*/chrome-linux/chrome"),
    ]
    for pat in patterns:
        hits = sorted(glob.glob(pat))
        if hits:
            return hits[-1]
    return None


def fetch_html(
    url: str,
    *,
    wait_selector: str | None = None,
    timeout_ms: int = 20_000,
    user_agent: str | None = None,
) -> str:
    """
    Abre `url` num Chromium headless e devolve o HTML renderizado (pós-JS).
    Levanta se o navegador não estiver disponível — o chamador (task Celery)
    trata com circuit breaker/cache.
    """
    from playwright.sync_api import sync_playwright

    ua = user_agent or (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    exe = resolve_chromium_executable()
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=exe, headless=True, args=_DEFAULT_ARGS)
        try:
            page = browser.new_context(user_agent=ua).new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            if wait_selector:
                page.wait_for_selector(wait_selector, timeout=timeout_ms)
            return page.content()
        finally:
            browser.close()

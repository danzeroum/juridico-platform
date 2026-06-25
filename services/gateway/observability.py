"""
Helper de observabilidade compartilhado entre os routers.

Substitui o boilerplate `_OTEL`/`_tracer`/`_noop_span` que era duplicado em cada
router por um único context manager `span(...)` com degradação graciosa quando o
OpenTelemetry não está instalado.

Uso:
    from services.gateway.observability import span
    with span("petibot.assemble", {"tipo_acao": case.tipo_acao.value}):
        ...

Atributos com valor None são ignorados; chaves podem conter ponto
(ex.: "descricao.len"), por isso são passadas como dict e não como kwargs.
"""
from __future__ import annotations

from contextlib import contextmanager

try:
    from opentelemetry import trace as _otel_trace
    _OTEL = True
except ImportError:  # OTel é opcional
    _OTEL = False
    _otel_trace = None  # type: ignore[assignment]


@contextmanager
def span(name: str, attributes: dict | None = None):
    """Abre um span OTel nomeado (ou no-op se a lib não estiver disponível)."""
    if not _OTEL:
        yield None
        return
    tracer = _otel_trace.get_tracer(name.split(".", 1)[0])
    with tracer.start_as_current_span(name) as sp:
        for key, value in (attributes or {}).items():
            if value is not None:
                sp.set_attribute(key, value)
        yield sp

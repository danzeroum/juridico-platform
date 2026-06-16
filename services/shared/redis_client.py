"""
Cliente Redis compartilhado.
Usado para cache de LLM, sessoes e filas Celery.
"""

import redis
from shared.config import settings

_redis_client = None


def get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
        )
    return _redis_client

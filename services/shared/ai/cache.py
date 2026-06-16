"""
Cache estrategico para chamadas LLM.
Evita reprocessar prompts identicos - economia de custo significativa.
Chave: hash(modelo + versao_template + prompt)
TTL: 30 dias
"""

import hashlib
import json
import logging
from functools import wraps
from shared.redis_client import get_redis

logger = logging.getLogger(__name__)


class LLMMemoizer:
    """Cache de respostas LLM com invalidacao por versao de template."""

    def __init__(self):
        self.ttl = 30 * 24 * 3600  # 30 dias

    def __call__(self, model: str = "gpt-4o"):
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                prompt = kwargs.get("prompt") or (args[0] if args else "")
                template_ver = getattr(func, "__version__", "1")

                cache_key = hashlib.sha256(
                    f"{model}:{template_ver}:{str(prompt)}".encode()
                ).hexdigest()

                r = get_redis()
                cached = r.get(f"llm:{cache_key}")

                if cached:
                    logger.info(f"LLM cache HIT: {cache_key[:8]}...")
                    return json.loads(cached)

                result = func(*args, **kwargs)
                r.setex(f"llm:{cache_key}", self.ttl, json.dumps(result))
                logger.info(f"LLM cache SET: {cache_key[:8]}...")
                return result

            return wrapper
        return decorator


memoizer = LLMMemoizer()

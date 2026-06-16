from pathlib import Path
import os


def load_secret(name: str) -> str:
    path = Path('/run/secrets') / name
    if path.exists():
        return path.read_text().strip()
    return os.getenv(name.upper(), '')

"""
Conexao com PostgreSQL via SQLAlchemy + PgBouncer.
SEMPRE conectar via PgBouncer (porta 6432), nunca direto ao PostgreSQL.
"""

import logging

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from shared.config import settings

logger = logging.getLogger(__name__)

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Dependency injection para FastAPI."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

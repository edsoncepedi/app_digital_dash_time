# auxiliares/models_ordens.py
from __future__ import annotations

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class OrdemProducao(Base):
    __tablename__ = "ordens_producao"

    id = Column(Integer, primary_key=True, autoincrement=True)

    codigo_op = Column(String(64), unique=True, nullable=False, index=True)  # ex: OP000123
    produto = Column(String(120), nullable=False)
    descricao = Column(Text, nullable=True)

    meta = Column(Integer, nullable=False, default=0)

    # ABERTA | EM_EXECUCAO | FINALIZADA
    status = Column(String(20), nullable=False, default="ABERTA")

    criada_em = Column(DateTime, nullable=False, default=datetime.utcnow)
    atualizada_em = Column(DateTime, nullable=False, default=datetime.utcnow)

def inicializa_ordens(engine) -> None:
    """Cria a tabela no Postgres, se ainda não existir."""
    Base.metadata.create_all(bind=engine)

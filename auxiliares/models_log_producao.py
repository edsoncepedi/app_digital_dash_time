from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import declarative_base

BaseLogProducao = declarative_base()

class LogProducao(BaseLogProducao):
    __tablename__ = "log_producao"

    id = Column(Integer, primary_key=True, autoincrement=True)

    ordem_codigo = Column(String(50), nullable=False)
    meta = Column(Integer, nullable=False)

    status = Column(String(20), nullable=False, default="ARMED")

    armada_em = Column(DateTime, default=datetime.utcnow)
    inicio_em = Column(DateTime, nullable=True)
    fim_em = Column(DateTime, nullable=True)

    motivo_fim = Column(String(120), nullable=True)
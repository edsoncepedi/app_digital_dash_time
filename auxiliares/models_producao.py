from sqlalchemy import Column, Integer, String, Float, DateTime
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()

class LogEventoProducao(Base):
    """
    Log por peça/posto (eventos de produção).
    NÃO confundir com log_producao (sessão Start->Stop).
    """
    __tablename__ = "log_eventos_producao"

    id = Column(Integer, primary_key=True)
    ordem_codigo = Column(String(50), nullable=False)
    produto_codigo = Column(String(100))

    posto_nome = Column(String(50), nullable=False)
    funcionario_id = Column(Integer)

    tempo_preparo = Column(Float)
    tempo_montagem = Column(Float)
    tempo_espera = Column(Float)
    tempo_transferencia = Column(Float)
    tempo_ciclo = Column(Float)

    data_registro = Column(DateTime, default=datetime.utcnow)

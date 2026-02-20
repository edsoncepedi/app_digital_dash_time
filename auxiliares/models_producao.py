from sqlalchemy import Column, Integer, String, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class LogProducao(Base):
    __tablename__ = "log_producao"

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

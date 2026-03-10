from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, relationship
from auxiliares.models_ordens import OrdemProducao
from auxiliares.utils import agora_sp
from auxiliares.db_base import Base


class LogProducao(Base):
    __tablename__ = "log_producao"

    id = Column(Integer, primary_key=True)

    ordem_id = Column(Integer, ForeignKey("ordens_producao.id"))

    meta = Column(Integer)

    status = Column(String(20), default="ARMED")

    armada_em = Column(DateTime, default=agora_sp)
    inicio_em = Column(DateTime)
    fim_em = Column(DateTime)

    motivo_fim = Column(String(120))

    ordem = relationship(OrdemProducao)
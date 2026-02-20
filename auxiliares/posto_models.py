# auxiliares/posto_models.py
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime
from sqlalchemy.sql import func

BaseProducao = declarative_base()

def make_posto_model(table_name: str):
    """
    Cria dinamicamente um Model para a tabela do posto.
    table_name exemplo: 'posto_0', 'posto_1', ...
    """
    class PostoHistorico(BaseProducao):
        __tablename__ = table_name

        id = Column(Integer, primary_key=True, autoincrement=True)

        # produto pode começar NULL e ser preenchido depois (seu caso)
        produto = Column(String(80), nullable=True)
        palete = Column(String(80), nullable=True)     # opcional, mas recomendo

        # seus 5 tempos (mesmos nomes do CSV)
        tempo_preparo = Column(Float, nullable=True)
        tempo_montagem = Column(Float, nullable=True)
        tempo_espera = Column(Float, nullable=True)
        tempo_transferencia = Column(Float, nullable=True)
        tempo_ciclo = Column(Float, nullable=True)

        # marca se essa “linha” ainda está em andamento
        aberta = Column(Boolean, nullable=False, default=True)

        criado_em = Column(DateTime(timezone=True), server_default=func.now())

    return PostoHistorico
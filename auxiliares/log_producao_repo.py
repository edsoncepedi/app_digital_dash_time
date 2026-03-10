from datetime import datetime
from sqlalchemy.orm import sessionmaker
from auxiliares.models_log_producao import LogProducao
from auxiliares.db_base import Base

class LogProducaoRepo:

    def __init__(self, engine):
        Base.metadata.create_all(bind=engine)
        self.SessionLocal = sessionmaker(bind=engine)

    def criar(self, ordem_id, meta):
        session = self.SessionLocal()
        try:
            log = LogProducao(
                ordem_id=ordem_id,
                meta=meta,
                status="ARMED",
                armada_em=datetime.now()
            )
            session.add(log)
            session.commit()
            return log.id
        finally:
            session.close()

    def marcar_inicio(self, log_id):
        session = self.SessionLocal()
        try:
            log = session.get(LogProducao, log_id)
            if log:
                log.status = "ON"
                log.inicio_em = datetime.now()
                session.commit()
        finally:
            session.close()

    def finalizar(self, log_id, motivo):
        session = self.SessionLocal()
        try:
            log = session.get(LogProducao, log_id)
            if log:
                log.status = "FINALIZADA"
                log.fim_em = datetime.now()
                log.motivo_fim = motivo
                session.commit()
        finally:
            session.close()
from datetime import datetime
from sqlalchemy.orm import sessionmaker
from auxiliares.models_log_producao import LogProducao, BaseLogProducao

class LogProducaoRepo:

    def __init__(self, engine):
        BaseLogProducao.metadata.create_all(bind=engine)
        self.SessionLocal = sessionmaker(bind=engine)

    def criar(self, ordem_codigo, meta):
        session = self.SessionLocal()
        try:
            log = LogProducao(
                ordem_codigo=ordem_codigo,
                meta=meta,
                status="ARMED"
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
                log.inicio_em = datetime.utcnow()
                session.commit()
        finally:
            session.close()

    def finalizar(self, log_id, motivo):
        session = self.SessionLocal()
        try:
            log = session.get(LogProducao, log_id)
            if log:
                log.status = "FINALIZADA"
                log.fim_em = datetime.utcnow()
                log.motivo_fim = motivo
                session.commit()
        finally:
            session.close()
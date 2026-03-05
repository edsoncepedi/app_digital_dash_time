# auxiliares/db.py
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager
from auxiliares.banco_post import Conectar_DB

# Engines por banco (cache)
_ENGINES = {}
_SESSIONS = {}

def get_engine(db_name: str = "funcionarios"):
    if db_name not in _ENGINES:
        _ENGINES[db_name] = Conectar_DB(db_name)  # seu helper que retorna engine
    return _ENGINES[db_name]

def get_sessionmaker(db_name: str = "funcionarios"):
    if db_name not in _SESSIONS:
        engine = get_engine(db_name)
        _SESSIONS[db_name] = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return _SESSIONS[db_name]

@contextmanager
def session_scope(db_name: str = "funcionarios"):
    SessionLocal = get_sessionmaker(db_name)
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
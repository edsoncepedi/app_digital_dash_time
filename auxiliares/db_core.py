# auxiliares/db_core.py
from sqlalchemy import create_engine
from auxiliares.configuracoes import ip

def Conectar_DB(DB_NAME: str):
    DB_HOST = ip
    DB_USER = "postgres"
    DB_PASSWORD = "cepedi123"  # ideal: trocar para env depois
    DB_PORT = "5432"
    return create_engine(f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}")
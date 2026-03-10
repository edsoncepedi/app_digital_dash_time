from auxiliares.db_base_prod import BaseProd
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime
from datetime import datetime


def make_posto_model(table_name: str):

    class_name = f"PostoHistorico_{table_name}"

    return type(
        class_name,
        (BaseProd,),
        {
            "__tablename__": table_name,

            "id": Column(Integer, primary_key=True, autoincrement=True),

            "produto": Column(String(80), nullable=True),
            "palete": Column(String(80), nullable=True),
            "ordem_producao": Column(String(80), nullable=True),

            "tempo_preparo": Column(Float, nullable=True),
            "tempo_montagem": Column(Float, nullable=True),
            "tempo_espera": Column(Float, nullable=True),
            "tempo_transferencia": Column(Float, nullable=True),
            "tempo_ciclo": Column(Float, nullable=True),

            "aberta": Column(Boolean, nullable=False, default=True),

            "criado_em": Column(DateTime, default=datetime.now),
        }
    )
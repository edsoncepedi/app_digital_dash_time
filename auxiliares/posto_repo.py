# auxiliares/posto_repo.py
from sqlalchemy.orm import sessionmaker
from auxiliares.banco_post import Conectar_DB
from auxiliares.configuracoes import ultimo_posto_bios
from auxiliares.posto_models import BaseProducao, make_posto_model

DB_PRODUCAO = "producao"  # banco separado (não usar 'funcionarios')

engine_producao = Conectar_DB(DB_PRODUCAO)  # usa seu Conectar_DB :contentReference[oaicite:2]{index=2}
SessionProducao = sessionmaker(bind=engine_producao)

# dict: 'posto_0' -> ModelClass
POSTO_MODELS = {}

def init_postos_models():
    for i in range(ultimo_posto_bios + 1):
        nome = f"posto_{i}"
        POSTO_MODELS[nome] = make_posto_model(nome)

    # cria todas as tabelas definidas no Base
    BaseProducao.metadata.create_all(bind=engine_producao)

def criar_linha_aberta(posto_nome: str, palete: str | None = None) -> int:
    Model = POSTO_MODELS[posto_nome]
    session = SessionProducao()
    try:
        row = Model(produto=None, palete=palete, aberta=True)
        session.add(row)
        session.commit()
        session.refresh(row)
        return int(row.id)
    finally:
        session.close()

def atualizar_produto_db(posto_nome: str, row_id: int, produto: str):
    Model = POSTO_MODELS[posto_nome]
    session = SessionProducao()
    try:
        row = session.get(Model, row_id)
        if not row:
            return
        row.produto = str(produto)
        session.commit()
    finally:
        session.close()

def atualizar_tempo_db(posto_nome: str, row_id: int, campo: str, valor: float):
    """
    campo deve ser um desses:
    tempo_preparo, tempo_montagem, tempo_espera, tempo_transferencia, tempo_ciclo
    """
    Model = POSTO_MODELS[posto_nome]
    session = SessionProducao()
    try:
        row = session.get(Model, row_id)
        if not row:
            return
        setattr(row, campo, float(valor))
        session.commit()
    finally:
        session.close()

def fechar_linha(posto_nome: str, row_id: int):
    Model = POSTO_MODELS[posto_nome]
    session = SessionProducao()
    try:
        row = session.get(Model, row_id)
        if not row:
            return
        row.aberta = False
        session.commit()
    finally:
        session.close()
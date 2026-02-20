from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
import pandas as pd
from auxiliares.configuracoes import ip
from auxiliares.db_writer import db_writer, InsertJob
import threading
from auxiliares.db_core import Conectar_DB



def inserir_dados(df: pd.DataFrame, dataframe: str, tabela: str):
    job = InsertJob(df=df, db_name=dataframe, table=tabela, max_retries=5)
    ok = db_writer.submit(job)
    if not ok:
        print(f"[DB] FILA CHEIA: descartando insert em {tabela}. (considere aumentar max_queue ou reduzir taxa)")

def verifica_conexao_banco(db):
    """
    Uma função que tenta se conectar ao banco de dados. E retorna Verdadeiro se conseguir conectar ou Falso se a tentativa for falha.
    :return: True ou False para a conexão com o banco de dados.
    """
    try:
        with db.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except OperationalError:
        return False

def Leitura_DB(engine, sql):
    if engine is None:
        print("Conexao invalida. Verifique o banco de dados.")
        return None

    try:
        with engine.connect() as conn:
            df = pd.read_sql(sql, conn)
            return df

    except Exception as e:
        print(f" Erro ao ler dados: {e}")
        return None

def consulta_produto_assoc(palete_lido):
    db = Conectar_DB('paletes')
    if verifica_conexao_banco(db):
        df = Leitura_DB(db, "select * from paletes")
        lista_paletes = df['palete'].tolist()
        if palete_lido in lista_paletes:
            filtro = df['palete'] == palete_lido
            produto = df[filtro]['produto'].item()
            return produto
        else:
            return 'Erro'
    return None

def consulta_funcionario_posto(nome_posto: str):
    db = Conectar_DB('funcionarios')  # ou o nome do seu banco onde estão as tabelas
    if not verifica_conexao_banco(db):
        return None

    # JOIN entre posto e funcionario para pegar nome + imagem
    sql = f"""
        SELECT f.nome, f.imagem_path
        FROM posto p
        LEFT JOIN funcionario f ON f.id = p.funcionario_id
        WHERE p.nome = '{nome_posto}'"""

    df = Leitura_DB(db, sql)

    if df is None or df.empty:
        # nenhum funcionário associado a esse posto
        return None

    linha = df.iloc[0]
    return linha["nome"], linha["imagem_path"]
    

def consulta_paletes():
    db = Conectar_DB('paletes')
    if verifica_conexao_banco(db):
        df = Leitura_DB(db, "select * from paletes")
        lista_paletes = df['palete'].tolist()
        return lista_paletes
    else:
        return 'Erro'

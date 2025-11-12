from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
import pandas as pd
from auxiliares.configuracoes import ip
import threading

# DB Credentials - PostgreSQL
def Conectar_DB(DB_NAME):
    try:
        DB_HOST = ip  # Altere se necessário
        DB_USER = 'postgres'
        DB_PASSWORD = 'cepedi123'
        DB_PORT = '5432'

        engine = create_engine(f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}')
        return engine

    except Exception as e:
        print(f"Erro ao conectar ao banco de dados: {e}")
        return None


def inserir_dados(df, dataframe, tabela):
    def worker():
        try:
            # Conectar ao banco de dados
            engine = Conectar_DB(dataframe)

            # Inserir os dados do DataFrame na tabela 'sensor_data'
            df.to_sql(tabela, engine, if_exists='append', index=False)
            print(f"[DB] Dados inseridos na tabela '{tabela}' com sucesso.")
        except Exception as e:
            print(f"[ERRO] Falha ao salvar no banco: {e}")
    threading.Thread(target=worker).start()

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

def consulta_paletes():
    db = Conectar_DB('paletes')
    if verifica_conexao_banco(db):
        df = Leitura_DB(db, "select * from paletes")
        lista_paletes = df['palete'].tolist()
        return lista_paletes
    else:
        return 'Erro'

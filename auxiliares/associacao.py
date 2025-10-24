from sqlalchemy import Column, String, Integer
from sqlalchemy.orm import declarative_base
from auxiliares.banco_post import Conectar_DB

def inicializa_Base_assoc():
    db = Conectar_DB('paletes')

    Base = declarative_base()

    #Criação da tabela de associações, onde está localizado o histórico de todas as associações.
    class Associacao(Base):
        __tablename__ = "associacoes"
        id = Column("id", Integer, primary_key=True, autoincrement=True)      #Coluna de id, do tipo Inteiro, sendo a primary_key.
        palete = Column("palete", String)                                     #Coluna de Palete, do tipo String.
        produto = Column("produto", String)                                   #Coluna de Produto, do tipo String.
        horario = Column("horario", String)                                   #Coluna de Horário, do tipo String.

        # Modelo de como as informações são passadas para a função e posteriormente são levadas ao banco de dados.
        def __init__(self, palete, produto, horario):
            self.palete = palete
            self.produto = produto
            self.horario = horario

    # Fim da sintaxe para a criação da tabela caso não existam.
    Base.metadata.create_all(bind=db)


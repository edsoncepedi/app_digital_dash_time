from sqlalchemy import Column, String, Integer, Date, Numeric, ForeignKey
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from auxiliares.banco_post import Conectar_DB
from auxiliares.configuracoes import ultimo_posto_bios

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

def inicializa_funcionario():
    engine = Conectar_DB('funcionarios')
    Base = declarative_base()

    class Funcionario(Base):
        __tablename__ = "funcionario"

        id = Column(Integer, primary_key=True)
        nome = Column(String(100), nullable=False)
        data_nascimento = Column(Date, nullable=False)
        horas_trabalho = Column(Numeric(5, 2), default=8.00)
        imagem_path = Column(String(255))
        rfid_tag = Column(String(32), nullable=False, unique=True)
    
    class Posto(Base):
        __tablename__ = "posto"

        id = Column(Integer, primary_key=True)
        nome = Column(String(50), nullable=False, unique=True)
        funcionario_id = Column(Integer, ForeignKey("funcionario.id"), unique=True)

        funcionario = relationship("Funcionario", lazy="joined")

    # cria a tabela se não existir (não apaga dados existentes)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    qtd_postos = ultimo_posto_bios

    try:
        for i in range(0, qtd_postos + 1):
            nome = f"posto_{i}"
            existente = session.query(Posto).filter_by(nome=nome).first()
            if not existente:
                session.add(Posto(nome=nome))
        session.commit()
    finally:
        session.close()
    return Funcionario, Posto


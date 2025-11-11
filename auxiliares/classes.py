import pandas as pd
import os
from datetime import datetime
import time
from auxiliares.configuracoes import ultimo_posto_bios, cartao_palete
from auxiliares.utils import verifica_palete_nfc, verifica_cod_produto


hora_inicio = time.perf_counter()
producao = False
postos = {}

def inicia_producao():
    global producao
    if not producao:
        producao = True

def verifica_estado_producao():
    return producao

def inicializar_postos(mqttc):
    global postos  # apenas declarar o uso da variável global
    for i in range(ultimo_posto_bios+1):
        postos[f"posto_{i}"] = Posto(f"posto_{i}", mqttc)
    print("[INFO] Postos inicializados:")
    for nome in postos.keys():
        print(f"    - {nome}")

class Tabela_Assoc:
    def __init__(self, entrada):
        self.nome = entrada.lower()
        self.csvPath = f"{self.nome}.csv"
        self.df_assoc = self.carregarDados()

    def carregarDados(self):
        if os.path.exists(self.csvPath):
            print(f"[{self.nome}] Carregando dados Locais.")
            return pd.read_csv(self.csvPath)
        else:
            print(f"[{self.nome}] Dados Locais n encontrados.")
            return pd.DataFrame(columns=[
                "produto",
                "palete",
                "horario"
            ])

    def salvarDadosLocais(self):
        self.df_assoc.to_csv(self.csvPath, index=False)
        print(f"[{self.nome}] Dados salvos com sucesso.")

    def paletes_assoc(self):
        return self.df_assoc['palete'].tolist()

    def associa(self, palete, produto):
        horario = str(datetime.now().strftime("%d/%m/%Y, %H:%M:%S"))
        dado = pd.DataFrame([{
            'palete': palete,
            'produto': produto,
            'horario': horario
        }])
        dado.to_csv(f"historico_{self.csvPath}", index=False, mode='a', header=False)
        self.df_assoc = pd.concat([self.df_assoc, dado], ignore_index=True)
        self.salvarDadosLocais()

    def desassocia(self, produto):
        self.df_assoc = self.df_assoc[self.df_assoc['produto'] != produto]
        self.df_assoc = self.df_assoc.reset_index(drop=True)
        self.salvarDadosLocais()

    def palete_produto(self, palete):
        paletes = self.paletes_assoc()
        if palete in paletes:
            resultado = self.df_assoc[self.df_assoc['palete'] == palete]
            produto = resultado['produto'].values[0]
            return produto
        else:
            return 'Erro'

associacoes = Tabela_Assoc('associacoes')

"""
class Produto:
    def __init__ (self, codigo_produto):
        self.codigo_produto = codigo_produto
        self.df_historico = pd.DataFrame(columns=[
            "codigo_posto",
            "inter_arrival_time",
            "tempo_preparo",
            "tempo_montagem",
            "tempo_espera",
            "tempo_transferencia",
            "tempo_ciclo",
            "hora"
        ])
        
    def registrar_passagem(self, tempos: pd.DataFrame):
        #Adiciona uma linha no DataFrame com os tempos do produto.
        :param produto: instância de Produto
        :param tempos: dicionário com os tempos

        self.df_historico = pd.concat([self.df_historico, tempos], ignore_index=True)"""

class Posto:
    def __init__ (self, posto, mqttc):
        self.id_posto = posto
        self.n_posto = int(posto.split("_")[1])
        if self.n_posto > 0:
            self.posto_anterior = f"posto_{self.n_posto - 1}"
        if self.n_posto < ultimo_posto_bios:
            self.posto_posterior = f"posto_{self.n_posto + 1}"
        self.nome = posto.upper()
        self.csvPath = f"{self.nome}.csv"
        self.XlsPath = f"{self.nome}.xlsx"
        self.df_historico = self.carregarDados()
        self.produto_atual = None
        self.palete_atual = None
        self.maquina_estado = 0
        self.maquina_estado_anterior = 0
        self.timestamp = {"BS": None, "BT1": None, "BT2": None, "BD": time.perf_counter()}
        self.BS_posterior = None
        self.BD_backup = None
        self.mqttc = mqttc

    # === Cria nova linha para o produto ===
    def inicia_montagem(self, arrival):
        nova_linha = {
            "produto": None,
            "arrival_time": arrival,
            "tempo_preparo": None,
            "tempo_montagem": None,
            "tempo_espera": None,
            "tempo_transferencia": None,
            "tempo_ciclo": None,
            "hora": str(datetime.now().strftime("%d/%m/%Y, %H:%M:%S"))
        }

        self.df_historico = pd.concat([self.df_historico, pd.DataFrame([nova_linha])], ignore_index=True)
        self.salvarDadosLocais()

    def inicia_produto(self, produto):
        self.produto_atual = produto
        nova_linha = {
            "produto": produto,
            "tempo_preparo": None,
            "tempo_montagem": None,
            "tempo_transferencia": None,
            "hora": datetime.now()
        }
        self.df_historico = pd.concat([self.df_historico, pd.DataFrame([nova_linha])], ignore_index=True)
        self.salvarDadosLocais()
        print(f"[{self.nome}] Novo produto iniciado: {produto}")
    
    def atualizar_tempo(self, produto, tipo_tempo, valor):
        if produto != None:
            if produto not in self.df_historico["produto"].values:
                print(f"[{self.nome}] Produto {produto} não encontrado, criando nova linha.")
                self.iniciar_produto(produto)

            self.df_historico.loc[self.df_historico["produto"] == produto, tipo_tempo] = valor
            self.salvarDadosLocais()
            print(f"[{self.nome}] {tipo_tempo} do produto {produto} atualizado ({valor:.2f}s)")
        else:
            if len(self.df_historico) == 0:
                print(f"[{self.nome}] Nenhum registro ativo para atualizar.")
                return
            idx = self.df_historico.index[-1]
            self.df_historico.at[idx, tipo_tempo] = valor
            self.salvarDadosLocais()
            print(f"[{self.nome}] {tipo_tempo} atualizado com {valor:.2f}s.")

    def atualiza_produto(self, produto):
        if len(self.df_historico) == 0:
            print(f"[{self.nome}] Nenhuma linha para associar produto.")
            return

        # pega o último índice (último BS registrado)
        idx = self.df_historico.index[-1]
        self.df_historico.at[idx, "produto"] = produto
        self.salvarDadosLocais()
        print(f"[{self.nome}] Produto {produto} associado à última entrada (linha {idx}).")

    def calcula_transporte(self):
        if self.n_posto > 0:
            self.BS_posterior = time.perf_counter()
            transporte = self.BS_posterior - self.BD_backup
            self.atualizar_tempo(self.produto_atual, "tempo_transferencia", transporte)

    def tratamento_dispositivo(self, payload):
        if payload in self.timestamp.keys():
            self.timestamp[payload] = time.perf_counter()

            if payload == 'BS':
                postos[self.posto_anterior].calcula_transporte()
                if self.maquina_estado == 0:
                    print(f'[{self.nome}] - ESTADO 1 - BS')
                    arrival = self.timestamp['BS'] - self.timestamp['BD']
                    self.inicia_montagem(arrival)

                    self.maquina_estado_anterior = self.maquina_estado
                    self.maquina_estado = 1
                return

            if payload == 'BT1':
                if self.maquina_estado == 1:
                    print(f'[{self.nome}] - ESTADO 2 - BT1')
                    preparo = self.timestamp['BT1'] - self.timestamp['BS']
                    self.atualizar_tempo(self.produto_atual, "tempo_preparo", preparo)
                    self.maquina_estado_anterior = self.maquina_estado
                    self.maquina_estado = 2
                return

            if payload == 'BT2':
                if self.maquina_estado == 2:
                    print(f'[{self.nome}] - ESTADO 3 - BT2')
                    montagem = self.timestamp['BT2'] - self.timestamp['BT1']
                    self.atualizar_tempo(self.produto_atual, "tempo_montagem", montagem)

                    self.maquina_estado_anterior = self.maquina_estado
                    self.maquina_estado = 3
                return

            if payload == 'BD':
                if self.maquina_estado == 3:
                    print(f'[{self.nome}] - ESTADO 4 - BD')
                    if self.produto_atual != None:
                        espera = self.timestamp['BD'] - self.timestamp['BT2']
                        self.atualizar_tempo(self.produto_atual, "tempo_espera", espera)

                        if self.id_posto == f"posto_0":
                            self.atualiza_produto(associacoes.palete_produto(self.palete_atual))

                        if self.id_posto == f"posto_{ultimo_posto_bios}":
                            associacoes.desassocia(self.produto_atual)

                        self.produto_atual = None
                        self.palete_atual = None
                        self.BD_backup = time.perf_counter()
                        self.maquina_estado = 0
                        self.maquina_estado_anterior = 3
                return
        elif verifica_palete_nfc(payload):
            if self.id_posto == "posto_0":
                self.palete_atual = cartao_palete[payload]
            else:
                self.tratamento_palete(cartao_palete[payload])

    def tratamento_palete(self, palete):
        produto_lido = associacoes.palete_produto(palete)
        if verifica_cod_produto(produto_lido):
            self.palete_atual = palete
            self.produto_atual = produto_lido
            self.atualiza_produto(self, self.produto_atual)
        else:
            print(f"[{self.nome}] - {palete} não foi associado.")

    def carregarDados(self):
        if os.path.exists(self.csvPath):
            print(f"[{self.nome}] Carregando dados Locais.")
            return pd.read_csv(self.csvPath)
        else:
            print(f"[{self.nome}] Dados Locais n encontrados.")
            return pd.DataFrame(columns=[
            "produto",
            "arrival_time",
            "tempo_preparo",
            "tempo_montagem",
            "tempo_espera",
            "tempo_transferencia",
            "tempo_ciclo",
            "hora"
        ])

    def salvarDadosLocais(self):
        self.df_historico.to_csv(self.csvPath, index=False)
        self.df_historico.to_excel(self.XlsPath, index=False)
        print(f"[{self.nome}] Dados salvos com sucesso.")

def trata_mensagem_DD(message):
    if message.topic.split("/")[0] == 'rastreio_nfc' and producao:
        dispositivo = message.topic.split("/")[2]
        agente = message.topic.split("/")[3]
        payload = str(str(message.payload).split("'")[1])
        if agente == 'dispositivo':
            postos[dispositivo].tratamento_dispositivo(payload)
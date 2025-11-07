import pandas as pd
import os
from datetime import datetime
from auxiliares.utils import verifica_cod_produto, verifica_palete, verifica_palete_nfc
from auxiliares.banco_post import inserir_dados, Conectar_DB, atualizar_tempo_transporte
import pickle
from auxiliares.configuracoes import cartao_palete
from auxiliares.configuracoes import ultimo_posto_bios

#--------------------------------------------------------------------------------------------------------------------------
produto_atual = {}
palete_atual = {}
tempo = {"BS": {}, "BT1": {}, "BT2": {}, "BD": {}}
dados = {"arrival": {}, "preparo": {}, "montagem": {}, "espera": {}, "transferencia": {}}
data_frame_postos = {}
maquina_estado = {}
maquina_estado_anterior = {}
contagem_erros  = 0
hora_inicio = datetime.now()
inicia_producao = False
erro_bd_atrasado = {}

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
        """        Adiciona uma linha no DataFrame com os tempos do produto.
        :param produto: instância de Produto
        :param tempos: dicionário com os tempos
        """
        self.df_historico = pd.concat([self.df_historico, tempos], ignore_index=True)
        memoriza_produtos()

    def lista_postos_historico(self):
        if self.df_historico.empty:
            return []  # caso não tenha registros ainda
        df = self.df_historico.copy()  # copia o DataFrame original
        df["numero"] = df["codigo_posto"].str.split("_").str[1].astype(int)  # extrai o número
        df = df.sort_values("numero")
        lista_postos = df["codigo_posto"].tolist()
        return lista_postos
        
#DEFINIÇÃO DE FUNÇÕES
def chama_objeto(nome_objeto, objeto_default):
    pasta = "objetos_memory"
    os.makedirs(pasta, exist_ok=True)  # garante que a pasta exista

    caminho = os.path.join(pasta, f"{nome_objeto}.pkl")

    if os.path.isfile(caminho):
        try:
            with open(caminho, "rb") as f:
                return pickle.load(f)
        except (pickle.UnpicklingError, EOFError, Exception):
            print(f"[AVISO] Falha ao carregar '{caminho}', usando objeto padrão.")
    return objeto_default

# ELEMENTOS DE MEMÓRIA
listaProdutos = chama_objeto('listaProdutos', {})

#DEFINIÇÃO DE FUNÇÕES
def salva_objeto(nome_objeto, objeto):
    caminho = f"objetos_memory/{nome_objeto}.pkl"
    with open(caminho, "wb") as f:
        pickle.dump(objeto, f)

def memoriza_produtos():
    salva_objeto('listaProdutos', listaProdutos)

def adicionarProduto(novoProduto):
    listaProdutos[novoProduto] = Produto(novoProduto)
    memoriza_produtos()


#DEFINIÇÃO DE CLASSES
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

class Posto:
    def __init__ (self, posto):
        self.id_posto = posto
        self.nome = posto.upper()
        self.csvPath = f"{self.nome}.csv"
        self.XlsPath = f"{self.nome}.xlsx"
        self.df_historico = self.carregarDados()

    def carregarDados(self):
        if os.path.exists(self.csvPath):
            print(f"[{self.nome}] Carregando dados Locais.")
            return pd.read_csv(self.csvPath)
        else:
            print(f"[{self.nome}] Dados Locais n encontrados.")
            return pd.DataFrame(columns=[
            "produto",
            "inter_arrival_time",
            "tempo_preparo",
            "tempo_montagem",
            "tempo_espera",
            "tempo_transferencia",
            "tempo_ciclo",
            "hora"
        ])

    def registrar_passagem(self, tempos: pd.DataFrame):
        """        Adiciona uma linha no DataFrame com os tempos do produto.
        :param produto: instância de Produto
        :param tempos: dataframe de tempos
        """
        if self.df_historico.empty:
            self.df_historico = tempos.copy()
        else:
            self.df_historico = pd.concat([self.df_historico, tempos], ignore_index=True)
        self.salvarDadosLocais()

    def salvarDadosLocais(self):
        self.df_historico.to_csv(self.csvPath, index=False)
        self.df_historico.to_excel(self.XlsPath, index=False)
        print(f"[{self.nome}] Dados salvos com sucesso.")

postos = {}

def inicializar_postos():
    global postos  # apenas declarar o uso da variável global
    for i in range(ultimo_posto_bios+1):
        postos[f"posto_{i}"] = Posto(f"posto_{i}")
    print("[INFO] Postos inicializados:")
    for nome in postos.keys():
        print(f"    - {nome}")

def envia_dados_tempo(dispositivo, time, produto_idem = '', recupera=False, zera_transporte=False):
    global postos
    global data_frame_postos
    if produto_idem == '':
        data_frame_postos[dispositivo]['transferencia'] = time - data_frame_postos[dispositivo]['transferencia']
        data_frame_postos[dispositivo]['transferencia'] = data_frame_postos[dispositivo]['transferencia'].dt.seconds
        #Calculando o tempo de ciclo
        colunas_tempo = ["arrival", "preparo", "montagem", "espera", "transferencia"]
        data_frame_postos[dispositivo]["tempo_ciclo"] = data_frame_postos[dispositivo][colunas_tempo].sum(axis=1)
        data_frame_postos[dispositivo]["hora"] =  str(datetime.now().strftime("%d/%m/%Y, %H:%M:%S"))
        #Enviando dados
        print("Enviando dados tempo...")
        #Para o objeto Posto
        postos[dispositivo].registrar_passagem(data_frame_postos[dispositivo])

        #Para o banco de dados
        print(data_frame_postos[dispositivo])
        inserir_dados(data_frame_postos[dispositivo],'tempos_postos', dispositivo)

        #Para o objeto Produto
        produto = data_frame_postos[dispositivo]["produto"][0]
        data_frame_postos[dispositivo] = data_frame_postos[dispositivo].drop(columns=["produto"])
        data_frame_postos[dispositivo]["codigo_posto"] = dispositivo

        #PERMANENTE
        listaProdutos[produto].registrar_passagem(data_frame_postos[dispositivo])

        del data_frame_postos[dispositivo]
    elif verifica_cod_produto(produto_idem):
        
        if recupera:
            # Criando um novo DataFrame com a linha a remover
            tempos_produto_idem = data_frame_postos[dispositivo][data_frame_postos[dispositivo]['produto'] == 'XXXXXXXXXX']

            # Removendo a linha do DataFrame original
            data_frame_postos[dispositivo] = data_frame_postos[dispositivo][data_frame_postos[dispositivo]['produto'] != 'XXXXXXXXXX']

            #Tratando dados
            tempos_produto_idem['produto'] = produto_idem
            tempos_produto_idem['transferencia'] = time - tempos_produto_idem['transferencia']
            if int(tempos_produto_idem['transferencia'].dt.seconds.iloc[0]) > 7200 or zera_transporte:
                tempos_produto_idem['transferencia'] = 0
            else:
                tempos_produto_idem['transferencia'] = tempos_produto_idem['transferencia'].dt.seconds

            # Calculando o tempo de ciclo
            colunas_tempo = ["arrival", "preparo", "montagem", "espera", "transferencia"]
            tempos_produto_idem["tempo_ciclo"] = tempos_produto_idem[colunas_tempo].sum(axis=1)
            tempos_produto_idem["hora"] = str(datetime.now().strftime("%d/%m/%Y, %H:%M:%S"))

            # Para o objeto Posto
            postos[dispositivo].registrar_passagem(tempos_produto_idem)

            # Para o banco de dados
            print(tempos_produto_idem)
            inserir_dados(tempos_produto_idem, 'tempos_postos', dispositivo)

            # Para o objeto Produto
            produto = tempos_produto_idem["produto"][0]
            tempos_produto_idem = tempos_produto_idem.drop(columns=["produto"])
            tempos_produto_idem["codigo_posto"] = dispositivo

            # PERMANENTE
            listaProdutos[produto].registrar_passagem(tempos_produto_idem)
            print("Produto recuperado com sucesso")
        elif (data_frame_postos[dispositivo]['produto'] == produto_idem).any():
            # Criando um novo DataFrame com a linha a remover
            tempos_produto_idem = data_frame_postos[dispositivo][data_frame_postos[dispositivo]['produto'] == produto_idem]

            # Removendo a linha do DataFrame original
            data_frame_postos[dispositivo] = data_frame_postos[dispositivo][data_frame_postos[dispositivo]['produto'] != produto_idem]

            #Tratando dados
            tempos_produto_idem['transferencia'] = time - tempos_produto_idem['transferencia']
            if int(tempos_produto_idem['transferencia'].dt.seconds.iloc[0]) > 7200 or zera_transporte:
                tempos_produto_idem['transferencia'] = 0
            else:
                tempos_produto_idem['transferencia'] = tempos_produto_idem['transferencia'].dt.seconds


            # Calculando o tempo de ciclo
            colunas_tempo = ["arrival", "preparo", "montagem", "espera", "transferencia"]
            tempos_produto_idem["tempo_ciclo"] = tempos_produto_idem[colunas_tempo].sum(axis=1)
            tempos_produto_idem["hora"] = str(datetime.now().strftime("%d/%m/%Y, %H:%M:%S"))

            # Enviando dados
            print("Enviando dados tempo...")
            # Para o objeto Posto
            postos[dispositivo].registrar_passagem(tempos_produto_idem)

            # Para o banco de dados
            print(tempos_produto_idem)
            inserir_dados(tempos_produto_idem, 'tempos_postos', dispositivo)

            # Para o objeto Produto
            produto = tempos_produto_idem["produto"][0]
            tempos_produto_idem = tempos_produto_idem.drop(columns=["produto"])
            tempos_produto_idem["codigo_posto"] = dispositivo

            # PERMANENTE
            listaProdutos[produto].registrar_passagem(tempos_produto_idem)
            print('Envio realizado com suscesso')
        else:
            print(f'[RASTREADOR] - Erro: {produto_idem} não está na fila do {dispositivo}')

    else:
        print(f'[RASTREADOR] - Erro: Esse {produto_idem} não é um produto.')

def tratar_rastreador(mqttc, message):
    if message.topic.split("/")[0] == 'rastreio_nfc' and inicia_producao:
        global contagem_erros
        dispositivo = message.topic.split("/")[2]
        agente = message.topic.split("/")[3]
        n_posto = int(dispositivo.split("_")[1])
        dispositivo_posterior = 'posto_' + str(n_posto + 1)
        dispositivo_anterior = 'posto_' + str(n_posto - 1)
        payload = str(str(message.payload).split("'")[1])
        if agente == 'dispositivo':
            if payload in tempo.keys():
                #cria a máquina de estados verificando se ela ja existe
                if dispositivo not in maquina_estado.keys():
                    maquina_estado[dispositivo] = 0
                    tempo['BD'][dispositivo] = hora_inicio

                #insere o dado de tempo na tabela geral de tempos de cada rastreador
                try:
                    tempo[payload][dispositivo] = datetime.now()
                except:
                    print('Ocorreu um erro ao inserir dados nos dicionário.')

                #máquina de estados
                if payload == 'BS':
                    if maquina_estado[dispositivo] == 0 or maquina_estado[dispositivo] == 4:
                        print(f'[RASTREADOR {n_posto}] - ESTADO 1 - BS')
                        dados['arrival'][dispositivo] = (tempo['BS'][dispositivo] - tempo['BD'][dispositivo]).seconds
                        maquina_estado_anterior[dispositivo] = maquina_estado[dispositivo]
                        maquina_estado[dispositivo] = 1
                    return

                if payload == 'BT1':
                    if maquina_estado[dispositivo] == 1 or maquina_estado[dispositivo] == 3:
                        print(f'[RASTREADOR {n_posto}] - ESTADO 2 - BT1')
                        dados['preparo'][dispositivo] = (tempo['BT1'][dispositivo] - tempo['BS'][dispositivo]).seconds
                        maquina_estado_anterior[dispositivo] = maquina_estado[dispositivo]
                        maquina_estado[dispositivo] = 2
                    return

                if payload == 'BT2':
                    if maquina_estado[dispositivo] == 1:
                        dados['preparo'][dispositivo] = 0
                        dados['montagem'][dispositivo] = (tempo['BT2'][dispositivo] - tempo['BS'][dispositivo]).seconds
                        #maquina_estado_anterior[dispositivo] = maquina_estado[dispositivo]
                        maquina_estado[dispositivo] = 3
                        maquina_estado_anterior[dispositivo] = 2

                    if maquina_estado[dispositivo] == 2:
                        print(f'[RASTREADOR {n_posto}] - ESTADO 3 - BT2')
                        dados['montagem'][dispositivo] = (tempo['BT2'][dispositivo] - tempo['BT1'][dispositivo]).seconds
                        maquina_estado_anterior[dispositivo] = maquina_estado[dispositivo]
                        maquina_estado[dispositivo] = 3
                    return

                if payload == 'BD':
                    if contagem_erros == 2:
                        mqttc.publish(f"rastreio/esp32/{dispositivo}/sistema", "dd_parar_erro_1")
                        contagem_erros = 0

                    if maquina_estado[dispositivo] == 1:
                        if dispositivo not in produto_atual.keys():
                            maquina_estado[dispositivo] = 0
                            maquina_estado_anterior[dispositivo] = 1
                            print(f"[RASTREADOR {n_posto}] - ESTADO 0 - BD")
                        else:
                            dados['preparo'][dispositivo] = 0
                            dados['montagem'][dispositivo] = (tempo['BD'][dispositivo] - tempo['BS'][dispositivo]).seconds
                            dados['espera'][dispositivo] = 0
                            maquina_estado[dispositivo] = 3
                            maquina_estado_anterior[dispositivo] = 1

                    if maquina_estado[dispositivo] == 2:
                        if dispositivo not in produto_atual.keys():
                            maquina_estado[dispositivo] = 0
                            maquina_estado_anterior[dispositivo] = 2
                        else:
                            dados['montagem'][dispositivo] = (tempo['BD'][dispositivo] - tempo['BT1'][dispositivo]).seconds
                            dados['espera'][dispositivo] = 0
                            maquina_estado[dispositivo] = 3
                            maquina_estado_anterior[dispositivo] = 1

                    if maquina_estado[dispositivo] == 3:
                        print(f'[RASTREADOR {n_posto}] - ESTADO 4 - BD')
                        if dispositivo in produto_atual.keys():
                            if maquina_estado_anterior[dispositivo] != 1:
                                dados['espera'][dispositivo] = (tempo['BD'][dispositivo] - tempo['BT2'][dispositivo]).seconds

                            organiza = {
                                "produto": [produto_atual[dispositivo]],
                                "arrival": [dados['arrival'][dispositivo]],
                                "preparo": [dados['preparo'][dispositivo]],
                                "montagem": [dados['montagem'][dispositivo]],
                                "espera": [dados['espera'][dispositivo]],
                                "transferencia": [tempo['BD'][dispositivo]]
                            }

                            if dispositivo not in data_frame_postos.keys():
                                print(f'Novo Produto no Rastreador {n_posto}')
                                data_frame_postos[dispositivo] = pd.DataFrame(organiza)
                            else:
                                print(f'Produto adicionado a fila do Rastreador {n_posto}')
                                data_frame_postos[dispositivo] = pd.concat([data_frame_postos[dispositivo], pd.DataFrame(organiza)], ignore_index=True)

                            if dispositivo == f"posto_{ultimo_posto_bios}":
                                envia_dados_tempo(dispositivo, tempo['BD'][dispositivo], produto_idem=produto_atual[dispositivo], zera_transporte=True)
                                associacoes.desassocia(produto_atual[dispositivo])

                            if dispositivo in erro_bd_atrasado.keys():
                                if produto_atual[dispositivo] == erro_bd_atrasado[dispositivo][0]:
                                    envia_dados_tempo(dispositivo, erro_bd_atrasado[dispositivo][1], produto_idem=produto_atual[dispositivo])
                                    del erro_bd_atrasado[dispositivo]

                            del produto_atual[dispositivo]
                            #maquina_estado_anterior[dispositivo] = maquina_estado[dispositivo]
                            maquina_estado[dispositivo] = 4
                            maquina_estado_anterior[dispositivo] = 3
                        else:
                            if maquina_estado_anterior[dispositivo] != 1:
                                dados['espera'][dispositivo] = (tempo['BD'][dispositivo] - tempo['BT2'][dispositivo]).seconds

                            organiza = {
                                "produto": ['XXXXXXXXXX'],
                                "arrival": [dados['arrival'][dispositivo]],
                                "preparo": [dados['preparo'][dispositivo]],
                                "montagem": [dados['montagem'][dispositivo]],
                                "espera": [dados['espera'][dispositivo]],
                                "transferencia": [tempo['BD'][dispositivo]]
                            }
                            if dispositivo not in data_frame_postos.keys():
                                print(f'Novo Produto no Rastreador {n_posto}')
                                data_frame_postos[dispositivo] = pd.DataFrame(organiza)
                            else:
                                print(f'Produto adicionado a fila do Rastrador {n_posto}')
                                data_frame_postos[dispositivo] = pd.concat([data_frame_postos[dispositivo], pd.DataFrame(organiza)], ignore_index=True)

                            if dispositivo == f"posto_{ultimo_posto_bios}":
                                envia_dados_tempo(dispositivo, tempo['BD'][dispositivo], produto_idem=produto_atual[dispositivo], zera_transporte=True)
                                associacoes.desassocia(produto_atual[dispositivo])

                            maquina_estado[dispositivo] = 4
                            maquina_estado_anterior[dispositivo] = 3

                            print("LEITURA NÃO FOI REALIZADA A TEMPO")
                    return

            elif verifica_palete_nfc(payload):
                if dispositivo == "posto_0":
                    palete_atual[dispositivo] = cartao_palete[payload]
                else:
                    tratamento_palete(cartao_palete[payload], dispositivo, mqttc)

            else:
                print("Código lido inválido!")
                if contagem_erros <= 1:
                    mqttc.publish(f"rastreio_nfc/esp32/{dispositivo}/sistema", "dd_erro_0")
                    contagem_erros += 1
                    return
                mqttc.publish(f"rastreio_nfc/esp32/{dispositivo}/sistema", "dd_iniciar_erro_1")

def palete_atual_posto(posto):
    if posto in palete_atual.keys():
        return palete_atual[posto]
    else:
        print("Posto não encontrado no dic palete_atual")
        return None

def inicia_sistema_rastreador(message):
    global hora_inicio
    global inicia_producao
    payload = str(str(message.payload).split("'")[1])
    if message.topic == "ControleProducao_DD" and payload == "Start":
        print('Recebi o Start')
        hora_inicio = datetime.now()
        inicia_producao = True
    elif message.topic == "Produtos":
        try:
            print(listaProdutos[payload].df_historico)
        except:
            print('ERRO PRODUTOS')

def verifica_estado_producao():
    return inicia_producao

def produto_em_fila_rastreador(produto, dispositivo):
    global data_frame_postos
    if dispositivo in data_frame_postos.keys():
        print(f'O {dispositivo} esta no dataframe postos.')
        if (data_frame_postos[dispositivo]['produto'] == produto).any():
            print(f'O {produto} esta no dataframe do {dispositivo}')
            return True
        else:
            return False
    else:
        print(f'O {dispositivo} não esta no dataframe postos.')
        return False

def tratamento_palete(payload, dispositivo, mqttc):
    global produto_atual
    global contagem_erros
    global erro_bd_atrasado
    global listaProdutos

    n_posto = int(dispositivo.split("_")[1])

    if n_posto > 0:
        dispositivo_anterior = 'posto_' + str(n_posto - 1)
    else:
        dispositivo_anterior = 'posto_0'
    
    produto_lido = associacoes.palete_produto(payload)
    print(f"Produto: {produto_lido}, Palete: {payload}, Rastreador: {dispositivo}")

    if verifica_palete(payload):
        if verifica_cod_produto(produto_lido):
            produto_atual[dispositivo] = produto_lido
            try:
                if n_posto > 0:
                    print(f'Rastreador {n_posto} enviando {produto_lido} do {dispositivo_anterior}')
                    if produto_em_fila_rastreador(produto_lido, dispositivo_anterior):
                        print(f'Realizando envio padrão: {produto_lido} no {dispositivo} enviando dados de {dispositivo_anterior}')
                        envia_dados_tempo(dispositivo_anterior, tempo['BS'][dispositivo], produto_idem=produto_lido)

                    else:
                        if produto_em_fila_rastreador('XXXXXXXXXX', dispositivo_anterior):
                            print(f'Rastreador {n_posto} não encontrou {produto_lido} na fila do {dispositivo_anterior}, Tentando recuperar dados "XXXXXXXXXX"')
                            envia_dados_tempo(dispositivo_anterior, tempo['BS'][dispositivo], produto_idem=produto_lido,
                                              recupera=True)
                            if produto_em_fila_rastreador(produto_lido, f'posto_{n_posto - 2}'):
                                print(f'Devido a recuperação. Rastreador {n_posto} enviando {produto_lido} do posto_{n_posto - 2}')
                                envia_dados_tempo(f'posto_{n_posto - 2}', tempo['BS'][dispositivo],
                                                  produto_idem=produto_lido, zera_transporte=True)
                        else:
                            lista_historico_postos = listaProdutos[produto_lido].lista_postos_historico()

                            if dispositivo_anterior in lista_historico_postos:
                                if lista_historico_postos[-1] == dispositivo_anterior:
                                    print(f'RASTREADOR {n_posto}: O produto {produto_lido} já foi registrado no {dispositivo_anterior}. Ignorando tentativa de envio...')
                                else:
                                    print(f'RASTREADOR {n_posto}: O produto {produto_lido} já foi registrado no {dispositivo_anterior}, e em outro seguinte. Ignorando tentativa de envio...')
                            else:
                                print(f'Não foi possível recuperar as informações do produto {produto_lido} no rastreador do {dispositivo_anterior}')
                                erro_bd_atrasado[dispositivo_anterior] = [produto_lido, tempo['BS'][dispositivo]]

                                for i in range(n_posto - 1, 0, -1):
                                    if produto_em_fila_rastreador(produto_lido, f'posto_{i}'):
                                        print(f'Enviando dados do {produto_lido} no Rastreador do posto_{i}')
                                        envia_dados_tempo(f'posto_{i}', tempo['BS'][dispositivo], produto_idem=produto_lido,
                                                          zera_transporte=True)
                                        break
            except Exception as e:
                print(f'Erro ao enviar dados do {produto_lido} no Rastreador do {dispositivo_anterior}: ERRO {e}')
        else:
            print("Não foi possível validar o palete!")
            contagem_erros = 2
            mqttc.publish(f"rastreio/esp32/{dispositivo}/sistema", "dd_iniciar_erro_1")
    else:
        print("Código lido inválido!")
        if contagem_erros <= 1:
            mqttc.publish(f"rastreio/esp32/{dispositivo}/sistema", "dd_erro_0")
            contagem_erros += 1
            return
        mqttc.publish(f"rastreio/esp32/{dispositivo}/sistema", "dd_iniciar_erro_1")
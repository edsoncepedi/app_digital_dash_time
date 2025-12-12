import re
import socket
import pandas as pd
from auxiliares.configuracoes import ultimo_posto_bios
from datetime import datetime, date
import os.path
import glob
import shutil
import sys
from pyzbar.pyzbar import decode
from auxiliares.configuracoes import cartao_palete



#Essa função é global, sem superpoderes, que serve para separar o nome e o numero de uma string. Utilizada para ler RUNIN2. Entrega runnin, 2.
def separar_topico(s):
    match = re.match(r"([A-Za-z]+)(\d+)", s)
    if match:
        letras, numeros = match.groups()
        return letras.lower(), int(numeros)
    return None, None

def verifica_palete(texto):
    if len(texto) == 5:
        cod = texto[0:3]
        try:
            num = int(texto[3:5])
        except:
            return False
        if cod == 'PLT' and 0 < num <= 26:
            return True
        else:
            return False
    else:
        return False

def verifica_palete_nfc(palete):
    if palete in cartao_palete.keys():
        return True
    else:
        return False

def verifica_cod_produto(code):
    """
    Essa função verifica se a string inserida é da forma de um código de produto que é da forma 101CP01079. Onde os três primeiros caracteres
    representam o dia corrido do ano (001 a 366). O quarto e o quinto caractere é uma fixa CP. O sexto e sétimo represetam a versão do protótipo (01 a 99).
    Os últimos 3 caracteres represetam o número do produto daquele dia (001 a 999).
    :param code: Uma string a ser verificada.
    :return: True ou False. True se a string possuir um formato compatível e False se não.
    """
    if len(code) == 10:
        try:
            dia = int(code[:3])
            cp = code[3:5]
            prot = int(code[5:7])
            sn = int(code[7:])
        except:
            return False
        if (dia > 0 and dia <= 366) and (cp == 'CP') and (prot != 0) and (sn != 0):
            return True
        else:
            return False
    else:
        return False

def imprime_qrcode(code):
    mysocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    host = "172.16.8.55" #ERRADO DE PROPOSITO
    port = 6101

    try:
        mysocket.connect((host, port)) #connecting to host
        #TAG MAIOR
        #LARG = 832
        #mysocket.send(f"^XA^FO50,50^GB700,3,3^FS^CF,60^FO185,130^FD{code}^FS^FX Gerando QRCODE^FO50,250^GB700,3,3^FS^FO285,320^BQ,,10^FDQA,{code}^FS^FO50,900^GB700,3,3^FS^FO50,50^GB3,850,3^FS^FO750,50^GB3,850,3^FS^FO50,620^GB700,3,3^FS^FO240,630^GFA,9120,9120,38,,:::::::::::::::::::::::::::::::::::::::::::::::::::::gW04,gU07IFC,gT03KFC,gS01MF8,gS07MFE,gR01JF1JF8,gR07IFE0JFC,gR0JFC07JF,gQ03JFC07JF8,gQ07JFC03JFE,gQ0KFC03KF,gP01KFC03KF8,gP03KFC03KFC,gP07KF801KFE,gP0LF801LF,gO01LF801LF,gO01LF801LF8,gO03LF003LFC,gO07LF003LFC,gO07KFE003LFE,gO0LFE003MF,gN01LFC007MF,gN01LFC007MF8,gN03LF800NF8,gN03LFI0NFC,:gN07KFE001NFC,gN07KFC001NFE,:gN0LF8I0NFE,gN0LF8J07MF,gN0LFL01LF,gN0LFN0KF,gM01KFEO0JF,gM01KFEO07IF,gM01KFCO03IF,:gM01KFCO03IF8,gM01KF8O03IF8,gM01KFP07IF8,:gM01JFEP07IF8,gM01JFEP07IF,gM01JFCP03IF,gM01JF8P01IF,gN0JFQ01IF,gN0IFCQ01IF,gN0FFER01IF,gN0F8S01FFE,hI03FFE,hI07FFE,hI0IFE,hI0IFC,hI07FFC,hI07FF8,:hI0IF,:hH03FFE,hH07FFE,hH07FFC,:hH07FF8,hH07FF,hH0FFE,hG01FFC,hG07FF8,h07IF,gY0JFE,gU01MFC,gT07NF8,gS03NFE,gS0OFC,gS0OF,gS03MFC,gT0LFE,gT01KF,gU01IF,,::::::::::::V01IF8K01JFgS01IF8,J0MFJ01KF8I01KFC07FFC3NF07FF83FFEI07FFC01KF8,J0MFEI07KFEI07KFC07FFC3NF07FF83FFEI0IF807KFE,J0NFI0MF001LFC07FFC3NF07FF81FFEI0IF80MF,J0NF801MF803LFC07FFC3NF07FF81IFI0IF81MF8,J0NFC03MFC07LFC07FFC3NF07FF81IFI0IF03MFC,J0NFC07MFC07LFC07FFC3NF07FF81IFI0IF07MFC,J0NFE07MFC0MFC07FFC3NF07FF80IF001IF07MFC,J0NFE07MFE0MFC07FFC3NF07FF80IF001IF07MFE,J0IF803FFE0IFC07FFE0IFCK07FFCI07FFCI07FF80IF801FFE0IFC07FFE,J0IF801FFE0IF803FFE0IFL07FFCI07FFCI07FF807FF801FFE0IF803FFE,J0IF801FFE0IF801FFE0IFL07FFCI07FFCI07FF807FF803FFE0IF801FFE,J0IF801IF0IF001IF0IFL07FFCI07FFCI07FF807FF803FFC0IF001IF,J0IF801IF0IF001IF0IFL07FFCI07FFCI07FF807FFC03FFC0IF001IF,J0IF801IF0IF001IF0IFCK07FFCI07FFCI07FF803FFC03FFC0IF001IF,J0IF801IF1IF001IF0JFEJ07FFCI07FFCI07FF803FFC03FFC1IF001IF,J0IF801IF1IF001IF0KFEI07FFCI07FFCI07FF803FFC07FF81IF001IF,J0IF801FFE1IF001IF0LFC007FFCI07FFCI07FF803FFC07FF81IF001IF,J0IF803FFE1IF001IF07LF007FFCI07FFCI07FF801FFE07FF81IF001IF,J0IF807FFE1IF001IF07LFC07FFCI07FFCI07FF801FFE07FF81IF001IF,J0NFE1IF001IF03LFE07FFCI07FFCI07FF801FFE0IF01IF001IF,J0NFE1IF001IF00LFE07FFCI07FFCI07FF800FFE0IF01IF001IF,J0NFC1IF001IF003LF07FFCI07FFCI07FF800FFE0IF01IF001IF,J0NFC1IF001IFI0LF07FFCI07FFCI07FF800IF0FFE01IF001IF,J0NF81IF001IFJ0KF07FFCI07FFCI07FF800IF0FFE01IF001IF,J0MFE01IF001IFK0JF07FFCI07FFCI07FF8007FF1FFE00IF001IF,J0MF800IF001IFL0IF07FFCI07FFCI07FF8007FF1FFE00IF001IF,J0KFEJ0IF001IFL0IF07FFCI07FFCI07FF8007FF9FFC00IF001IF,J0IF8L0IF001IFL07FF07FFCI07FFCI07FF8007FF9FFC00IF001IF,J0IF8L0IF801FFEL0IF07FFCI07FFCI07FF8003FF9FFC00IF801FFE,J0IF8L0IF803FFEK01IF07FFCI07FFCI07FF8003FFBFFC00IF803FFE,J0IF8L0NFE07MF07FFCI07FFCI07FF8003FFBFF800NFE,J0IF8L07MFE07MF07FFCI07FFCI07FF8001KF8007MFE,J0IF8L07MFC07MF07FFCI07FFCI07FF8001KF8007MFC,J0IF8L03MFC07LFE07FFCI07FFCI07FF8001KFI03MFC,J0IF8L03MF807LFC07FFCI07FFCI07FF8001KFI03MF8,J0IF8L01MF007LFC07FFCI07FFCI07FF8I0KFI01MF,J0IF8M0LFE007LF007FFCI07FFCI07FF8I0KFJ0LFE,J0IF8M03KFC00LFE007FFCI07FFCI07FF8I0JFEJ03KF8,J0IF8N07IFEI07KFI07FFCI07FFCI07FF8I07IFEK07IFE,,::::::::::::::::::::::::::::::::::::::::::::::::::::::^FS^XZ".encode())  # using bytes
        mysocket.send(f"^XA^FO60,10^GB370,3,3^FS^FO60,220^GB373,3,3^FS^CF,15^A0R,35,35^FO330,35^FD{code}^FS^FX Gerando QRCODE^FO110,23^BQ,,8^FDQA,{code}^FS^FO60,10^GB3,210,3^FS^FO430,10^GB3,210,3^FS^XZ".encode())
        mysocket.close () #closing connection
    except:
        print('Erro na conexão da Impressora Zebra')

def reiniciar_produtos():
    if os.path.exists("produtos.txt"):
        print("Resetando contagem de produtos...")
        os.remove("produtos.txt")

    if os.path.exists("memoria.txt"):
        print("Resetando contagem de produtos...")
        os.remove("memoria.txt")

def reiniciar_sistema(debug=False, dados=True, backup=False):
    if not debug:
        horario = str(datetime.now().strftime("%d_%m_%Y_%H_%M_%S"))
        # Cria pasta de backup, se necessário
        if backup:
            pasta_backup = f"backup_{horario}"
            os.makedirs(pasta_backup, exist_ok=True)
        if dados:
            pasta_dados = f"dados_{horario}"
            os.makedirs(pasta_dados, exist_ok=True)

            dados = glob.glob("*.xlsx")
            dados.extend(glob.glob("historico_associacoes.csv"))

            for dado in dados:
                destino_dados = os.path.join(pasta_dados, os.path.basename(dado))
                shutil.copy2(dado, destino_dados)

    arquivos = glob.glob("*.csv")
    arquivos.extend(glob.glob("*.xlsx"))
    arquivos.extend(glob.glob("objetos_memory/*.xlsx"))
    arquivos.extend(glob.glob("auxiliares/*.xlsx"))
    arquivos.extend(glob.glob("auxiliares/*.csv"))
    arquivos.extend(glob.glob("objetos_memory/*.pkl"))

    for arquivo in arquivos:
        try:
            if not debug and backup:
                # Define destino no backup (mantendo só o nome do arquivo)
                destino_backup = os.path.join(pasta_backup, os.path.basename(arquivo))

                # Faz backup
                shutil.copy2(arquivo, destino_backup)
                print(f"Backup feito: {arquivo} → {destino_backup}")

            os.remove(arquivo)
            print(f"Removido: {arquivo}")
        except Exception as e:
            print(f"Erro ao remover {arquivo}: {e}")

    reiniciar_produtos()

    # Parando o Script
    sys.exit(1)


def ler_ultimo_codigo(nome_arquivo):
    """
    Abre o arquivo direcionado e retorna o conteúdo da última linha.
    :param nome_arquivo: String com o nome do arquivo que deve ser aberto.
    :return: Uma string com o conteúdo da última linha.
    """
    if os.path.exists(nome_arquivo):
        arquivo = open(nome_arquivo, "r")
        linhas = list()
        for linha in arquivo.readlines():
            linhas.append(linha.strip())
        arquivo.close()
        if len(linhas) == 0:
            return None
        else:
            return linhas[-1]
    else:
        arquivo = open(nome_arquivo, "x")
        arquivo.close()
        return None

def memoriza_produto(code):
    """
    Verifica se o código recebido é um código de produto e se for ele armazena em um arquivo de texto chamado memória.txt.
    :param code: String que deve ser memorizada.
    :return: Não retorna nada.
    """
    if verifica_cod_produto(code):
        arquivo_mem = "memoria.txt"
        arquivo = open(arquivo_mem, "a")
        arquivo.write(code + "\n")
        arquivo.close()

def gera_codigo_produto():
    """
    Essa função é responsável por gerar um código de produto válido e original para cada novo produto. Cada vez que a função é chamada
    ela verifica no arquivo produto.txt o último código gerado para, a partir dele, gerar um novo código. Essa função analisa o dia do ano
    e compara com o dia do último produto, caso sejam diferentes, ele inicia uma nova contagem de produtos com o dia atual. Se for o mesmo dia
    ela incrementará o número do dispositivo e retornará a nova string.
    :return: String com o novo código de produto.
    """
    ano = int((datetime.now().year))
    primeirodia = date(ano, 1, 1)
    hoje = date.today()
    dias_corridos = (hoje - primeirodia).days + 1
    versao_prototipo = 1
    nome_arquivo_produto = "produtos.txt"

    ultimo_poduto = ler_ultimo_codigo(nome_arquivo_produto)
    produto = 0

    if ultimo_poduto == None:
        produto = 1
    else:
        if verifica_cod_produto(ultimo_poduto):
            if int(ultimo_poduto[:3]) != dias_corridos:
                produto = 1
            else:
                produto = int(ultimo_poduto[7:]) + 1

    code = f"{dias_corridos:03}CP{versao_prototipo:02}{produto:03}"

    if verifica_cod_produto(code):
        arquivo = open(nome_arquivo_produto, "w")
        arquivo.write(code + "\n")
        arquivo.close()
        return code
    else:
        return None

def apaga_ultimo_produto_txt():
    """
    Essa função foi criada para apagar o último produto da lista de produtos, caso o último produto gerado não tenha sido vinculado.
    :return: Não retorna nada.
    """
    nome_arquivo_produto = "produtos.txt"

    arquivo = open(nome_arquivo_produto, "r")
    linhas = list()
    for linha in arquivo.readlines():
        linhas.append(linha.strip())
    arquivo.close()

    arquivo = open(nome_arquivo_produto, "w")
    for i in range(len(linhas)-1):
        arquivo.write(linhas[i] + "\n")
    arquivo.close()

def separar_posto(s):
    letras, numero = s.split('_')
    return f"{letras}_", int(numero)

def posto_anterior(posto_id):
    """
    Dado o ID de um posto, retorna o ID do posto anterior.
    :param posto_id: String com o ID do posto atual.
    :return: String com o ID do posto anterior ou None se não existir.
    """
    letras, numero = separar_posto(posto_id)
    if letras is None or numero is None:
        return None
    if numero == 0:
        return None
    numero_anterior = numero - 1
    return f"{letras}{numero_anterior}"

def posto_proximo(posto_id):
    """
    Dado o ID de um posto, retorna o ID do próximo posto.
    :param posto_id: String com o ID do posto atual.
    :return: String com o ID do próximo posto ou None se não existir.
    """
    letras, numero = separar_posto(posto_id)
    if letras is None or numero is None:
        return None
    numero_proximo = numero + 1
    proximo_id = f"{letras}{numero_proximo}"
    if numero_proximo > ultimo_posto_bios:
        return None
    return proximo_id
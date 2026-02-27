# auxiliares/utils.py
# -*- coding: utf-8 -*-

import glob
import logging
import os
import re
import shutil
import socket
import sys
from datetime import date, datetime
from typing import Optional, Tuple

from dotenv import load_dotenv

from auxiliares.configuracoes import cartao_palete, ultimo_posto_bios

# -----------------------------------------------------------------------------
# ENV / PATHS
# -----------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(BASE_DIR, ".."))

dotenv_path = os.path.join(PROJECT_DIR, ".env")
load_dotenv(dotenv_path=dotenv_path)

ARQUIVO_PRODUTOS = os.path.join(PROJECT_DIR, "produtos.txt")
ARQUIVO_MEMORIA = os.path.join(PROJECT_DIR, "memoria.txt")

# -----------------------------------------------------------------------------
# LOGGING
# -----------------------------------------------------------------------------
logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# REGEX (pré-compiladas)
# -----------------------------------------------------------------------------
_RE_TOPICO = re.compile(r"([A-Za-z]+)(\d+)")
_RE_CODE_PRODUTO = re.compile(r"^\d{3}CP\d{2}\d{3}$")
_RE_PALETE = re.compile(r"^PLT(0[1-9]|1[0-9]|2[0-6])$")


# -----------------------------------------------------------------------------
# HELPERS
# -----------------------------------------------------------------------------
def separar_topico(s: str) -> Tuple[Optional[str], Optional[int]]:
    """
    Separa o nome e o número de uma string, por exemplo:
    "RUNIN2" -> ("runin", 2)
    """
    if s is None:
        return None, None
    match = _RE_TOPICO.match(str(s).strip())
    if match:
        letras, numeros = match.groups()
        return letras.lower(), int(numeros)
    return None, None


def verifica_palete(texto: str) -> bool:
    """
    Verifica pallet no formato 'PLT01' ... 'PLT26' (5 caracteres).
    """
    if not isinstance(texto, str):
        return False
    return bool(_RE_PALETE.match(texto.strip()))


def verifica_palete_nfc(palete: str) -> bool:
    """
    Verifica se o pallet NFC existe no dicionário cartao_palete.
    """
    return palete in cartao_palete


def verifica_cod_produto(code: str) -> bool:
    """
    Verifica se a string inserida é um código de produto no formato 101CP01079:
      - 3 primeiros: dia corrido do ano (001 a 366)
      - 4º e 5º: "CP"
      - 6º e 7º: versão do protótipo (01 a 99) (não pode ser 00)
      - últimos 3: número do produto do dia (001 a 999) (não pode ser 000)
    """
    if not isinstance(code, str):
        return False

    code = code.strip()
    if not _RE_CODE_PRODUTO.match(code):
        return False

    try:
        dia = int(code[:3])
        prot = int(code[5:7])
        sn = int(code[7:])
    except ValueError:
        return False

    return (1 <= dia <= 366) and (prot != 0) and (sn != 0)


def imprime_qrcode(code: str) -> None:
    """
    Envia ZPL via TCP para a impressora Zebra.

    Melhorias:
    - timeout para não travar o sistema
    - fechamento garantido do socket (finally)
    - logs com exceção real
    """
    host = os.getenv("IP_IMPRESSORA")  # ajuste no seu .env
    port = 6101

    if not host:
        logger.error("IP_IMPRESSORA não está definido no .env")
        return

    zpl = (
        f"^XA^FO60,10^GB370,3,3^FS^FO60,220^GB373,3,3^FS^CF,15^A0R,35,35"
        f"^FO330,35^FD{code}^FS^FX Gerando QRCODE^FO110,23^BQ,,8^FDQA,{code}^FS"
        f"^FO60,10^GB3,210,3^FS^FO430,10^GB3,210,3^FS^XZ"
    ).encode()

    mysocket: Optional[socket.socket] = None
    try:
        mysocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        mysocket.settimeout(3)  # evita travar
        mysocket.connect((host, port))
        mysocket.send(zpl)
    except (OSError, socket.timeout) as e:
        logger.exception("Erro na conexão/envio para a Impressora Zebra (%s:%s): %s", host, port, e)
        print("Erro na conexão da Impressora Zebra")  # mantém compatibilidade com seu fluxo atual
    finally:
        if mysocket is not None:
            try:
                mysocket.close()
            except OSError:
                pass


def reiniciar_produtos() -> None:
    """
    Remove arquivos de contagem/memória.
    """
    for path in (ARQUIVO_PRODUTOS, ARQUIVO_MEMORIA):
        if os.path.exists(path):
            try:
                print("Resetando contagem de produtos...")
                os.remove(path)
            except OSError as e:
                logger.exception("Erro ao remover %s: %s", path, e)


def reiniciar_sistema(debug: bool = False, salvar_dados: bool = True, backup: bool = False) -> None:
    """
    Remove arquivos de trabalho (csv/xlsx/pkl) e opcionalmente cria pasta de backup e/ou
    pasta de dados com cópias antes de apagar.

    Melhorias:
    - não sobrescreve parâmetro com variável local
    - paths consistentes (rodando de onde for)
    - logs e tratamento de erro melhores
    """
    pasta_backup = None
    pasta_dados = None

    if not debug:
        horario = datetime.now().strftime("%d_%m_%Y_%H_%M_%S")

        if backup:
            pasta_backup = os.path.join(PROJECT_DIR, f"backup_{horario}")
            os.makedirs(pasta_backup, exist_ok=True)

        if salvar_dados:
            pasta_dados = os.path.join(PROJECT_DIR, f"dados_{horario}")
            os.makedirs(pasta_dados, exist_ok=True)

            lista_dados = glob.glob(os.path.join(PROJECT_DIR, "*.xlsx"))
            lista_dados.extend([os.path.join(PROJECT_DIR, "historico_associacoes.csv")])

            for dado in lista_dados:
                if os.path.exists(dado):
                    try:
                        destino = os.path.join(pasta_dados, os.path.basename(dado))
                        shutil.copy2(dado, destino)
                    except OSError as e:
                        logger.exception("Falha ao copiar dado %s -> %s: %s", dado, pasta_dados, e)

    # Arquivos a remover
    padroes = [
        os.path.join(PROJECT_DIR, "*.csv"),
        os.path.join(PROJECT_DIR, "*.xlsx"),
        os.path.join(PROJECT_DIR, "objetos_memory", "*.xlsx"),
        os.path.join(PROJECT_DIR, "auxiliares", "*.xlsx"),
        os.path.join(PROJECT_DIR, "auxiliares", "*.csv"),
        os.path.join(PROJECT_DIR, "objetos_memory", "*.pkl"),
    ]

    arquivos = []
    for p in padroes:
        arquivos.extend(glob.glob(p))

    for arquivo in arquivos:
        try:
            if (not debug) and backup and pasta_backup:
                destino_backup = os.path.join(pasta_backup, os.path.basename(arquivo))
                shutil.copy2(arquivo, destino_backup)
                print(f"Backup feito: {arquivo} → {destino_backup}")

            os.remove(arquivo)
            print(f"Removido: {arquivo}")
        except OSError as e:
            logger.exception("Erro ao remover %s: %s", arquivo, e)
            print(f"Erro ao remover {arquivo}: {e}")

    reiniciar_produtos()

    # Parando o Script
    sys.exit(1)


def ler_ultimo_codigo(nome_arquivo: str) -> Optional[str]:
    """
    Abre o arquivo direcionado e retorna o conteúdo da última linha.
    Cria o arquivo se ele não existir.

    Melhorias:
    - usa with open
    - lê sem carregar tudo em memória (pega última linha iterando)
    """
    if not nome_arquivo:
        return None

    os.makedirs(os.path.dirname(nome_arquivo), exist_ok=True)

    if not os.path.exists(nome_arquivo):
        # cria vazio
        with open(nome_arquivo, "x", encoding="utf-8"):
            pass
        return None

    ultima_linha = None
    try:
        with open(nome_arquivo, "r", encoding="utf-8") as f:
            for linha in f:
                ultima_linha = linha.strip()
    except OSError as e:
        logger.exception("Erro ao ler %s: %s", nome_arquivo, e)
        return None

    return ultima_linha or None


def memoriza_produto(code: str) -> None:
    """
    Se for um código de produto válido, armazena em memoria.txt.
    """
    if not verifica_cod_produto(code):
        return

    os.makedirs(os.path.dirname(ARQUIVO_MEMORIA), exist_ok=True)
    try:
        with open(ARQUIVO_MEMORIA, "a", encoding="utf-8") as arquivo:
            arquivo.write(code.strip() + "\n")
    except OSError as e:
        logger.exception("Erro ao escrever memória (%s): %s", ARQUIVO_MEMORIA, e)


def gera_codigo_produto() -> Optional[str]:
    """
    Gera um novo código de produto válido e original baseado no último salvo em produtos.txt.

    Observação importante:
    - Se dois processos chamarem isso ao mesmo tempo, pode haver duplicidade.
      O ideal para 100% robustez é gerar via banco (transação/lock).
    """
    ano = datetime.now().year
    primeirodia = date(ano, 1, 1)
    hoje = date.today()
    dias_corridos = (hoje - primeirodia).days + 1

    versao_prototipo = 1  # ajuste se necessário
    ultimo_produto = ler_ultimo_codigo(ARQUIVO_PRODUTOS)

    produto = 0
    if ultimo_produto is None:
        produto = 1
    else:
        if verifica_cod_produto(ultimo_produto):
            if int(ultimo_produto[:3]) != dias_corridos:
                produto = 1
            else:
                try:
                    produto = int(ultimo_produto[7:]) + 1
                except ValueError:
                    produto = 1
        else:
            produto = 1

    code = f"{dias_corridos:03}CP{versao_prototipo:02}{produto:03}"

    if not verifica_cod_produto(code):
        return None

    os.makedirs(os.path.dirname(ARQUIVO_PRODUTOS), exist_ok=True)
    try:
        with open(ARQUIVO_PRODUTOS, "w", encoding="utf-8") as arquivo:
            arquivo.write(code + "\n")
    except OSError as e:
        logger.exception("Erro ao escrever produtos (%s): %s", ARQUIVO_PRODUTOS, e)
        return None

    return code


def apaga_ultimo_produto_txt() -> None:
    """
    Apaga o último produto em produtos.txt (caso o último produto gerado não tenha sido vinculado).
    """
    if not os.path.exists(ARQUIVO_PRODUTOS):
        return

    try:
        with open(ARQUIVO_PRODUTOS, "r", encoding="utf-8") as arquivo:
            linhas = [linha.strip() for linha in arquivo if linha.strip()]

        if not linhas:
            return

        linhas = linhas[:-1]  # remove último

        with open(ARQUIVO_PRODUTOS, "w", encoding="utf-8") as arquivo:
            for linha in linhas:
                arquivo.write(linha + "\n")
    except OSError as e:
        logger.exception("Erro ao apagar último produto em %s: %s", ARQUIVO_PRODUTOS, e)


def separar_posto(s: str) -> Tuple[str, int]:
    letras, numero = s.split("_")
    return f"{letras}_", int(numero)


def posto_anterior(posto_id: str) -> Optional[str]:
    """
    Dado o ID de um posto, retorna o ID do posto anterior.
    Ex: "posto_3" -> "posto_2"
    """
    try:
        letras, numero = separar_posto(posto_id)
    except Exception:
        return None

    if numero == 0:
        return None

    return f"{letras}{numero - 1}"


def posto_proximo(posto_id: str) -> Optional[str]:
    """
    Dado o ID de um posto, retorna o ID do próximo posto.
    Ex: "posto_3" -> "posto_4" (se existir)
    """
    try:
        letras, numero = separar_posto(posto_id)
    except Exception:
        return None

    numero_proximo = numero + 1
    if numero_proximo > ultimo_posto_bios:
        return None

    return f"{letras}{numero_proximo}"


def posto_nome_para_id(posto_nome: str) -> int:
    """
    Aceita:
    - 'posto_0'
    - 'Posto 0'
    - 'POSTO 0'
    - '0'
    """
    if posto_nome is None:
        raise ValueError("posto_nome é None")

    s = str(posto_nome).strip().lower()

    # caso seja "0"
    if s.isdigit():
        return int(s)

    # caso seja "posto_0" ou "posto 0" (pega número no final)
    m = re.search(r"(\d+)$", s)
    if not m:
        raise ValueError(f"Formato inválido de posto: {posto_nome}")

    return int(m.group(1))
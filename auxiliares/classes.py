from __future__ import annotations

import os
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, List

import pandas as pd

from auxiliares.configuracoes import ultimo_posto_bios, cartao_palete
from auxiliares.utils import verifica_palete_nfc, verifica_cod_produto
from auxiliares.banco_post import inserir_dados, consulta_funcionario_posto  # noqa: F401  # mantido para uso futuro
from auxiliares.utils import imprime_qrcode, gera_codigo_produto
from auxiliares.posto_repo import criar_linha_aberta, atualizar_tempo_db, atualizar_produto_db, fechar_linha

from enum import Enum
from dataclasses import dataclass
from typing import Optional
from flask import current_app



class PostoState(Enum):
    IDLE = 0
    BS = 1
    BT1 = 2
    BT2 = 3
    BD = 4


@dataclass
class PostoSnapshot:
    id: str
    state: PostoState
    modelo: Optional[str]
    produto: Optional[str]
    palete: Optional[str]
    arrival: float | None
    t_preparo: float | None
    t_montagem: float | None
    t_espera: float | None
    t_transf: float | None
    t_ciclo: float | None
    n_produtos: int
    last_update_ts: float
    funcionario_nome: Optional[str]
    funcionario_imagem: Optional[str]

# -----------------------------------------------------------------------------
# LOGGING
# -----------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(asctime)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# ESTADO GLOBAL
# -----------------------------------------------------------------------------

#hora_inicio = time.perf_counter()
#producao: bool = False

# Pasta padrão para CSV/XLSX
DATA_DIR = Path(".")
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Colunas padrão dos DataFrames
COLS_ASSOC = ["produto", "palete", "horario"]
COLS_POSTO = [
    "produto",
    "arrival_time",
    "tempo_preparo",
    "tempo_montagem",
    "tempo_espera",
    "tempo_transferencia",
    "tempo_ciclo",
    "hora",
]

# -----------------------------------------------------------------------------
# FUNÇÕES DE CONTROLE DE PRODUÇÃO
# -----------------------------------------------------------------------------
def verifica_estado_producao() -> bool:
    return current_app.state.producao_ligada()


# -----------------------------------------------------------------------------
# INICIALIZAÇÃO DOS POSTOS
# -----------------------------------------------------------------------------

def inicializar_postos(mqttc) -> None:
    postos: Dict[str, "Posto"] = {}
    for i in range(int(os.getenv('NUMERO_POSTOS', 2)) + 1):
        nome = f"posto_{i}"
        postos[nome] = Posto(nome, mqttc)
    logger.info("Postos inicializados: %s", ", ".join(postos.keys()))
    return postos
# -----------------------------------------------------------------------------
# TABELA DE ASSOCIAÇÃO PRODUTO↔PALETE
# -----------------------------------------------------------------------------
class Tabela_Assoc:
    def __init__(self, entrada: str):
        self.nome = entrada.lower()
        self.csvPath = DATA_DIR / f"{self.nome}.csv"
        self.histPath = DATA_DIR / f"historico_{self.nome}.csv"
        self.df_assoc = self.carregarDados()

    def carregarDados(self) -> pd.DataFrame:
        if self.csvPath.exists():
            logger.info("[%s] Carregando dados locais de associações.", self.nome)
            try:
                df = pd.read_csv(self.csvPath)
            except Exception as e:
                logger.error("[%s] Erro ao ler %s: %s", self.nome, self.csvPath, e)
                df = pd.DataFrame(columns=COLS_ASSOC)
        else:
            logger.warning("[%s] Dados locais não encontrados (iniciando vazio).", self.nome)
            df = pd.DataFrame(columns=COLS_ASSOC)
        # garante colunas e tipos básicos
        for col in COLS_ASSOC:
            if col not in df.columns:
                df[col] = pd.Series(dtype="object")
        return df

    def salvarDadosLocais(self) -> None:
        try:
            self.df_assoc.to_csv(self.csvPath, index=False)
            logger.info("[%s] Dados de associações salvos.", self.nome)
        except Exception as e:
            logger.error("[%s] Falha ao salvar %s: %s", self.nome, self.csvPath, e)

    def paletes_assoc(self) -> List[str]:
        if "palete" not in self.df_assoc:
            return []
        return [p for p in self.df_assoc["palete"].dropna().astype(str).tolist()]

    def associa(self, palete: str, produto: str) -> None:
        horario = datetime.now().strftime("%d/%m/%Y, %H:%M:%S")
        dado = pd.DataFrame([
            {"palete": palete, "produto": produto, "horario": horario}
        ])

        # apêndice no histórico (com cabeçalho somente se o arquivo ainda não existir)
        try:
            header = not self.histPath.exists()
            dado.to_csv(self.histPath, index=False, mode="a", header=header)
        except Exception as e:
            logger.error("[%s] Erro ao escrever histórico %s: %s", self.nome, self.histPath, e)

        self.df_assoc = pd.concat([self.df_assoc, dado], ignore_index=True)
        self.salvarDadosLocais()

    def desassocia(self, produto: str) -> None:
        if "produto" not in self.df_assoc:
            return
        self.df_assoc = self.df_assoc[self.df_assoc["produto"] != produto].reset_index(drop=True)
        self.salvarDadosLocais()

    def palete_produto(self, palete: str) -> Optional[str]:
        if self.df_assoc.empty:
            return None
        resultado = self.df_assoc[self.df_assoc["palete"] == palete]
        if resultado.empty:
            return None
        # retorna o ÚLTIMO produto associado ao palete
        try:
            return resultado.tail(1)["produto"].astype(str).iloc[0]
        except Exception:
            return None


associacoes = Tabela_Assoc("associacoes")


# -----------------------------------------------------------------------------
# CLASSE POSTO
# -----------------------------------------------------------------------------
class Posto:
    def __init__(self, posto: str, mqttc) -> None:
        self.id_posto = posto
        self.n_posto = int(posto.split("_")[1])
        self.posto_anterior: Optional[str] = f"posto_{self.n_posto - 1}" if self.n_posto > 0 else None
        self.posto_posterior: Optional[str] = (
            f"posto_{self.n_posto + 1}" if self.n_posto < ultimo_posto_bios else None
        )

        self.nome = posto.upper()
        self.csvPath = DATA_DIR / f"{self.nome}.csv"
        self.XlsPath = DATA_DIR / f"{self.nome}.xlsx"

        self.df_historico = self.carregarDados()
        self.produto_atual: Optional[str] = None
        self.palete_atual: Optional[str] = None

        self.maquina_estado = 0
        self.maquina_estado_anterior = 0
        self.timestamp = {"BS": None, "BT1": None, "BT2": None, "BD": None}
        self.BS_posterior: Optional[float] = None
        self.BD_backup: Optional[float] = None

        self.contador_produtos = 0

        self.mqttc = mqttc
        self.on_change = None # callback opcional
        self.mudanca_estado = None # callback opcional
        self.transporte = None # callback opcional
        self._last_update = time.time()

        self.funcionario_nome = None
        self.funcionario_imagem = None

        self.db_row_id_atual = None
    
    def insert_produto(self, produto):
        if verifica_cod_produto(produto):
            self.produto_atual = produto
            self._notify()
        else:
            print(f"[ERRO] - Erro ao tentar associar produto ao posto {self.id_posto}")


    def add_funcionario(self, nome, imagem):
        self.funcionario_nome = nome
        self.funcionario_imagem = imagem  
    # ------------------------------------------------------------------
    # Registro de linha (início de montagem)
    # ------------------------------------------------------------------
    def inicia_prod_tempo(self):
        self.timestamp['BD'] = time.perf_counter()

    def inicia_montagem(self, arrival: float) -> None:
        nova_linha = {
            "produto": None,
            "arrival_time": float(arrival),
            "tempo_preparo": None,
            "tempo_montagem": None,
            "tempo_espera": None,
            "tempo_transferencia": None,
            "tempo_ciclo": None,
            "hora": datetime.now().strftime("%d/%m/%Y, %H:%M:%S"),
        }
        self.df_historico = pd.concat([self.df_historico, pd.DataFrame([nova_linha])], ignore_index=True)
        self.salvarDadosLocais()
        if self.db_row_id_atual is None:
            self.db_row_id_atual = criar_linha_aberta(self.id_posto, palete=self.palete_atual)

    def atualizar_tempo(self, produto: Optional[str], tipo_tempo: str, valor: float) -> None:
        valor = float(valor)
        if produto is not None:
            if produto not in self.df_historico["produto"].astype(str).values:
                logger.info("[%s] Produto %s não encontrado, associando à última linha.", self.nome, produto)
                self.atualiza_produto(produto)
            self.df_historico.loc[self.df_historico["produto"].astype(str) == str(produto), tipo_tempo] = round(valor, 2)
            self.salvarDadosLocais()
            logger.info("[%s] %s do produto %s atualizado (%.2fs)", self.nome, tipo_tempo, produto, valor)
        else:
            if len(self.df_historico) == 0:
                logger.warning("[%s] Nenhum registro ativo para atualizar.", self.nome)
                return
            idx = self.df_historico.index[-1]
            self.df_historico.at[idx, tipo_tempo] = round(valor, 2)
            self.salvarDadosLocais()
            logger.info("[%s] %s atualizado (%.2fs).", self.nome, tipo_tempo, valor)

        if self.db_row_id_atual is not None:
            atualizar_tempo_db(self.id_posto, self.db_row_id_atual, tipo_tempo, valor)

    def atualiza_produto(self, produto: str) -> None:
        if len(self.df_historico) == 0:
            logger.warning("[%s] Nenhuma linha para associar produto.", self.nome)
            return
        idx = self.df_historico.index[-1]
        self.df_historico.at[idx, "produto"] = str(produto)
        self.salvarDadosLocais()
        logger.info("[%s] Produto %s associado à linha %d.", self.nome, produto, idx)
        if self.db_row_id_atual is not None:
            atualizar_produto_db(self.id_posto, self.db_row_id_atual, produto)


    # ------------------------------------------------------------------
    # Cálculos de tempos
    # ------------------------------------------------------------------
    def calcula_transporte(self) -> None:
        if self.n_posto < ultimo_posto_bios:
            if self.BD_backup is None:
                logger.debug("[%s] Sem BD_backup anterior; transporte não calculado.", self.nome)
                return
            self.BS_posterior = time.perf_counter()
            transporte = round(self.BS_posterior - self.BD_backup, 2)
            self.atualizar_tempo(self.produto_atual, "tempo_transferencia", transporte)
        elif self.n_posto == ultimo_posto_bios:
            self.atualizar_tempo(self.produto_atual, "tempo_transferencia", 0.0)
        else:
            logger.error("[%s] Posto inválido para transporte.", self.nome)
            return

        tempo_ciclo = self.calcular_tempo_ciclo()
        self._notify()
        if tempo_ciclo is not None:
            self.atualizar_tempo(self.produto_atual, "tempo_ciclo", tempo_ciclo)

    def calcular_tempo_ciclo(self, idx: Optional[int] = None) -> Optional[float]:
        if self.df_historico.empty:
            logger.warning("[%s] Nenhum dado disponível para cálculo.", self.nome)
            return None
        if idx is None:
            idx = self.df_historico.index[-1]

        campos_tempos = [
            "arrival_time",
            "tempo_preparo",
            "tempo_montagem",
            "tempo_espera",
            "tempo_transferencia",
        ]

        valores: List[float] = []
        for c in campos_tempos:
            v = self.df_historico.at[idx, c]
            if pd.notna(v):
                try:
                    valores.append(float(v))
                except Exception:
                    logger.debug("[%s] Valor não numérico em %s (linha %d): %r", self.nome, c, idx, v)

        if not valores:
            logger.info("[%s] Nenhum tempo válido para somar (linha %d).", self.nome, idx)
            return None

        tempo_ciclo = round(sum(valores), 2)
        self.contador_produtos += 1
        return tempo_ciclo

    # ------------------------------------------------------------------
    # Tratamento de mensagens do dispositivo
    # ------------------------------------------------------------------
    def tratamento_dispositivo(self, payload: str) -> None:
        if payload in self.timestamp:
            self.timestamp[payload] = time.perf_counter()

            if payload == "BS":
                if self.posto_anterior is not None:
                    logger.debug("Chamando transporte do %s → %s", self.posto_anterior, self.id_posto)
                    self.transporte(self.posto_anterior)
                if self.maquina_estado == 0:
                    logger.info("[%s] - ESTADO 1 - BS", self.nome)
                    arrival = round(self.timestamp["BS"] - self.timestamp["BD"], 2)
                    self.inicia_montagem(arrival)
                    self.atualizar_estado(1)
                return

            if payload == "BT1" and self.maquina_estado == 1:
                logger.info("[%s] - ESTADO 2 - BT1", self.nome)
                preparo = round(self.timestamp["BT1"] - self.timestamp["BS"], 2)
                self.atualizar_tempo(self.produto_atual, "tempo_preparo", preparo)
                self.atualizar_estado(2)
                return

            if payload == "BT2" and self.maquina_estado == 2:
                logger.info("[%s] - ESTADO 3 - BT2", self.nome)
                montagem = round(self.timestamp["BT2"] - self.timestamp["BT1"], 2)
                self.atualizar_tempo(self.produto_atual, "tempo_montagem", montagem)
                self.atualizar_estado(3)
                return

            if payload == "BD" and self.maquina_estado == 3:
                logger.info("[%s] - ESTADO 4 - BD", self.nome)
                if self.produto_atual is None:
                    self.produto_atual = associacoes.palete_produto(self.palete_atual)
                espera = round(self.timestamp["BD"] - self.timestamp["BT2"], 2)
                self.atualizar_tempo(self.produto_atual, "tempo_espera", espera)

                if self.id_posto == "posto_0":
                    prod = associacoes.palete_produto(self.palete_atual)
                    if prod is not None:
                        self.atualiza_produto(prod)

                if self.id_posto == f"posto_{ultimo_posto_bios}":
                    self.calcula_transporte()
                    if self.produto_atual is not None:
                        associacoes.desassocia(self.produto_atual)

                if self.db_row_id_atual is not None:
                    fechar_linha(self.id_posto, self.db_row_id_atual)
                    self.db_row_id_atual = None

                self.produto_atual = None
                self.palete_atual = None
                self.BD_backup = time.perf_counter()
                self.atualizar_estado(0)
                return

        # Não é um timestamp: pode ser leitura NFC de palete
        elif verifica_palete_nfc(payload):
            if self.produto_atual is None or self.palete_atual is None:
                palete_lido = cartao_palete.get(payload)
                if palete_lido is None:
                    logger.warning("[%s] Cartão %s não mapeado em cartao_palete.", self.nome, payload)
                    return
                if self.id_posto == "posto_0":
                    self.palete_atual = palete_lido
                    self._notify()
                else:
                    self.tratamento_palete(palete_lido)
                    self._notify()

    # ------------------------------------------------------------------
    # Palete
    # ------------------------------------------------------------------
    def tratamento_palete(self, palete: str) -> None:
        produto_lido = associacoes.palete_produto(palete)
        if produto_lido and verifica_cod_produto(produto_lido):
            self.palete_atual = palete
            self.produto_atual = produto_lido
            self.atualiza_produto(self.produto_atual)
        else:
            logger.warning("[%s] - %s não foi associado a um produto válido.", self.nome, palete)

    # ------------------------------------------------------------------
    # Persistência
    # ------------------------------------------------------------------
    def carregarDados(self) -> pd.DataFrame:
        if self.csvPath.exists():
            logger.info("[%s] Carregando dados locais do posto.", self.nome)
            try:
                df = pd.read_csv(self.csvPath)
            except Exception as e:
                logger.error("[%s] Erro ao ler %s: %s", self.nome, self.csvPath, e)
                df = pd.DataFrame(columns=COLS_POSTO)
        else:
            logger.warning("[%s] Dados locais não encontrados (iniciando vazio).", self.nome)
            df = pd.DataFrame(columns=COLS_POSTO)

        # garante colunas
        for col in COLS_POSTO:
            if col not in df.columns:
                df[col] = pd.Series(dtype="object")
        return df

    def salvarDadosLocais(self) -> None:
        try:
            self.df_historico.to_csv(self.csvPath, index=False)
            # Opcional: exportar para Excel (custo de IO alto). Descomente se necessário.
            # self.df_historico.to_excel(self.XlsPath, index=False)
            logger.debug("[%s] Dados salvos em %s.", self.nome, self.csvPath)
        except Exception as e:
            logger.error("[%s] Falha ao salvar %s: %s", self.nome, self.csvPath, e)
    
    def _state_enum(self) -> PostoState:
        mapping = {0: PostoState.IDLE, 1: PostoState.BS, 2: PostoState.BT1, 3: PostoState.BT2}
        # quando está pronto para BD, state=3; após BD concluído voltamos a 0
        return mapping.get(self.maquina_estado, PostoState.BD if self.maquina_estado_anterior == 3 else PostoState.IDLE)

    def atualizar_estado(self, estado: int) -> None:
        self.maquina_estado_anterior = self.maquina_estado
        self.maquina_estado = estado
        if callable(self.mudanca_estado):
            try:
                self.mudanca_estado(self.id_posto, estado)
            except Exception as e:
                # Agora vamos logar o erro para saber o que quebrou no Supervisor.
                logger.error(f"Erro ao notificar mudança de estado no {self.id_posto}: {e}", exc_info=True)
        self._notify()

    def snapshot(self) -> PostoSnapshot:
        idx = self.df_historico.index[-1] if len(self.df_historico) else None
        def getv(col):
            if idx is None or col not in self.df_historico.columns:
                return None
            val = self.df_historico.at[idx, col]
            return float(val) if pd.notna(val) else None
        return PostoSnapshot(
            id=self.id_posto,
            state=self._state_enum(),
            produto=self.produto_atual,
            modelo="Proxy - CPD",
            palete=self.palete_atual,
            n_produtos=self.contador_produtos,
            arrival=getv("arrival_time"),
            t_preparo=getv("tempo_preparo"),
            t_montagem=getv("tempo_montagem"),
            t_espera=getv("tempo_espera"),
            t_transf=getv("tempo_transferencia"),
            t_ciclo=getv("tempo_ciclo"),
            last_update_ts=time.time(),
            funcionario_nome = self.funcionario_nome,
            funcionario_imagem = self.funcionario_imagem
        )

    def _notify(self):
        self._last_update = time.time()
        if callable(self.on_change):
            try:
                self.on_change(self.snapshot())
            except Exception:
                pass

    def ativa_batedor(self):
        if self.mqttc:
            self.mqttc.publish(f"rastreio_nfc/raspberry/{self.id_posto}/sistema", "batedor")
        return

    def ativa_camera(self):
        if self.mqttc:
            self.mqttc.publish(f"sistema/camera/{self.id_posto}", "restart")
        return

    def desativa_camera(self):
        if self.mqttc:
            self.mqttc.publish(f"sistema/camera/{self.id_posto}", "stop")
        return
    
    def controle_mqtt_camera(self, payload):
        if payload == "BS" and self.id_posto != "posto_0":
            self.ativa_camera()
        elif payload == "BT1" and self.id_posto == "posto_0":
            self.ativa_camera()
        elif payload == "BD":
            self.desativa_camera()
        return
    
    def get_estado(self):
        return self.maquina_estado
# -----------------------------------------------------------------------------
# MQTT → Roteamento de mensagens para cada Posto
# -----------------------------------------------------------------------------

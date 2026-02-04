# state.py
import time
import threading
from enum import Enum

class ProducaoStatus(Enum):
    OFF = 0
    ARMED = 1
    ON = 2

class ProducaoState:
    def __init__(self):
        self.status = ProducaoStatus.OFF
        self.inicio_ts = None
        self.alterada_por = None
        self.motivo = None
        self.meta = 0


class State:
    def __init__(self, total_postos: int):
        self._lock = threading.Lock()
        self.producao = ProducaoState()

        self.postos = {
            i: {
                "pronto": False,
                "em_producao": False,
                "snapshot": None,
                "updated_at": None,
            }
            for i in range(total_postos)
        }
        self.notifica_armando_producao = None # callback opcional


    # ---------- PRODUÇÃO ----------
    def armar_producao(self, meta: int = 0, por=None, motivo=None):
        with self._lock:
            self.producao.status = ProducaoStatus.ARMED
            self.producao.meta = meta
            self.producao.alterada_por = por
            self.producao.motivo = motivo
            self.producao.inicio_ts = None
        
        if callable(self.notifica_armando_producao):
            try:
                self.notifica_armando_producao()
            except Exception:
                pass

    def ligar_producao(self, por=None, motivo=None):
        with self._lock:
            if self.producao.status != ProducaoStatus.ON:
                self.producao.status = ProducaoStatus.ON
                self.producao.inicio_ts = time.time()
                self.producao.alterada_por = por
                self.producao.motivo = motivo

    def desligar_producao(self, por=None, motivo=None):
        with self._lock:
            self.producao.status = ProducaoStatus.OFF
            self.producao.inicio_ts = None
            self.producao.meta = 0
            self.producao.alterada_por = por
            self.producao.motivo = motivo

    def producao_ligada(self) -> bool:
        with self._lock:
            return self.producao.status == ProducaoStatus.ON

    def producao_armada(self) -> bool:
        with self._lock:
            return self.producao.status == ProducaoStatus.ARMED

    # ---------- POSTOS ----------
    def set_posto_pronto(self, posto_id: int, pronto: bool):
        with self._lock:
            self.postos[posto_id]["pronto"] = pronto
            self.postos[posto_id]["updated_at"] = time.time()

    def update_snapshot(self, posto_id: int, snapshot: dict):
        with self._lock:
            self.postos[posto_id]["snapshot"] = snapshot
            self.postos[posto_id]["updated_at"] = time.time()

    # ---------- REGRA DE INÍCIO ----------
    def pode_iniciar_producao(self) -> bool:
        """
        REGRA CENTRAL.
        Exemplo atual: todos os postos prontos.
        """
        with self._lock:
            return all(p["pronto"] for p in self.postos.values())

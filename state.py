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

        self.ordem_codigo = None
        self.meta = 0
        self.log_producao_id = None


class State:
    def __init__(self, ultimo_posto: int):
        self._lock = threading.Lock()
        self.producao = ProducaoState()

        self.postos = {
            i: {
                "pronto": False,
                "em_producao": False,
                "snapshot": None,
                "updated_at": None,
            }
            for i in range(ultimo_posto+1)
        }
        self.notifica_armando_producao = None # callback opcional


    # ---------- PRODUÇÃO ----------
    def armar_producao(self, meta: int = 0, ordem_codigo: str | None = None, log_id=None, por=None, motivo=None):
        with self._lock:
            self.producao.status = ProducaoStatus.ARMED
            self.producao.meta = meta
            self.producao.ordem_codigo = ordem_codigo
            self.producao.log_producao_id = log_id
            self.producao.alterada_por = por
            self.producao.motivo = motivo
            self.producao.inicio_ts = None
        
        if callable(self.notifica_armando_producao):
            try:
                self.notifica_armando_producao()
            except Exception:
                pass

    def ligar_producao(self, por=None, motivo=None, ordem_codigo: str | None = None, meta: int = 0):
        with self._lock:
            if self.producao.status != ProducaoStatus.ON:
                self.producao.status = ProducaoStatus.ON
                self.producao.inicio_ts = time.time()
                self.producao.alterada_por = por
                self.producao.motivo = motivo
                self.producao.ordem_codigo = ordem_codigo
                self.producao.meta = int(meta or 0)

    def desligar_producao(self, por=None, motivo=None):
        with self._lock:
            self.producao.status = ProducaoStatus.OFF
            self.producao.inicio_ts = None
            self.producao.meta = 0
            self.producao.ordem_codigo = None
            self.producao.log_producao_id = None
            self.producao.alterada_por = por
            self.producao.motivo = motivo

    def get_producao_status(self) -> str:
        with self._lock:
            return self.producao.status.name 
    
    def get_meta(self) -> int:
        with self._lock:
            return int(getattr(self.producao, "meta", 0) or 0)

    def get_ordem_atual(self):
        with self._lock:
            return getattr(self.producao, "ordem_codigo", None)
    def get_log_producao_id(self):
        with self._lock:
            return getattr(self.producao, "log_producao_id", None)

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
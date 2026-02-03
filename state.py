# state.py
import time
import threading


class ProducaoState:
    def __init__(self):
        self.ligada = False
        self.inicio_ts = None
        self.alterada_por = None
        self.motivo = None


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

    # ---------- PRODUÇÃO ----------
    def ligar_producao(self, por=None, motivo=None):
        with self._lock:
            if not self.producao.ligada:
                self.producao.ligada = True
                self.producao.inicio_ts = time.time()
                self.producao.alterada_por = por
                self.producao.motivo = motivo

    def desligar_producao(self, por=None, motivo=None):
        with self._lock:
            self.producao.ligada = False
            self.producao.inicio_ts = None
            self.producao.alterada_por = por
            self.producao.motivo = motivo

    def producao_ligada(self) -> bool:
        with self._lock:
            return self.producao.ligada

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

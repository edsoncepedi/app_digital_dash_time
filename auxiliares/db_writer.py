# auxiliares/db_writer.py
import time
import threading
from queue import Queue, Empty
from dataclasses import dataclass
import pandas as pd

from auxiliares.db_core import Conectar_DB  # usa seu Conectar_DB

@dataclass
class InsertJob:
    df: pd.DataFrame
    db_name: str
    table: str
    max_retries: int = 5

class DBWriter:
    def __init__(self, max_queue: int = 500):
        self.q = Queue(maxsize=max_queue)
        self._stop = threading.Event()
        self._t = threading.Thread(target=self._run, daemon=True)
        self._t.start()

    def submit(self, job: InsertJob) -> bool:
        """Retorna False se a fila estiver cheia."""
        try:
            self.q.put(job, block=False)
            return True
        except Exception:
            return False

    def stop(self, timeout: float = 2.0):
        self._stop.set()
        self._t.join(timeout=timeout)

    def _run(self):
        while not self._stop.is_set():
            try:
                job = self.q.get(timeout=0.2)
            except Empty:
                continue

            ok = False
            attempt = 0

            while not ok and attempt <= job.max_retries and not self._stop.is_set():
                attempt += 1
                try:
                    engine = Conectar_DB(job.db_name)
                    job.df.to_sql(job.table, engine, if_exists="append", index=False)
                    ok = True
                except Exception as e:
                    # backoff simples: 0.5s, 1s, 2s, 4s...
                    wait = min(0.5 * (2 ** (attempt - 1)), 10.0)
                    print(f"[DBWriter] ERRO insert {job.table} (tentativa {attempt}/{job.max_retries}): {e} | retry em {wait:.1f}s")
                    time.sleep(wait)

            if not ok:
                print(f"[DBWriter] FALHA DEFINITIVA: não consegui inserir em {job.table} após {job.max_retries} tentativas.")

            self.q.task_done()

# instância global (um único worker)
db_writer = DBWriter()
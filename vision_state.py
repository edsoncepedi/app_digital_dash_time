from __future__ import annotations

import json
import re
import time
import threading
from dataclasses import dataclass
from typing import Dict, Optional, Tuple, Any


VALID_ESTADOS = {"INICIO", "MONTAGEM", "FINALIZADO"}


@dataclass
class VisionSnapshot:
    posto: str                 # ex: "posto_0"
    estado: str                # "INICIO" | "MONTAGEM" | "FINALIZADO"
    since_ts: float            # desde quando esse estado está ativo
    last_seen_ts: float        # quando recebemos a última msg MQTT desse posto


class VisionStateStore:
    """
    Cache do estado da visão por posto.
    - Thread-safe (Flask + MQTT callbacks)
    - Mantém "since" para debounce/estabilidade
    - Mantém "last_seen" para TTL/stale detection
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._by_posto: Dict[str, VisionSnapshot] = {}

    # ----------------------------
    # API de consulta
    # ----------------------------

    def get_estado(self, posto: str) -> str:
        """Retorna o estado atual (ou INICIO se não existir)."""
        posto = self._normalize_posto(posto)
        with self._lock:
            snap = self._by_posto.get(posto)
            return snap.estado if snap else "INICIO"

    def get_snapshot(self, posto: str) -> VisionSnapshot:
        """Retorna snapshot completo (cria default se não existir)."""
        posto = self._normalize_posto(posto)
        now = time.time()
        with self._lock:
            snap = self._by_posto.get(posto)
            if snap:
                return snap
            default = VisionSnapshot(posto=posto, estado="INICIO", since_ts=now, last_seen_ts=0.0)
            self._by_posto[posto] = default
            return default

    def is_stale(self, posto: str, max_age_s: float = 3.0) -> bool:
        """True se o estado está 'velho' (sem update MQTT há muito tempo)."""
        posto = self._normalize_posto(posto)
        now = time.time()
        with self._lock:
            snap = self._by_posto.get(posto)
            if not snap:
                return True
            return (now - snap.last_seen_ts) > float(max_age_s)

    def is_finalizado(
        self,
        posto: str,
        min_stable_s: float = 0.5,
        max_age_s: float = 3.0
    ) -> bool:
        """
        True somente se:
        - estado == FINALIZADO
        - não está stale (TTL)
        - FINALIZADO está estável por pelo menos min_stable_s
        """
        posto = self._normalize_posto(posto)
        now = time.time()
        with self._lock:
            snap = self._by_posto.get(posto)
            if not snap:
                return False

            if (now - snap.last_seen_ts) > float(max_age_s):
                return False

            if snap.estado != "FINALIZADO":
                return False

            return (now - snap.since_ts) >= float(min_stable_s)

    # ----------------------------
    # Atualização (interno)
    # ----------------------------

    def update_estado(self, posto: str, estado: str, ts: Optional[float] = None) -> bool:
        """
        Atualiza o cache.
        Retorna True se houve mudança de estado.
        """
        posto = self._normalize_posto(posto)
        estado = self._normalize_estado(estado)
        now = ts or time.time()

        with self._lock:
            prev = self._by_posto.get(posto)
            if not prev:
                self._by_posto[posto] = VisionSnapshot(
                    posto=posto,
                    estado=estado,
                    since_ts=now,
                    last_seen_ts=now,
                )
                return True

            changed = (prev.estado != estado)
            if changed:
                prev.estado = estado
                prev.since_ts = now

            prev.last_seen_ts = now
            return changed

    # ----------------------------
    # MQTT handler
    # ----------------------------

    def handle_mqtt_message_vision(self, message: Any) -> None:
        """
        Handler compatível com flask_mqtt (message.topic / message.payload).
        """
        try:
            topic = getattr(message, "topic", "")
            payload_bytes = getattr(message, "payload", b"")
            payload = payload_bytes.decode(errors="ignore") if isinstance(payload_bytes, (bytes, bytearray)) else str(payload_bytes)
        except Exception:
            return

        posto, estado = self._parse_topic_and_payload(topic, payload)
        if not posto or not estado:
            return

        self.update_estado(posto, estado)

    # ----------------------------
    # Parsing / normalização
    # ----------------------------

    def _parse_topic_and_payload(self, topic: str, payload: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Tenta extrair posto e estado de:
        - topic: visao/posto_0/estado   payload: FINALIZADO
        - topic: visao/0/estado        payload: {"estado":"MONTAGEM"}
        - topic: camera/posto_1/estado ...
        """
        topic = (topic or "").strip()
        payload = (payload or "").strip()

        posto = self._posto_from_topic(topic)
        if not posto:
            return None, None

        # payload pode ser JSON
        estado = None
        if payload.startswith("{") and payload.endswith("}"):
            try:
                data = json.loads(payload)
                if isinstance(data, dict):
                    estado = data.get("estado") or data.get("state")
            except Exception:
                estado = None
        else:
            estado = payload

        if not estado:
            return posto, None

        try:
            estado = self._normalize_estado(str(estado))
        except Exception:
            return posto, None

        return posto, estado

    def _posto_from_topic(self, topic: str) -> Optional[str]:
        # Captura ".../(posto_2|2)/estado"
        m = re.search(r"/(?P<posto>posto_\d+|\d+)/estado$", topic)
        if not m:
            return None
        raw = m.group("posto")
        return self._normalize_posto(raw)

    def _normalize_posto(self, posto: str) -> str:
        posto = (posto or "").strip().lower()
        if posto.isdigit():
            return f"posto_{posto}"
        if re.fullmatch(r"posto_\d+", posto):
            return posto
        # fallback: tenta extrair número
        m = re.search(r"(\d+)", posto)
        if m:
            return f"posto_{m.group(1)}"
        return posto or "posto_0"

    def _normalize_estado(self, estado: str) -> str:
        estado = (estado or "").strip().upper()
        # aceita variações
        aliases = {
            "FINISH": "FINALIZADO",
            "DONE": "FINALIZADO",
            "FINAL": "FINALIZADO",
            "MOUNT": "MONTAGEM",
            "ASSEMBLY": "MONTAGEM",
            "START": "INICIO",
            "BEGIN": "INICIO",
        }
        estado = aliases.get(estado, estado)
        if estado not in VALID_ESTADOS:
            raise ValueError(f"Estado inválido: {estado}")
        return estado

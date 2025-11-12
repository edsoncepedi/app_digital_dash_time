# app/supervisor.py
from dataclasses import asdict

class PostoSupervisor:
    def __init__(self, postos, socketio, mqttc):
        self.postos = postos          # dict: {"posto_0": Posto, ...}
        self.socketio = socketio      # o MESMO socketio do main.py
        self.mqttc = mqttc            # o MESMO mqtt do main.py
        self._snapshots = {}          # cache p/ snapshot inicial

        # conecta o callback on_change de cada Posto
        for p in self.postos.values():
            p.on_change = self._on_change

    def _on_change(self, snap):
        # snap é PostoSnapshot; precisamos JSON-friendly
        d = asdict(snap)
        d["state"] = int(snap.state.value)   # Enum -> int
        self._snapshots[snap.id] = snap
        # envia só para quem está na sala do posto
        self.socketio.emit("posto/state_changed", d, room=f"posto:{snap.id}")

    def get_snapshot(self, posto_id):
        snap = self._snapshots.get(posto_id)
        if not snap:
            return None
        d = asdict(snap)
        d["state"] = int(snap.state.value)
        return d

    def command(self, posto_id, cmd, **kwargs):
        p = self.postos[posto_id]
        if cmd == "buzzer":
            p.set_buzzer(kwargs.get("on", True))
        elif cmd == "light":
            p.set_light(kwargs.get("color", "green"))

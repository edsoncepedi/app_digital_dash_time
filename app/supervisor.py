#app/supervisor.py 
from dataclasses import asdict 
import auxiliares.classes as classes 
from auxiliares.utils import reiniciar_sistema 
class PostoSupervisor: 
    def __init__(self, postos, socketio, mqttc): 
        self.postos = postos # dict: {"posto_0": Posto, ...} 
        self.socketio = socketio # o MESMO socketio do main.py 
        self.mqttc = mqttc # o MESMO mqtt do main.py 
        self._snapshots = {} # cache p/ snapshot inicial 
        self.meta_producao = None # conecta o callback on_change de cada Posto 
        for p in self.postos.values(): 
            p.on_change = self._on_change 
            
    def _on_change(self, snap): 
        # snap é PostoSnapshot; precisamos JSON-friendly 
        d = asdict(snap) 
        d["state"] = int(snap.state.value) # Enum -> int 
        self._snapshots[snap.id] = snap  
        # envia só para quem está na sala do posto 
        self.socketio.emit("posto/state_changed", d, room=f"posto:{snap.id}") 
        if snap.id == self._ultimo_posto_id(): 
            if snap.n_produtos == self.meta_producao: 
                self.socketio.emit("timer/control", {"action": "stop"}) 
                classes.encerra_producao() 
                self.socketio.emit("alerta_geral", {'mensagem': "Produção Finalizada. Reinicie o Sistema", 'cor': "#00b377", 'tempo': 1000}) 
                reiniciar_sistema(debug=False, dados=False, backup=True) 
        
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
    
    def injeta_meta_producao(self, meta): 
        self.meta_producao = meta 
        
    def _ultimo_posto_id(self): 
        """ Considerando que os ids são 'posto_0', 'posto_1', ..., 'posto_n' """ 
        idx = len(self.postos) - 1 
        return f"posto_{idx}"
# app/supervisor.py
from dataclasses import asdict
import time
import math # Importado para a lógica de projeção
import auxiliares.classes as classes
from auxiliares.utils import reiniciar_sistema, posto_anterior, posto_proximo


class PostoSupervisor:
    def __init__(self, postos, socketio, mqttc):
        self.postos = postos
        self.socketio = socketio
        self.mqttc = mqttc
        self._snapshots = {}
        
        # NOVAS VARIÁVEIS DE ESTADO GLOBAL
        self.meta_producao = 0 
        self.timer_running = False
        self.timer_start_ts = None
        self.timer_accumulated = 0

        for p in self.postos.values():
            p.on_change = self._on_change
            p.mudanca_estado = self.mudanca_estado

# --- MÉTODOS AUXILIARES NOVOS ---
    def _get_current_time_ms(self):
        tempo_ms = self.timer_accumulated * 1000
        if self.timer_running and self.timer_start_ts:
            delta = time.time() - self.timer_start_ts
            tempo_ms += (delta * 1000)
        return tempo_ms

    def _calcular_projecao_str(self, tempo_ms, producao_atual):
        """ Calcula projeção e retorna string formatada (ex: '2 h 30 min') """
        if producao_atual <= 0 or self.meta_producao <= 0:
            return "--"
        
        # Regra de três: (Tempo Decorrido / Peças Feitas) * Meta Total
        tempo_por_peca = tempo_ms / producao_atual
        tempo_total_estimado_ms = tempo_por_peca * self.meta_producao
        
        total_seconds = int(tempo_total_estimado_ms / 1000)
        horas = total_seconds // 3600
        minutos = (total_seconds % 3600) // 60
        segundos = total_seconds % 60
        
        texto = ""
        if horas > 0:
            texto += f"{horas} h "
        texto += f"{minutos} min {segundos} s"
        return texto
    
    def mudanca_estado(self, posto_id, novo_estado):
        if posto_id == 'posto_0':
            if novo_estado == 3: # Entrou em Espera
                if self.postos[posto_proximo(posto_id)].get_estado() == 0: # Idle
                    self.command(posto_id, "ativa_batedor")
        elif posto_id == self._ultimo_posto_id():
            if novo_estado == 3: # Entrou em Espera
                self.command(posto_id, "ativa_batedor")
            elif novo_estado == 0: # Entrou em Idle
                if self.postos[posto_anterior(posto_id)].get_estado() == 3: # Espera
                    self.command(posto_anterior(posto_id), "ativa_batedor")
        else:
            if novo_estado == 3: # Entrou em Espera
                if self.postos[posto_proximo(posto_id)].get_estado() == 0: # Idle
                    self.command(posto_id, "ativa_batedor")
            elif novo_estado == 0: # Entrou em Idle 
                if self.postos[posto_anterior(posto_id)].get_estado() == 3: # Espera
                    self.command(posto_anterior(posto_id), "ativa_batedor")

    def _on_change(self, snap):
        d = asdict(snap) 
        
        # --- CORREÇÃO DO ENUM (mantido) ---
        if hasattr(snap.state, 'value'):
            d["state"] = snap.state.value
        else:
            d["state"] = snap.state
        # ---------------------

        self._snapshots[snap.id] = snap  
        self.socketio.emit("posto/state_changed", d, room=f"posto:{snap.id}") 
        
        # LÓGICA DE ATUALIZAÇÃO GLOBAL E FIM DE PRODUÇÃO
        if snap.id == self._ultimo_posto_id():
            
            # --- NOVO CÁLCULO DE PROJEÇÃO E EMISSÃO DE UPDATE ---
            tempo_atual = self._get_current_time_ms()
            projecao_str = self._calcular_projecao_str(tempo_atual, snap.n_produtos)
            
            # Emite o evento de produção com a projeção calculada
            self.socketio.emit("producao/update", {
                "atual": snap.n_produtos,
                "meta": self.meta_producao,
                "projecao": projecao_str
            })
            # --- FIM DO UPDATE ---

            if self.meta_producao > 0 and snap.n_produtos >= self.meta_producao: 
                self.parar_timer()
                classes.encerra_producao() 
                self.socketio.emit("timer/control", {"action": "stop"}) 
                self.socketio.emit("alerta_geral", {'mensagem': "Produção Finalizada. Reinicie o Sistema", 'cor': "#00b377", 'tempo': 1000}) 
                #reiniciar_sistema(debug=False, dados=False, backup=True)

    def iniciar_timer(self, meta):
        self.meta_producao = meta
        if not self.timer_running:
            self.timer_running = True
            self.socketio.emit("producao/control", {"meta_producao": meta})
            self.socketio.emit("timer/control", {"action": "start"})
            self.timer_start_ts = time.time()

    def parar_timer(self):
        if self.timer_running:
            self.timer_running = False
            self.socketio.emit("timer/control", {"action": "stop"})
            if self.timer_start_ts:
                delta = time.time() - self.timer_start_ts
                self.timer_accumulated += delta
            self.timer_start_ts = None
            
    def resetar_timer(self):
        self.socketio.emit("timer/control", {"action": "restart"})
        self.timer_running = False
        self.timer_start_ts = None
        self.timer_accumulated = 0

    def get_global_status(self):
        """ Retorna um dicionário com TUDO que o front precisa ao dar F5 """
        
        # 1. Calcular tempo decorrido atual
        tempo_ms = self._get_current_time_ms()

        # 2. Pegar produção do último posto
        ultimo_id = self._ultimo_posto_id()
        prod_atual = 0
        if ultimo_id in self._snapshots:
            prod_atual = self._snapshots[ultimo_id].n_produtos
        elif ultimo_id in self.postos:
            prod_atual = self.postos[ultimo_id].contador_produtos
            
        # 3. NOVO: Calcular projeção aqui para enviar no sync inicial
        projecao_str = self._calcular_projecao_str(tempo_ms, prod_atual)

        return {
            "meta": self.meta_producao,
            "producao_atual": prod_atual,
            "projecao": projecao_str, # <--- Enviando a projeção pronta
            "timer_ms": tempo_ms,
            "timer_running": self.timer_running
        }

    def _ultimo_posto_id(self):
        idx = len(self.postos) - 1
        return f"posto_{idx}"
    
    def get_snapshot(self, posto_id): 
        snap = self._snapshots.get(posto_id) 
        
        if not snap and posto_id in self.postos:
            snap = self.postos[posto_id].snapshot()

        if not snap: 
            return None 
        
        d = asdict(snap) 
        
        if hasattr(snap.state, 'value'):
            d["state"] = snap.state.value
        else:
            d["state"] = snap.state
        
        return d

    def command(self, posto_id, cmd, **kwargs): 
        if posto_id in self.postos:
            p = self.postos[posto_id] 
            if cmd == "buzzer": 
                p.set_buzzer(kwargs.get("on", True)) 
            elif cmd == "light": 
                p.set_light(kwargs.get("color", "green"))
            elif cmd == "ativa_batedor":
                p.ativa_batedor()
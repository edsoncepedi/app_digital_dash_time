# app/supervisor.py
from dataclasses import asdict
import time
import math # Importado para a lógica de projeção
from typing import Optional
from auxiliares.utils import reiniciar_sistema, posto_anterior, posto_proximo, posto_nome_para_id
from auxiliares.banco_post import consulta_funcionario_posto, Conectar_DB
from auxiliares.log_producao_repo import LogProducaoRepo
import logging

# -----------------------------------------------------------------------------
# LOGGING
# -----------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(asctime)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

class PostoSupervisor:
    def __init__(self, postos, socketio, mqttc, state, vision_state=None):
        self.postos = postos
        self.socketio = socketio
        self.mqttc = mqttc
        self.vision_state = vision_state
        self._snapshots = {}
        self.operadores_ativos = {}
        self.state = state
        
        # NOVAS VARIÁVEIS DE ESTADO GLOBAL
        self.meta_producao = 0 
        self.timer_running = False
        self.timer_start_ts = None
        self.timer_accumulated = 0

        self.state.notifica_armando_producao = self.notifica_armando_producao

        self._bt2_reject_cooldown = {}  

        self._log_repo = LogProducaoRepo(Conectar_DB("funcionarios"))


        for p in self.postos.values():
            p.on_change = self._on_change
            p.mudanca_estado = self.mudanca_estado
            p.transporte = self.transporte

     # -------------------------------------------------------------------------
     # ALERTA DIRECIONADO PARA UM POSTO (ROOM)
     # -------------------------------------------------------------------------
    def emit_alerta_posto(self, posto_id: str, mensagem: str, cor: str = "#ff0000", tempo: int = 2500):
        """
        Emite popup somente para o posto específico.
        Ex: posto_id = 'posto_3'
        """
        try:
            self.socketio.emit(
                "alerta_posto",
                {"mensagem": mensagem, "cor": cor, "tempo": tempo},
                room=f"posto:{posto_id}"
            )
        except Exception:
            pass


    def _alerta_bt2_bloqueado(self, posto_id: str):
        now = time.time()
        last = self._bt2_reject_cooldown.get(posto_id, 0)

        # cooldown: 1.0s
        if (now - last) < 1.0:
            return

        self._bt2_reject_cooldown[posto_id] = now

        self.emit_alerta_posto(
            posto_id=posto_id,
            mensagem="Finalize a montagem (visão) e pressione BT2 novamente.",
            cor="#ff0000",
            tempo=2500
        )
    def _evento_bloqueado(self, posto, payload: str) -> bool:
        """
        Retorna True se o evento deve ser BLOQUEADO e não entregue à FSM do posto.
        """

        # Só travamos BT2, e somente quando o posto está na fase de montagem
        if payload != "BT2":
            return False

        if posto.get_estado() != 2:
            return False

        # Checa visão (cache MQTT)
        ok = self.vision_state.is_finalizado(
            posto.id_posto,
            min_stable_s=0.5,
            max_age_s=3.0
        )

        if ok:
            return False

        # Não está finalizado => bloqueia
        self._alerta_bt2_bloqueado(posto.id_posto)
        return True

    def handle_mqtt_message(self, message):
        try:
            topic = message.topic
            payload_bytes = message.payload
            payload = payload_bytes.decode() if isinstance(payload_bytes, (bytes, bytearray)) else str(payload_bytes)
        except Exception as e:
            logger.error("Mensagem MQTT inválida: %s", e)
            return
        
        # Verificação que controla se a mensagem deve ser processada de acordo com o estado da produção
        if not self.state.producao_ligada():
            return
        
        parts = topic.split("/")
        if len(parts) != 4:
            return

        sistema, embarcado, dispositivo, agente = parts

        # ✅ regra global fica AQUI
        if sistema != "rastreio_nfc" or agente != "dispositivo":
            return
        
        posto = self.postos.get(dispositivo)
        
        if not posto:
            logger.warning("Posto %s não inicializado.", dispositivo)
            return
        
        posto.controle_mqtt_camera(payload)

        self.processar_evento_dispositivo(posto, payload)

    def processar_evento_dispositivo(self, posto, payload: str):
        """
        ÚNICO lugar que entrega eventos do ESP32 para o Posto.
        """

        # 🔒 trava de eventos (gate)
        if self._evento_bloqueado(posto, payload):
            return

        # evento válido: entra na FSM normal
        posto.tratamento_dispositivo(payload)

    def iniciar_producao(self, origem="sistema", ordem_codigo=None, meta_producao=0):
        if self.state.producao_ligada():
            return  # idempotente

        self.state.ligar_producao(
            por=origem,
            motivo="todos os operadores presentes",
            ordem_codigo=ordem_codigo,
            meta=meta_producao
        )

        #Sinal Esteira Iniciada
        if self.mqttc:
            self.mqttc.publish("ControleProducao_DD", "Start")

        for posto in self.postos.values():
            posto.inicia_prod_tempo()
            posto._notify()

        self.resetar_timer()
        self.iniciar_timer(meta_producao)


    # --- MÉTODOS AUXILIARES NOVOS ---
    def atualizar_operador_posto(self, posto_nome, dados_operador):
        """
        Atualiza estado interno e emite eventos.
        Nunca deve quebrar o fluxo de check-in/check-out.
        """
        self.operadores_ativos[posto_nome] = dados_operador
        
        # ⭐ SINCRONIZA COM O POSTO
        if posto_nome in self.postos:
            if dados_operador is None:
                self.postos[posto_nome].add_funcionario(None, None)
            else:
                self.postos[posto_nome].add_funcionario(
                    dados_operador.get("nome"),
                    dados_operador.get("foto")
                )

            self.postos[posto_nome]._notify()

        # 1) Atualiza prontidão no state (pode falhar por id fora do range, etc)
        try:
            posto_id = posto_nome_para_id(posto_nome)
            self.state.set_posto_pronto(posto_id, dados_operador is not None)
        except Exception as e:
            logger.error("Falha ao setar posto pronto (%s): %r", posto_nome, e, exc_info=True)

        payload = {
            "posto": posto_nome,
            "operador": dados_operador,
            "online": dados_operador is not None,
        }

        # 2) Emissões socket não podem derrubar
        try:
            self.socketio.emit("posto/operador_changed", payload, room=f"posto:{posto_nome}")
            self.socketio.emit("global/operador_update", payload)
        except Exception as e:
            logger.error("Falha ao emitir socket (%s): %r", posto_nome, e, exc_info=True)

        # 3) Tentar iniciar produção não pode derrubar
        try:
            self.tentar_iniciar_producao()
        except Exception as e:
            logger.error("Falha ao tentar iniciar produção: %r", e, exc_info=True)


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
        # LÓGICA DE ATIVAÇÃO DE BATEDOR
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
        
        # LÓGICA DE ATIVAÇÃO DA CÂMERA
        """
        if novo_estado == 1: # Chegou no Posto
            self.command(posto_id, "ativa_camera")
        elif novo_estado == 3: # Entrou em Idle
            self.command(posto_id, "desativa_camera")"""

    def transporte(self, posto_id):
        logger.debug("Chamando transporte do %s → %s", posto_anterior(posto_id), posto_id)
        self.postos[posto_id].calcula_transporte()

    def _on_change(self, snap):
        d = asdict(snap) 
        
        # --- CORREÇÃO DO ENUM (mantido) ---
        if hasattr(snap.state, 'value'):
            d["state"] = snap.state.value
        else:
            d["state"] = snap.state

        # ---------------------
        # ✅ INCLUI OPERADOR (pra não sumir no front)
        d["operador"] = self.operadores_ativos.get(snap.id)
        d["operador_online"] = (d["operador"] is not None)
        
        # =========================
        # CALCULO DO PROGRESSO
        # =========================

        if self.meta_producao > 0:
            mats_percent = int(
                (snap.n_produtos / self.meta_producao) * 100
            )
            mats_percent = max(0, min(100, mats_percent))
        else:
            mats_percent = 0

        d["mats_percent"] = mats_percent

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

                # 🔥 Finaliza log_producao por meta atingida
                log_id = self.state.get_log_producao_id()
                if log_id:
                    try:
                        self._log_repo.finalizar(log_id, "meta atingida")
                    except Exception:
                        pass

                self.state.desligar_producao(
                    por="sistema",
                    motivo="meta atingida"
                )
                if self.mqttc:
                    self.mqttc.publish("ControleProducao_DD", "Stop")
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
            "timer_running": self.timer_running,
            "operadores": self.operadores_ativos
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
        
        # ✅ INCLUI OPERADOR NO SNAPSHOT (F5 / join)
        d["operador"] = self.operadores_ativos.get(posto_id)
        d["operador_online"] = (d["operador"] is not None)

        return d

    def command(self, posto_id, cmd, **kwargs): 
        if posto_id in self.postos:
            p = self.postos[posto_id] 
            if cmd == "ativa_batedor":
                p.ativa_batedor()
            elif cmd == "ativa_camera":
                p.ativa_camera()
            elif cmd == "desativa_camera":
                p.desativa_camera()

    def notifica_armando_producao(self):
        self.tentar_iniciar_producao()

    def tentar_iniciar_producao(self):
        if not self.state.producao_armada():
            return

        if not self.state.pode_iniciar_producao():
            return

        # 🔥 condição satisfeita
        self.iniciar_producao(
            origem="checkin",
            ordem_codigo=self.state.get_ordem_atual(),
            meta_producao=self.state.get_meta()
        )

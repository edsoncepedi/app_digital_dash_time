from auxiliares.classes import verifica_estado_producao
from auxiliares.configuracoes import ultimo_posto_bios
import auxiliares.classes as classes
from auxiliares.utils import verifica_cod_produto
from datetime import datetime
from time import sleep
import threading
from flask_socketio import disconnect
from flask import request

clientes_associacao = set()  # para guardar sids da página de associação

def tem_cliente_associacao():
    #Se tiver cliente retorna True senão False
    return len(clientes_associacao) >= 1

def configurar_socketio_handlers(socketio):
    # Super função que é chamada assim que um cliente se conecta
    @socketio.on('connect')
    def handle_connect():
        pass

    @socketio.on('pagina_associacao_connect')
    def pagina_associacao_connect():
        sid = request.sid
        global clientes_associacao

        if len(clientes_associacao) >= 1:
            print(f"Cliente {sid} tentou conectar na associação, mas já tem cliente. Desconectando.")
            disconnect()
        else:
            clientes_associacao.add(sid)
            print(f"Cliente {sid} conectado na página de associação.")

    @socketio.on('disconnect')
    def on_disconnect():
        sid = request.sid
        if sid in clientes_associacao:
            clientes_associacao.remove(sid)
            print(f"Cliente {sid} desconectado da página de associação.")

    def enviar_status_producao_periodicamente():
        while True:
            status = verifica_estado_producao()  # Ex: "Ligada", "Desligada", etc.
            socketio.emit('atualiza_status_producao', {
                'status': status
            })
            sleep(1)

    threading.Thread(target=enviar_status_producao_periodicamente, daemon=True).start()

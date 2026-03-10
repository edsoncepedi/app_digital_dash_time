from auxiliares.classes import verifica_estado_producao
from auxiliares.configuracoes import ultimo_posto_bios
import auxiliares.classes as classes
from auxiliares.utils import verifica_cod_produto
from datetime import datetime
from time import sleep


def configurar_socketio_handlers(socketio, supervisor):

    # cliente conectou
    @socketio.on('connect')
    def handle_connect():
        print("Cliente conectado!")

    # cliente desconectou
    @socketio.on('disconnect')
    def on_disconnect():
        print("Cliente desconectado")

    # envia status da produção periodicamente
    def enviar_status_producao_periodicamente():
        while True:
            try:
                socketio.emit("atualiza_status_producao", {
                    "status": supervisor.state.get_producao_status()
                })
            except Exception as e:
                print("Erro ao enviar status:", e)

            socketio.sleep(1)

    socketio.start_background_task(enviar_status_producao_periodicamente)
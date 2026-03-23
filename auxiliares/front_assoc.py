from auxiliares.utils import verifica_palete_nfc, cartao_palete
import auxiliares.classes as classes
from auxiliares.configuracoes import ultimo_posto_bios


def front_mqtt_assoc(message, socketio, state, supervisor):
    # Separa a mensagem em topico e payload
    topic = message.topic
    payload = message.payload.decode()
    topicos = topic.split("/")

    if len(topicos) != 4:
        return
    else:
        sistema, embarcado, dispositivo, agente = topicos 

    if sistema == "rastreio_nfc" and embarcado == "esp32" and dispositivo == "posto_0" and agente == "dispositivo":
        if verifica_palete_nfc(payload):
            if state.producao_ligada():
                palete = cartao_palete[payload]

                if classes.associacoes.palete_produto(palete) is not None:
                    logger.warning("[%s] Palete NFC %s associado a produto. Ignorando.", dispositivo, palete)
                    socketio.emit('aviso_ao_operador_assoc', {'mensagem': f"Palete {palete} já associado a um produto da produção.", 'cor': "#dc3545", 'tempo': None})
                    return

                supervisor.postos['posto_0'].set_palete_atual(palete)

                socketio.emit('palete_detectado', {'palete': palete})
                socketio.emit(
                    "aviso_ao_operador_assoc",
                    {
                        "mensagem": "Pressione o botão de impressão de Tag para iniciar o Checklist de Componentes.",
                        "cor": "#202CEB",
                        "tempo": None
                    },
                    room=f"posto:posto_0"
                )
                return
            elif state.producao_armada():
                socketio.emit('aviso_ao_operador_assoc', {'mensagem': "Produção armada. Retire o palete do Posto 0 e Espere o início da produção.", 'cor': "#ffc107", 'tempo': None})
                return
            else:
                socketio.emit('aviso_ao_operador_assoc', {'mensagem': "Produção não iniciada. Retire o palete do Posto 0 e Espere o início da produção.", 'cor': "#dc3545", 'tempo': None})
                return
        elif payload == "BD" and not state.producao_ligada():
            socketio.emit("fechar_popup",room=f"posto:posto_0")
        elif payload in ["BS", "BT1", "BT2", "BD"]:
            return
        else:
            socketio.emit('aviso_ao_operador_assoc', {'mensagem': "Achou que eu tava brincando é?", 'cor': "#2fcce0", 'tempo': 3000})
            return
    else:
        return
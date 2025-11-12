from auxiliares.utils import verifica_palete_nfc, cartao_palete
from auxiliares.classes import verifica_estado_producao
from auxiliares.configuracoes import ultimo_posto_bios


def front_mqtt_assoc(message, socketio):
    # Separa a mensagem em topico e payload
    topic = message.topic
    payload = message.payload.decode()
    topicos = topic.split("/")

    if len(topicos) != 4:
        return
    else:
        sistema, embarcado, dispositivo, agente = topicos 

    n_posto = int(dispositivo.split("_")[1])
    if n_posto > ultimo_posto_bios:
        return

    if sistema == "rastreio_nfc" and embarcado == "esp32" and dispositivo == "posto_0" and agente == "dispositivo":
        if verifica_palete_nfc(payload):
            if verifica_estado_producao():
                socketio.emit('add_palete_lido', {'codigo': cartao_palete[payload]})
                return
            else:
                socketio.emit('aviso_ao_operador_assoc', {'mensagem': "Produção não iniciada. Retire o palete do Posto 0.", 'cor': "#dc3545", 'tempo': 3000})
                return
        elif payload in ["BS", "BT1", "BT2","BD"]:
            return
        else:
            socketio.emit('aviso_ao_operador_assoc', {'mensagem': "Achou que eu tava brincando é?", 'cor': "#2fcce0", 'tempo': 3000})
            return
    else:
        return
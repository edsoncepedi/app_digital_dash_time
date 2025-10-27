from auxiliares.utils import verifica_palete_nfc, cartao_palete

troca_cor = {}

def front_mqtt_assoc(message, socketio):
    global troca_cor
    # Separa a mensagem em topico e payload
    topic = message.topic
    payload = message.payload.decode()
    topicos = topic.split("/")

    if len(topicos) != 4:
        return
    else:
        sistema, esp, dispositivo, agente = topicos 
    
    if sistema == "rastreio_nfc" and dispositivo == "posto_0" and agente == "dispositivo":
        if verifica_palete_nfc(payload):
            print("Socket io ATUE")
            socketio.emit('add_palete_lido', {'codigo': cartao_palete[payload]})
        else:
            return
    else:
        return
from auxiliares.classes import tratar_rastreador, inicia_sistema_rastreador
from auxiliares.utils import trata_ips
from auxiliares.front_assoc import front_mqtt_assoc

def configurar_mqtt_handlers(mqtt, socketio):
    @mqtt.on_connect()
    def handle_connect(client, userdata, flags, rc):
        print("Conectado ao broker MQTT.")
        mqtt.subscribe("#")
        mqtt.publish(f"ControleProducao", f"Stop")

    @mqtt.on_message()
    def handle_mqtt_message(client, userdata, message):
        try:
            inicia_sistema_rastreador(message)
        except Exception as e:
            print(f"Erro tratamento Inicia_sistema_rastreador: {e}")

        try:
            front_mqtt_assoc(message, socketio)
        except Exception as e:
            print(f"Erro tratamento rastreadores: {e}")

        try:
            tratar_rastreador(mqtt, message)
        except Exception as e:
            print(f"Erro tratamento rastreadores: {e}")

        try:
            trata_ips(message)
        except Exception as e:
            print(f"Erro tratamento de ips: {e}")

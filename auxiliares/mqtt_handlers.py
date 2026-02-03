from auxiliares.front_assoc import front_mqtt_assoc

def configurar_mqtt_handlers(mqtt, socketio, supervisor):
    @mqtt.on_connect()
    def handle_connect(client, userdata, flags, rc):
        print("Conectado ao broker MQTT.")
        mqtt.subscribe("#")
        mqtt.publish(f"ControleProducao_DD", f"Stop")

    @mqtt.on_message()
    def handle_mqtt_message(client, userdata, message):
        try:
            front_mqtt_assoc(message, socketio)
        except Exception as e:
            print(f"[MQTT] - Front Assoc: {e}")

        try:
            supervisor.handle_mqtt_message(message)
        except Exception as e:
            print(f"Erro tratamento rastreadores: {e}")

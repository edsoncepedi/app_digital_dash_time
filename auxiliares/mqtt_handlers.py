from auxiliares.front_assoc import front_mqtt_assoc

def configurar_mqtt_handlers(mqtt, socketio, supervisor, state):
    @mqtt.on_connect()
    def handle_connect(client, userdata, flags, rc):
        print("Conectado ao broker MQTT.")
        mqtt.subscribe("#")
        mqtt.publish(f"ControleProducao_DD", f"Stop")

    @mqtt.on_message()
    def handle_mqtt_message(client, userdata, message):
        try:
            front_mqtt_assoc(message, socketio, state)
        except Exception as e:
            print(f"[MQTT] - Front Assoc: {e}")

        try:
            topic = getattr(message, "topic", "") or ""
            if topic.startswith("visao/") and topic.endswith("/estado"):
                # Ex: visao/posto_0/estado  payload: FINALIZADO
                supervisor.vision_state.handle_mqtt_message_vision(message)
                return
        except Exception as e:
            print(f"[MQTT] - VisionState: {e}")
        
        #try:
        supervisor.handle_mqtt_message(message)
        #except Exception as e:
            #print(f"[MQTT] - Supervisor: {e}")

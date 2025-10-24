import eventlet
eventlet.monkey_patch()

import os
from dotenv import load_dotenv

from flask import Flask
from flask_mqtt import Mqtt
from flask_socketio import SocketIO

import auxiliares.classes as classes
from auxiliares.routes import configurar_rotas
from auxiliares.mqtt_handlers import configurar_mqtt_handlers
from auxiliares.socketio_handlers import configurar_socketio_handlers
from auxiliares.associacao import inicializa_Base_assoc

load_dotenv()

def create_app():
    # ───────────────────────────────────────────────
    # Inicialização do app Flask
    app = Flask(__name__)
    app.url_map.strict_slashes = False

    # Configurações do MQTT
    app.config['MQTT_BROKER_URL'] = os.getenv('MQTT_BROKER_URL')
    app.config['MQTT_BROKER_PORT'] = int(os.getenv('MQTT_BROKER_PORT', 1883))  # Converte para inteiro e define um padrão
    app.config['MQTT_USERNAME'] = os.getenv('MQTT_USERNAME')
    app.config['MQTT_PASSWORD'] = os.getenv('MQTT_PASSWORD')
    app.config['MQTT_CLIENT_ID'] = os.getenv('MQTT_CLIENT_ID')

    # Inicialização de extensões
    mqtt = Mqtt()
    socketio = SocketIO(app, cors_allowed_origins="*")

    # Registro de funcionalidades
    configurar_rotas(app, mqtt, socketio)
    configurar_mqtt_handlers(mqtt, socketio)
    configurar_socketio_handlers(socketio)

    mqtt.init_app(app)
    # ───────────────────────────────────────────────
    # Inicialização do sistema de Associação
    inicializa_Base_assoc()

    # Inicialização do sistema de Postos
    classes.inicializar_postos()

    return app, socketio

# ───────────────────────────────────────────────
# Execução da aplicação
if __name__ == '__main__':
    app, socketio = create_app()
    socketio.run(app, host='0.0.0.0', port=7000)
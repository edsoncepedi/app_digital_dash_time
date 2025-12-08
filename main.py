import eventlet
eventlet.monkey_patch()

import os
from dotenv import load_dotenv

from flask import Flask
from flask_mqtt import Mqtt
from flask_socketio import SocketIO

from auxiliares.routes import configurar_rotas
from auxiliares.cadastro_funcionarios import rotas_funcionarios
from auxiliares.mqtt_handlers import configurar_mqtt_handlers
from auxiliares.socketio_handlers import configurar_socketio_handlers
from auxiliares.associacao import inicializa_Base_assoc
from auxiliares.classes import inicializar_postos
import auxiliares.classes as classes
from app.supervisor import PostoSupervisor
from app.socketio_gateway import register_socketio_handlers

load_dotenv()

def create_app():
    # ───────────────────────────────────────────────
    # Inicialização do app Flask
    app = Flask(__name__)
    app.url_map.strict_slashes = False

    #Configurações Sistema Funcionário
    app.config['UPLOAD_FOLDER'] = 'static/funcionarios'
    app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg'}
    app.secret_key = 'chave-secreta'

    # Configurações do MQTT
    app.config['MQTT_BROKER_URL'] = os.getenv('MQTT_BROKER_URL')
    app.config['MQTT_BROKER_PORT'] = int(os.getenv('MQTT_BROKER_PORT', 1883))  # Converte para inteiro e define um padrão
    app.config['MQTT_USERNAME'] = os.getenv('MQTT_USERNAME')
    app.config['MQTT_PASSWORD'] = os.getenv('MQTT_PASSWORD')
    app.config['MQTT_CLIENT_ID'] = os.getenv('MQTT_CLIENT_ID')
    app.config['ADMIN_DELETE_PASSWORD'] = os.getenv("ADMIN_DELETE_PASSWORD", "1234")

    # Inicialização de extensões
    mqtt = Mqtt()
    socketio = SocketIO(app, cors_allowed_origins="*")
    inicializar_postos(mqtt)
    supervisor = PostoSupervisor(classes.postos, socketio, mqtt)

    # Registro de funcionalidades
    configurar_rotas(app, mqtt, socketio, supervisor)
    rotas_funcionarios(app, mqtt, socketio)
    configurar_mqtt_handlers(mqtt, socketio)
    configurar_socketio_handlers(socketio)
    register_socketio_handlers(socketio, supervisor)

    mqtt.init_app(app)
    # ───────────────────────────────────────────────
    # Inicialização do sistema de Associação
    inicializa_Base_assoc()

    return app, socketio

# ───────────────────────────────────────────────
# Execução da aplicação
if __name__ == '__main__':
    app, socketio = create_app()
    socketio.run(app, host=os.getenv("IP_EXT", "0.0.0.0"), port=int(os.getenv("PORT_EXT", 7000)))
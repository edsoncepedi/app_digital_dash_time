from dotenv import load_dotenv
import os

dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(dotenv_path=dotenv_path)

ip = os.getenv('MQTT_BROKER_URL')
ultimo_posto_bios = int(os.getenv('NUMERO_POSTOS', 2))

cartao_palete = {" 83 9A BC FC": "PLT01", 
                 " 39 7E E8 97": "PLT02",
                 " 73 84 74 FC": "PLT03",
                 " C3 C1 A7 FC": "PLT04"}
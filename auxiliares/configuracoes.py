from dotenv import load_dotenv
import os

dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(dotenv_path=dotenv_path)

ip = os.getenv('MQTT_BROKER_URL')
ultimo_posto_bios = int(os.getenv('NUMERO_POSTOS', 2))

cartao_palete = {" C3 C3 64 AD": "PLT01", 
                 " 39 7E E8 97": "PLT02",
                 " 53 4A 68 AC": "PLT03",
                 " 03 48 4E AC": "PLT04"}
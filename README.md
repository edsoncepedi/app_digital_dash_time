# DigitalDash - Sistema Supervisório de Linha de Produção

O **DigitalDash** é uma solução completa de IoT e software para monitoramento, controle e rastreabilidade de linhas de montagem industrial. O sistema integra hardware (ESP32, leitores RFID/NFC, impressoras Zebra) com uma aplicação web em tempo real para gerenciar o fluxo de produção, calcular métricas de eficiência e controlar a alocação de operadores.

## 📋 Funcionalidades Principais

* **Monitoramento em Tempo Real:** Utiliza WebSockets (`Socket.IO`) para atualizar o status dos postos, contagem de produção e alertas instantaneamente no frontend.
* **Rastreabilidade:** Associação lógica entre Paletes (NFC) e Produtos (Códigos Únicos), permitindo o rastreio individual em cada etapa.
* **Gestão de Operadores:**
    * Cadastro de funcionários com foto e Tag RFID.
    * Controle de acesso aos postos via RFID (Check-in/Check-out).
    * Alocação dinâmica de operadores por posto via painel administrativo.
* **Máquina de Estados de Produção:** Lógica robusta para detectar etapas de montagem:
    * *Chegada (BS)*, *Início Processo (BT1)*, *Fim Processo (BT2)* e *Saída (BD)*.
    * Cálculo automático de tempos de **Ciclo, Montagem, Preparo, Espera e Transferência**.
* **Projeção de Metas:** Algoritmo que projeta o tempo estimado para conclusão da meta baseada no ritmo atual da linha.
* **Integração de Hardware:**
    * Comunicação MQTT com dispositivos ESP32.
    * Impressão automática de etiquetas (ZPL) em impressoras Zebra.
    * Controle de atuadores (Buzzers e Torres de Luz).
* **Persistência de Dados:** Histórico salvo em arquivos CSV/Excel e banco de dados SQLite (para funcionários).

## 🛠️ Tech Stack

* **Linguagem:** Python 3.x
* **Backend Framework:** Flask
* **Tempo Real:** Flask-SocketIO
* **IoT & Mensageria:** Flask-MQTT (Protocolo MQTT)
* **Banco de Dados:** SQLAlchemy (SQLite)
* **Processamento de Dados:** Pandas
* **Hardware Suportado:** ESP32, Leitores NFC/RFID, Impressoras Zebra (ZPL).

## 📂 Estrutura do Projeto

```text
├── app/
│   ├── supervisor.py            # Lógica central de supervisão, timers e projeções
│   └── ...
├── auxiliares/
│   ├── associacao.py            # Lógica de vínculo Palete <-> Produto
│   ├── banco_post.py            # Conexão com DB
│   ├── cadastro_funcionarios.py # Rotas e lógica de CRUD de operadores
│   ├── classes.py               # Definição das Classes (Posto, Tabela_Assoc) e Máquina de Estados
│   ├── configuracoes.py         # Configurações globais (nº de postos, mapas de tags)
│   ├── mqtt_handlers.py         # Roteamento de mensagens MQTT
│   ├── routes.py                # Rotas principais do Flask (/controle, /supervisorio)
│   └── utils.py                 # Utilitários (ZPL, backups, validações)
├── static/                      # Arquivos estáticos (CSS, JS, Imagens dos funcionários)
├── templates/                   # HTML (Jinja2)
├── main.py                      # Ponto de entrada da aplicação
└── .env                         # Variáveis de ambiente
```

## 🚀 Instalação e Configuração

### 1. Pré-requisitos
* Python 3.8+
* Servidor MQTT (Ex: Mosquitto) rodando localmente ou na rede.

### 2. Instalação das Dependências

Crie um ambiente virtual e instale as bibliotecas necessárias:

# Cria o ambiente virtual
python -m venv venv

# Ativa o ambiente (Windows)
venv\Scripts\activate
# Ativa o ambiente (Linux/Mac)
source venv/bin/activate

# Instala as dependências
pip install flask flask-socketio flask-mqtt pandas sqlalchemy eventlet python-dotenv pyzbar

### 3. Configuração do Ambiente (.env)

Crie um arquivo `.env` na raiz do projeto com as seguintes variáveis:

# Configurações do Servidor
IP_EXT=0.0.0.0
PORT_EXT=7000

# Configurações MQTT
MQTT_BROKER_URL=127.0.0.1
MQTT_BROKER_PORT=1883
MQTT_USERNAME=seu_usuario
MQTT_PASSWORD=sua_senha
MQTT_CLIENT_ID=Supervisor_PC

# Segurança
ADMIN_DELETE_PASSWORD=senha_mestra

### 4. Executando o Sistema

python main.py

O servidor iniciará (padrão porta 7000).
* **Painel de Controle:** `http://localhost:7000/controle`
* **Supervisório:** `http://localhost:7000/supervisorio`
* **Posto Operador:** `http://localhost:7000/posto/<id>`

## ⚙️ Funcionamento da Lógica de Postos

Cada posto de trabalho é uma instância da classe `Posto` (em `classes.py`), operando como uma máquina de estados finitos alimentada por sensores via MQTT:

1.  **IDLE (Estado 0):** Aguardando produto.
2.  **BS (Sensor de Entrada - Estado 1):** Produto detectado na esteira de entrada. Inicia contagem de *Preparo*.
3.  **BT1 (Botão de Início - Estado 2):** Operador iniciou o trabalho. Inicia contagem de *Montagem*.
4.  **BT2 (Botão de Fim - Estado 3):** Operador finalizou o trabalho. Inicia contagem de *Espera*.
5.  **BD (Sensor de Saída - Estado 4):** Produto saiu do posto. Calcula o tempo de *Transferência* para o próximo posto e reinicia o ciclo.

### Integração com Hardware (Tópicos MQTT)

O sistema escuta tópicos no padrão:
`rastreio_nfc/esp32/posto_X/dispositivo`

Payloads esperados:
* `BS`, `BT1`, `BT2`, `BD`: Comandos de sensores/botões.
* `UID_NFC`: Hexadecimal da tag NFC do palete (exclusivo Posto 0).

## 📊 Banco de Dados e Logs

* **Funcionários:** Armazenados em SQLite (`funcionarios.db`).
* **Produção:** Cada posto gera um arquivo `.csv` (ex: `POSTO_0.csv`) contendo logs detalhados de cada ciclo (timestamps de chegada, montagem, espera, etc).
* **Associações:** O arquivo `associacoes.csv` mantém o vínculo histórico entre o Palete físico e o Produto lógico.

## 🔄 Fluxo de Associação (Posto 0)

1.  O **Palete** (com Tag NFC) chega ao Posto 0.
2.  O sistema lê o NFC via MQTT.
3.  O sistema gera um novo **Código de Produto** (lógica baseada no dia do ano e versão).
4.  O código é enviado para uma impressora Zebra (ZPL) via socket.
5.  O vínculo `Palete <-> Produto` é salvo e o produto entra na linha.

## 🤝 Contribuição

1.  Faça um Fork do projeto.
2.  Crie uma Branch para sua Feature (`git checkout -b feature/NovaFeature`).
3.  Faça o Commit (`git commit -m 'Add some NovaFeature'`).
4.  Push para a Branch (`git push origin feature/NovaFeature`).
5.  Abra um Pull Request.

---
*Desenvolvido por Edson Alves*
